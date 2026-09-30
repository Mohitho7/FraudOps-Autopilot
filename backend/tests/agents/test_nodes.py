"""Node execution tests (Member 2, Batch 2).

Every node is exercised against the deterministic fake toolset: the happy path,
the skip-on-resume path, and the refusal to invent data when the fixed dataset
does not contain the subject. Also asserts that no analysis happened -- Batch 2
loads context and stops.
"""

from __future__ import annotations

from typing import cast

import pytest

from app.agents.graph.nodes import (
    CONTEXT_LOADING_NODES,
    FinalizeInvestigationNode,
    InitializeInvestigationNode,
    LoadCustomerContextNode,
    LoadMerchantContextNode,
    LoadRelationshipContextNode,
    LoadTransactionContextNode,
    ValidateInvestigationInputNode,
    node_completed,
)
from app.agents.graph.state import InvestigationState
from app.agents.graph.errors import ToolExecutionError
from app.agents.tools.fakes import (
    FAKE_CUSTOMER_ID,
    FAKE_MERCHANT_ID,
    FAKE_TRANSACTION_ID,
    FakeInvestigationToolset,
)
from app.schemas.investigation import InvestigationStatus, InvestigationStep
from tests.conftest import make_request, make_rule_result


@pytest.fixture
def state(investigation_request: object) -> InvestigationState:
    return InvestigationState.from_request(
        cast("object", investigation_request)
    )


async def test_initialize_records_the_start_of_the_audit_trail(
    fake_toolset: FakeInvestigationToolset, state: InvestigationState
) -> None:
    node = InitializeInvestigationNode(fake_toolset)

    update = await node(state)

    assert state.status is InvestigationStatus.RUNNING
    assert state.current_step is InvestigationStep.LOAD_STATE
    assert update["status"] is InvestigationStatus.RUNNING
    assert node_completed(state, node.name)
    assert state.activity[-1].tool_name == "initialize_investigation"
    assert "from the deterministic engine" in state.activity[-1].summary


async def test_initialize_is_skipped_on_a_second_pass(
    fake_toolset: FakeInvestigationToolset, state: InvestigationState
) -> None:
    node = InitializeInvestigationNode(fake_toolset)
    await node(state)
    before = len(state.activity)

    assert await node(state) == {}
    assert len(state.activity) == before


async def test_initialize_refuses_an_untraceable_state(
    fake_toolset: FakeInvestigationToolset, state: InvestigationState
) -> None:
    state.case_id = None
    node = InitializeInvestigationNode(fake_toolset)

    with pytest.raises(ToolExecutionError, match="no case id"):
        await node(state)


async def test_validate_agrees_with_the_stored_rule_results(
    fake_toolset: FakeInvestigationToolset, state: InvestigationState
) -> None:
    node = ValidateInvestigationInputNode(fake_toolset)

    await node(state)

    summary = state.activity[-1].summary
    assert "stored rule result(s)" in summary
    assert "confirmed the same transaction" in summary


async def test_validate_notes_a_divergence_without_failing(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    """Member 1 stays authoritative; a divergence is audited, not fatal."""

    state = InvestigationState.from_request(
        make_request(triggered_rules=[make_rule_result("unrelated_rule")])
    )
    node = ValidateInvestigationInputNode(fake_toolset)

    update = await node(state)

    assert "differ" in state.activity[-1].summary
    assert update["current_step"] is InvestigationStep.VALIDATE_OUTPUT
    assert state.error is None


async def test_validate_updates_only_real_state_fields(
    fake_toolset: FakeInvestigationToolset, state: InvestigationState
) -> None:
    """The update must only carry fields that exist on InvestigationState.

    LangGraph rejects an update with an unknown key, so a node that invents a
    field name fails at runtime rather than at import.
    """

    node = ValidateInvestigationInputNode(fake_toolset)

    update = await node(state)

    assert set(update) <= set(InvestigationState.model_fields)


async def test_transaction_context_uses_the_member1_snapshot(
    fake_toolset: FakeInvestigationToolset, state: InvestigationState
) -> None:
    node = LoadTransactionContextNode(fake_toolset)

    await node(state)

    assert "no read tool was needed" in state.activity[-1].summary
    assert state.transaction_context is not None


async def test_transaction_context_falls_back_to_the_history_tool(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    """Without a Member 1 snapshot the node locates the row via history."""

    state = InvestigationState.from_request(
        make_request(transaction_context=None)
    )
    node = LoadTransactionContextNode(fake_toolset)

    await node(state)

    assert state.transaction_context is not None
    assert state.transaction_context.transaction_id == FAKE_TRANSACTION_ID


async def test_transaction_context_refuses_an_unscopable_state(
    fake_toolset: FakeInvestigationToolset, state: InvestigationState
) -> None:
    state.transaction_context = None
    state.customer_id = None
    state.merchant_id = None
    node = LoadTransactionContextNode(fake_toolset)

    with pytest.raises(ToolExecutionError, match="no approved read tool"):
        await node(state)


async def test_transaction_context_refuses_a_missing_transaction(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    from uuid import uuid4

    unknown = uuid4()
    state = InvestigationState.from_request(
        make_request(transaction_context=None, transaction_id=unknown)
    )
    node = LoadTransactionContextNode(fake_toolset)

    with pytest.raises(ToolExecutionError, match="not found in the stored history"):
        await node(state)


async def test_customer_context_records_the_baseline(
    fake_toolset: FakeInvestigationToolset, state: InvestigationState
) -> None:
    node = LoadCustomerContextNode(fake_toolset)

    await node(state)

    assert state.customer_context is not None
    assert state.customer_context.amount_statistics is not None
    assert state.customer_context.amount_statistics.sample_size == 10
    assert "10 transaction(s)" in state.activity[-1].summary


async def test_customer_context_refuses_an_unknown_customer(
    fake_toolset: FakeInvestigationToolset, state: InvestigationState
) -> None:
    from uuid import uuid4

    state.customer_id = uuid4()
    node = LoadCustomerContextNode(fake_toolset)

    with pytest.raises(ToolExecutionError, match="no customer"):
        await node(state)


async def test_merchant_context_records_the_percentile_bands(
    fake_toolset: FakeInvestigationToolset, state: InvestigationState
) -> None:
    node = LoadMerchantContextNode(fake_toolset)

    await node(state)

    assert state.merchant_context is not None
    assert state.merchant_context.expected_p95 is not None
    assert "expected p95" in state.activity[-1].summary


async def test_merchant_context_refuses_an_unknown_merchant(
    fake_toolset: FakeInvestigationToolset, state: InvestigationState
) -> None:
    from uuid import uuid4

    state.merchant_id = uuid4()
    node = LoadMerchantContextNode(fake_toolset)

    with pytest.raises(ToolExecutionError, match="no merchant"):
        await node(state)


async def test_relationship_context_stores_links_without_interpreting_them(
    fake_toolset: FakeInvestigationToolset, state: InvestigationState
) -> None:
    node = LoadRelationshipContextNode(fake_toolset)

    await node(state)

    assert len(state.related_entities) == 3
    assert state.all_findings() == []
    assert "3 related entity" in state.activity[-1].summary


async def test_relationship_context_refuses_an_unknown_transaction(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    from uuid import uuid4

    state = InvestigationState.from_request(
        make_request(transaction_context=None, transaction_id=uuid4())
    )
    node = LoadRelationshipContextNode(fake_toolset)

    with pytest.raises(ToolExecutionError, match="no transaction"):
        await node(state)


async def test_finalize_completes_without_a_recommendation(
    fake_toolset: FakeInvestigationToolset, state: InvestigationState
) -> None:
    node = FinalizeInvestigationNode(fake_toolset)

    await node(state)

    assert state.status is InvestigationStatus.COMPLETED
    assert state.current_step is InvestigationStep.COMPLETE
    assert state.completed_at is not None
    assert state.recommendation is None


def test_context_node_names_match_the_workflow() -> None:
    """Node keys are derived from class names, so the two cannot drift."""

    from app.agents.graph.workflow import BATCH2_NODE_CLASSES, BATCH2_NODE_NAMES

    assert set(CONTEXT_LOADING_NODES) <= set(BATCH2_NODE_NAMES)
    assert len(BATCH2_NODE_CLASSES) == len(BATCH2_NODE_NAMES) == 7


async def test_nodes_use_only_approved_tool_names(
    fake_toolset: FakeInvestigationToolset, state: InvestigationState
) -> None:
    """The audit trail may only name tools from the Batch 1 toolset."""

    approved = {
        "get_recent_transactions",
        "get_customer_history",
        "get_rule_results",
        "get_merchant_profile",
        "get_related_entities",
    }
    for node_class, name in (
        (ValidateInvestigationInputNode, "validate_investigation_input"),
        (LoadTransactionContextNode, "load_transaction_context"),
        (LoadCustomerContextNode, "load_customer_context"),
        (LoadMerchantContextNode, "load_merchant_context"),
        (LoadRelationshipContextNode, "load_relationship_context"),
    ):
        fresh = InvestigationState.from_request(make_request())
        await node_class(fake_toolset)(fresh)
        used = {event.tool_name for event in fresh.activity}
        assert used <= {name} | approved


def test_fixed_dataset_ids_match_the_demo_request() -> None:
    request = make_request()

    assert request.transaction_id == FAKE_TRANSACTION_ID
    assert request.customer_id == FAKE_CUSTOMER_ID
    assert request.merchant_id == FAKE_MERCHANT_ID
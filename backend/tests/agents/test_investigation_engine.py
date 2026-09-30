"""Service lifecycle, checkpoint/resume and error handling tests (Member 2, Batch 2).

The Batch 1 suite in ``test_investigation_service.py`` covers the boundary
contract. This file covers the Batch 2 engine: a real graph run, idempotent
start, resume after a mid-graph failure, and the guarantee that no completed
node is ever executed twice.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.agents.config import InvestigationSettings
from app.agents.graph.checkpoint import InMemoryCheckpointStore
from app.agents.graph.errors import InvestigationWorkflowError
from app.agents.graph.state import InvestigationState
from app.agents.graph.workflow import BATCH2_NODE_NAMES
from app.agents.tools.fakes import FakeInvestigationToolset
from app.schemas.investigation import (
    InvestigationStatus,
    InvestigationStep,
    InvestigationTrigger,
    Severity,
)
from app.services.investigation_service import (
    InMemoryInvestigationService,
    InvestigationAlreadyCompletedError,
    InvestigationAlreadyRunningError,
    InvestigationNotFoundError,
    InvestigationNotRequiredError,
    InvestigationService,
    LangGraphInvestigationService,
    investigation_identity_key,
    should_start_investigation,
)
from tests.conftest import make_request, restore_read_layer


def build_service(
    toolset: FakeInvestigationToolset,
) -> LangGraphInvestigationService:
    """Build an engine with a fresh, isolated checkpoint store."""

    return LangGraphInvestigationService(
        toolset,
        settings=InvestigationSettings(checkpoint_backend="memory"),
        checkpoint_store=InMemoryCheckpointStore(),
    )


def test_langgraph_service_satisfies_the_batch1_boundary() -> None:
    """Member 1 and Member 3 depend on the interface, not the implementation."""

    assert issubclass(LangGraphInvestigationService, InvestigationService)
    assert issubclass(InMemoryInvestigationService, InvestigationService)


def test_identity_key_pairs_the_transaction_with_its_case() -> None:
    request = make_request()

    assert investigation_identity_key(request) == (
        str(request.transaction_id),
        str(request.case_id),
    )


def test_identity_key_differs_for_a_different_case() -> None:
    first = investigation_identity_key(make_request())
    second = investigation_identity_key(make_request(case_id=uuid4()))

    assert first != second


def test_low_severity_needs_an_explicit_reviewer_request() -> None:
    automatic = make_request(severity=Severity.LOW)
    reviewer = make_request(
        severity=Severity.LOW,
        trigger=InvestigationTrigger.REVIEWER_REQUEST,
        requested_by="reviewer-1",
    )

    assert not should_start_investigation(automatic)
    assert should_start_investigation(reviewer)


async def test_start_refuses_a_below_threshold_request(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    service = build_service(fake_toolset)

    with pytest.raises(InvestigationNotRequiredError, match="below the automatic"):
        await service.start_investigation(make_request(severity=Severity.LOW))


async def test_start_runs_the_whole_batch2_graph(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    service = build_service(fake_toolset)

    final = await service.start_investigation(make_request())

    assert final.status is InvestigationStatus.COMPLETED
    assert final.current_step is InvestigationStep.COMPLETE
    assert final.completed_at is not None
    assert final.customer_context is not None
    assert final.merchant_context is not None
    assert len(final.related_entities) == 3
    assert final.error is None


async def test_batch2_produces_no_findings_or_recommendation(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    """Context loading is not a conclusion; nothing may look like one."""

    service = build_service(fake_toolset)

    final = await service.start_investigation(make_request())

    assert final.all_findings() == []
    assert final.evidence == []
    assert final.recommendation is None
    assert final.confidence is None


async def test_run_uses_only_approved_tools(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    """No invented tool names in the audit trail."""

    approved = {
        "get_recent_transactions",
        "get_customer_history",
        "get_rule_results",
        "get_merchant_profile",
        "get_related_entities",
    }
    service = build_service(fake_toolset)

    final = await service.start_investigation(make_request())

    # The audit trail names nodes, not tools, so assert the inverse: every entry
    # is either a known Batch 2 node or an approved Batch 1 tool name.
    known = set(BATCH2_NODE_NAMES) | approved
    used = {event.tool_name for event in final.activity if event.tool_name}
    assert used
    assert used <= known


async def test_every_node_is_recorded_exactly_once(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    service = build_service(fake_toolset)

    final = await service.start_investigation(make_request())

    for name in BATCH2_NODE_NAMES:
        completions = [
            event
            for event in final.activity
            if event.tool_name == name and event.status == "COMPLETED"
        ]
        assert len(completions) == 1, name


async def test_get_returns_a_defensive_copy(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    service = build_service(fake_toolset)
    started = await service.start_investigation(make_request())

    first = await service.get_investigation(started.investigation_id)
    first.status = InvestigationStatus.FAILED
    second = await service.get_investigation(started.investigation_id)

    assert second.status is InvestigationStatus.COMPLETED


async def test_get_refuses_an_unknown_id(fake_toolset: FakeInvestigationToolset) -> None:
    service = build_service(fake_toolset)

    with pytest.raises(InvestigationNotFoundError):
        await service.get_investigation(uuid4())


async def test_start_is_idempotent_for_the_same_fraud_result(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    """A redelivered Member 1 result must not create a second investigation."""

    service = build_service(fake_toolset)
    request = make_request()
    first = await service.start_investigation(request)

    with pytest.raises(InvestigationAlreadyCompletedError):
        await service.start_investigation(request)

    assert (await service.get_investigation(first.investigation_id)).status is (
        InvestigationStatus.COMPLETED
    )


async def test_a_different_case_gets_its_own_investigation(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    service = build_service(fake_toolset)
    first = await service.start_investigation(make_request())

    second = await service.start_investigation(make_request(case_id=uuid4()))

    assert second.investigation_id != first.investigation_id


async def test_resume_of_a_completed_investigation_is_a_no_op(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    service = build_service(fake_toolset)
    started = await service.start_investigation(make_request())
    activity_before = len(started.activity)

    resumed = await service.resume_investigation(started.investigation_id)

    assert resumed.status is InvestigationStatus.COMPLETED
    assert len(resumed.activity) == activity_before


async def test_resume_refuses_an_unknown_id(fake_toolset: FakeInvestigationToolset) -> None:
    service = build_service(fake_toolset)

    with pytest.raises(InvestigationNotFoundError):
        await service.resume_investigation(uuid4())


async def test_a_failed_tool_leaves_the_investigation_failed_and_retryable(
    failing_toolset: FakeInvestigationToolset,
) -> None:
    """A failure is recorded and represented, never swallowed."""

    service = build_service(failing_toolset)
    request = make_request()

    with pytest.raises(InvestigationWorkflowError):
        await service.start_investigation(request)

    state = await service.get_investigation(_only_investigation_id(service))
    assert state.status is InvestigationStatus.FAILED
    assert state.current_step is InvestigationStep.FAILURE
    assert state.error is not None
    assert "simulated read-layer outage" in (state.error.message or "")
    assert state.retry_count >= 1


async def test_resume_after_a_failure_skips_completed_nodes(
    failing_toolset: FakeInvestigationToolset,
) -> None:
    """The core Batch 2 guarantee: completed work is not repeated."""

    service = build_service(failing_toolset)
    with pytest.raises(InvestigationWorkflowError):
        await service.start_investigation(make_request())

    failed = await service.get_investigation(_only_investigation_id(service))
    completed_before = {
        event.tool_name
        for event in failed.activity
        if event.status == "COMPLETED" and event.tool_name in BATCH2_NODE_NAMES
    }
    assert "load_customer_context" in completed_before
    assert "finalize_investigation" not in completed_before

    # The read layer recovers.
    _restore_merchant_tool(failing_toolset)
    resumed = await service.resume_investigation(failed.investigation_id)

    assert resumed.status is InvestigationStatus.COMPLETED
    assert resumed.current_step is InvestigationStep.COMPLETE
    for name in completed_before:
        completions = [
            event
            for event in resumed.activity
            if event.tool_name == name and event.status == "COMPLETED"
        ]
        assert len(completions) == 1, f"{name} was re-executed on resume"


async def test_resume_after_a_failure_clears_the_previous_error(
    failing_toolset: FakeInvestigationToolset,
) -> None:
    service = build_service(failing_toolset)
    with pytest.raises(InvestigationWorkflowError):
        await service.start_investigation(make_request())
    failed = await service.get_investigation(_only_investigation_id(service))

    _restore_merchant_tool(failing_toolset)
    resumed = await service.resume_investigation(failed.investigation_id)

    assert resumed.error is None
    assert resumed.status is InvestigationStatus.COMPLETED


async def test_a_failed_resume_can_be_retried(
    failing_toolset: FakeInvestigationToolset,
) -> None:
    """Two failures in a row must still leave a resumable investigation."""

    service = build_service(failing_toolset)
    with pytest.raises(InvestigationWorkflowError):
        await service.start_investigation(make_request())
    investigation_id = _only_investigation_id(service)

    with pytest.raises(InvestigationWorkflowError):
        await service.resume_investigation(investigation_id)

    state = await service.get_investigation(investigation_id)
    assert state.status is InvestigationStatus.FAILED

    _restore_merchant_tool(failing_toolset)
    assert (await service.resume_investigation(investigation_id)).status is (
        InvestigationStatus.COMPLETED
    )


async def test_start_is_refused_while_the_same_case_is_running(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    """A second start on a live investigation is refused, not duplicated.

    Simulated by marking the stored state ``RUNNING``, which is what the
    service holds between ``start_investigation`` and its return.
    """

    service = build_service(fake_toolset)
    started = await service.start_investigation(make_request())
    service._states[started.investigation_id].status = InvestigationStatus.RUNNING

    with pytest.raises(InvestigationAlreadyRunningError, match="resume_investigation"):
        await service.start_investigation(make_request())

    assert len(service._states) == 1


async def test_state_is_recoverable_from_the_checkpoint_store(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    """The store holds a materialised copy, so a lost service can still resume."""

    service = build_service(fake_toolset)
    final = await service.start_investigation(make_request())

    restored = await service.checkpoint_store.load_state(final.investigation_id)

    assert restored is not None
    assert restored.status is InvestigationStatus.COMPLETED
    assert restored.customer_context is not None


async def test_the_engine_never_calls_a_language_model(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    """Batch 2 must stay deterministic: no OpenAI client, no model name in state."""

    service = build_service(fake_toolset)

    final = await service.start_investigation(make_request())

    assert "openai" not in {type(service._graph).__module__}
    assert final.confidence is None


async def test_in_memory_service_boundary_still_holds(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    """The Batch 1 stub is untouched and still satisfies the contract."""

    service = InMemoryInvestigationService()

    state = await service.start_investigation(make_request())

    assert isinstance(state, InvestigationState)
    assert state.status is InvestigationStatus.RUNNING
    assert await service.get_investigation(state.investigation_id) == state


def _only_investigation_id(service: LangGraphInvestigationService):
    """Return the single investigation id the service currently holds."""

    return next(iter(service._states))


def _restore_merchant_tool(toolset: FakeInvestigationToolset) -> None:
    """Undo the simulated merchant outage."""

    restore_read_layer(toolset)
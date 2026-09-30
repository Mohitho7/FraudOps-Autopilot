"""Graph assembly tests (Member 2, Batch 2).

Covers the documented Batch 2 shape, the audit-trail dispatcher that makes
resume skip finished work, and the transition table retained for later batches.
"""

from __future__ import annotations

from app.agents.graph.nodes import (
    INVESTIGATION_NODE_SEQUENCE,
    LoadMerchantContextNode,
    LoadRelationshipContextNode,
    node_completed,
)
from app.agents.graph.state import InvestigationState
from app.agents.graph.workflow import (
    BATCH2_NODE_NAMES,
    PLANNED_EDGES,
    build_batch2_nodes,
    build_investigation_graph,
    route_next_node,
)
from app.schemas.investigation import InvestigationStep


def test_batch2_wires_the_documented_nodes() -> None:
    assert BATCH2_NODE_NAMES == (
        "initialize_investigation",
        "validate_investigation_input",
        "load_transaction_context",
        "load_customer_context",
        "load_merchant_context",
        "load_relationship_context",
        "finalize_investigation",
    )


def test_batch2_does_not_wire_analysis_nodes(fake_toolset: object) -> None:
    """Only context loading is wired; analysis and handoff stay unbuilt."""

    graph = build_investigation_graph(fake_toolset, None)  # type: ignore[arg-type]
    compiled_nodes = set(graph.get_graph().nodes)

    assert "analyze_transaction" not in compiled_nodes
    assert "generate_recommendation" not in compiled_nodes
    assert "human_handoff" not in compiled_nodes
    assert set(BATCH2_NODE_NAMES) == compiled_nodes - {"__start__", "__end__"}


def test_planned_edges_cover_the_full_documented_workflow() -> None:
    assert set(PLANNED_EDGES) == set(INVESTIGATION_NODE_SEQUENCE) | {
        InvestigationStep.FAILURE
    }
    assert PLANNED_EDGES[InvestigationStep.COMPLETE] == ()
    assert PLANNED_EDGES[InvestigationStep.FAILURE] == ()
    assert InvestigationStep.LOAD_STATE in PLANNED_EDGES


def _complete(state: InvestigationState, node_name: str, *, status: str = "COMPLETED") -> None:
    state.record_activity(
        step=InvestigationStep.CALL_TOOL,
        status=status,
        tool_name=node_name,
        summary="test",
    )


def test_router_starts_with_the_first_node(investigation_request: object) -> None:
    state = InvestigationState.from_request(investigation_request)  # type: ignore[arg-type]

    assert route_next_node(state) == "initialize_investigation"


def test_router_advances_past_completed_nodes(investigation_request: object) -> None:
    state = InvestigationState.from_request(investigation_request)  # type: ignore[arg-type]
    _complete(state, "initialize_investigation")
    _complete(state, "validate_investigation_input")

    assert route_next_node(state) == "load_transaction_context"


def test_router_ends_when_every_node_completed(investigation_request: object) -> None:
    state = InvestigationState.from_request(investigation_request)  # type: ignore[arg-type]
    for name in BATCH2_NODE_NAMES:
        _complete(state, name)

    assert route_next_node(state) == "__end__"


def test_router_reselects_a_failed_node(investigation_request: object) -> None:
    """A failed node has no COMPLETED marker, so it is the one selected again."""

    state = InvestigationState.from_request(investigation_request)  # type: ignore[arg-type]
    for name in BATCH2_NODE_NAMES:
        if name == "load_merchant_context":
            _complete(state, name, status="FAILED")
            continue
        _complete(state, name)

    assert route_next_node(state) == "load_merchant_context"


def test_router_ignores_step_names_that_are_not_nodes(investigation_request: object) -> None:
    """Batch 1 step names live in completed_steps; only node names gate routing."""

    state = InvestigationState.from_request(investigation_request)  # type: ignore[arg-type]
    _complete(state, "not_a_node")
    state.completed_steps = [InvestigationStep.LOAD_STATE.value]

    assert route_next_node(state) == "initialize_investigation"


def test_build_batch2_nodes_returns_one_instance_per_node(fake_toolset: object) -> None:
    nodes = build_batch2_nodes(fake_toolset)  # type: ignore[arg-type]

    assert tuple(nodes) == BATCH2_NODE_NAMES
    assert isinstance(nodes["load_merchant_context"], LoadMerchantContextNode)
    assert isinstance(nodes["load_relationship_context"], LoadRelationshipContextNode)


def test_graph_honours_the_configured_checkpoint_backend(fake_toolset: object) -> None:
    from app.agents.config import InvestigationSettings

    settings = InvestigationSettings(checkpoint_backend="memory")
    graph = build_investigation_graph(fake_toolset, settings)  # type: ignore[arg-type]

    assert graph.get_graph().nodes


def test_node_completed_requires_a_completed_activity(
    fake_toolset: object, investigation_request: object
) -> None:
    """Only a COMPLETED activity counts; a FAILED one must not gate routing."""

    node = LoadMerchantContextNode(fake_toolset)  # type: ignore[arg-type]
    state = InvestigationState.from_request(investigation_request)  # type: ignore[arg-type]
    assert not node_completed(state, node.name)

    state.record_activity(
        step=InvestigationStep.CALL_TOOL,
        status="FAILED",
        tool_name=node.name,
        summary="boom",
    )
    assert not node_completed(state, node.name)

    state.record_activity(
        step=InvestigationStep.CALL_TOOL,
        status="COMPLETED",
        tool_name=node.name,
        summary="ok",
    )
    assert node_completed(state, node.name)
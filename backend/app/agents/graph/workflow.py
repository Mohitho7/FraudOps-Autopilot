"""LangGraph workflow assembly (Member 2).

Status
------
Batch 2 implements the first runnable slice of the investigation workflow. The
graph loads deterministic context through approved tools and stops. Analysis,
evidence building, recommendation and human handoff are declared but not wired:
they belong to later batches.

Shape (Agent System Design section 8, Batch 2 subset)
-----------------------------------------------------
::

    START
      -> initialize_investigation
      -> validate_investigation_input
      -> load_transaction_context
      -> load_customer_context
      -> load_merchant_context
      -> load_relationship_context
      -> finalize_investigation
      -> END

Dispatch
--------
Routing is not a fixed chain. ``route_next_node`` inspects the investigation's
own audit trail and dispatches to the first node that has not yet completed,
which is what makes resume skip finished work
(``Agent System Design`` section 13). A node that failed has a ``FAILED``
activity entry rather than a ``COMPLETED`` one, so it is selected again on the
next run while every completed node stays untouched.

Checkpointing
-------------
The checkpointer comes from
:class:`~app.agents.graph.checkpoint.InvestigationCheckpointStore`, selected via
:attr:`~app.agents.config.InvestigationSettings.checkpoint_backend`. It stays
in-process ``memory`` until Member 4 provides the PostgreSQL checkpointer. The
thread identity is the investigation id, so resume is keyed by the same id that
the rest of the system uses.

BOUNDARY
--------
The graph never touches a database, an HTTP client or a language model. Its only
outbound dependency is the :class:`~app.agents.tools.base.InvestigationToolset`
it is compiled with, which is how the least-privilege guardrail survives
wiring.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from langgraph.graph import END, START, StateGraph

from app.agents.graph.checkpoint import (
    InvestigationCheckpointStore,
    build_checkpoint_store,
)
from app.agents.graph.nodes import (
    TERMINATE_INVESTIGATION,
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
from app.schemas.investigation import InvestigationStep

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.agents.tools.base import InvestigationToolset

__all__ = [
    "BATCH2_NODE_CLASSES",
    "BATCH2_NODE_NAMES",
    "PLANNED_EDGES",
    "build_investigation_graph",
    "build_batch2_nodes",
    "route_next_node",
]

PLANNED_EDGES: dict[InvestigationStep, tuple[InvestigationStep, ...]] = {
    InvestigationStep.LOAD_STATE: (InvestigationStep.CHECK_EVIDENCE,),
    InvestigationStep.CHECK_EVIDENCE: (
        InvestigationStep.SELECT_NEXT_CHECK,
        InvestigationStep.BEHAVIORAL_ANALYSIS,
        InvestigationStep.BUSINESS_CONTEXT_ANALYSIS,
        InvestigationStep.RELATIONSHIP_ANALYSIS,
        InvestigationStep.EVIDENCE_BUILD,
        InvestigationStep.HUMAN_HANDOFF,
    ),
    InvestigationStep.SELECT_NEXT_CHECK: (
        InvestigationStep.CALL_TOOL,
        InvestigationStep.BEHAVIORAL_ANALYSIS,
        InvestigationStep.BUSINESS_CONTEXT_ANALYSIS,
        InvestigationStep.RELATIONSHIP_ANALYSIS,
    ),
    InvestigationStep.CALL_TOOL: (InvestigationStep.VALIDATE_OUTPUT,),
    InvestigationStep.VALIDATE_OUTPUT: (InvestigationStep.PERSIST_FINDING,),
    InvestigationStep.PERSIST_FINDING: (InvestigationStep.CHECK_EVIDENCE,),
    InvestigationStep.BEHAVIORAL_ANALYSIS: (
        InvestigationStep.EVIDENCE_BUILD,
        InvestigationStep.CHECK_EVIDENCE,
    ),
    InvestigationStep.BUSINESS_CONTEXT_ANALYSIS: (
        InvestigationStep.EVIDENCE_BUILD,
        InvestigationStep.CHECK_EVIDENCE,
    ),
    InvestigationStep.RELATIONSHIP_ANALYSIS: (
        InvestigationStep.EVIDENCE_BUILD,
        InvestigationStep.CHECK_EVIDENCE,
    ),
    InvestigationStep.EVIDENCE_BUILD: (InvestigationStep.RECOMMENDATION,),
    InvestigationStep.RECOMMENDATION: (InvestigationStep.HUMAN_HANDOFF,),
    InvestigationStep.HUMAN_HANDOFF: (InvestigationStep.COMPLETE,),
    InvestigationStep.COMPLETE: (),
    InvestigationStep.FAILURE: (),
}
"""Documented transition table for the full workflow.

Batch 2 wires only the subset below. The analysis, evidence, recommendation and
handoff transitions are retained so the full table stays the reference when
those batches land; none of them is an edge in the compiled graph yet.
"""

BATCH2_NODE_CLASSES: tuple[type, ...] = (
    InitializeInvestigationNode,
    ValidateInvestigationInputNode,
    LoadTransactionContextNode,
    LoadCustomerContextNode,
    LoadMerchantContextNode,
    LoadRelationshipContextNode,
    FinalizeInvestigationNode,
)
"""Node classes wired in Batch 2, in execution order."""

def _node_name(node_class: type) -> str:
    """Return the LangGraph node key for a node class.

    Derived from the class name so the node key and the audit-trail entry can
    never drift apart.
    """

    base = node_class.__name__
    if base.endswith("Node"):
        base = base[: -len("Node")]
    return re.sub(r"(?<!^)(?=[A-Z])", "_", base).lower()


BATCH2_NODE_NAMES: tuple[str, ...] = tuple(
    _node_name(cls) for cls in BATCH2_NODE_CLASSES
)
"""LangGraph node keys, derived from the class names."""


def build_batch2_nodes(toolset: InvestigationToolset) -> dict[str, Any]:
    """Instantiate the Batch 2 nodes against ``toolset``.

    Returns:
        Mapping of LangGraph node key to node instance.
    """

    return {name: cls(toolset) for name, cls in zip(BATCH2_NODE_NAMES, BATCH2_NODE_CLASSES)}


def route_next_node(state: InvestigationState) -> str:
    """Return the name of the next node to run.

    Returns:
        The next node's name, or
        :data:`~app.agents.graph.nodes.TERMINATE_INVESTIGATION` when every node
        has completed.

    The route is derived from the audit trail rather than from a fixed edge, so
    resuming a checkpointed investigation resumes at the first unfinished step
    instead of replaying the whole chain.
    """

    for name in BATCH2_NODE_NAMES:
        if not node_completed(state, name):
            return name
    return TERMINATE_INVESTIGATION


def build_investigation_graph(
    toolset: InvestigationToolset,
    settings: Any,
    checkpoint_store: InvestigationCheckpointStore | None = None,
) -> Any:
    """Compile the Batch 2 LangGraph investigation graph.

    Args:
        toolset: Approved tools the workflow may call. The graph has no other
            outbound dependency, so a fake, a stub and a production read layer
            are interchangeable here.
        settings: Investigation settings. ``checkpoint_backend`` is honoured only
            when ``checkpoint_store`` is not supplied.
        checkpoint_store: Checkpoint store to compile with. Defaults to
            :func:`~app.agents.graph.checkpoint.build_checkpoint_store` for the
            configured backend.

    Returns:
        A compiled LangGraph graph whose state schema is
        :class:`~app.agents.graph.state.InvestigationState`. Invoke it with
        ``ainvoke(state, thread_config)``.

    Raises:
        UnsupportedCheckpointBackendError: When the configured backend is not
            available.
    """

    if checkpoint_store is None:
        from app.agents.config import get_investigation_settings

        effective_settings = settings or get_investigation_settings()
        checkpoint_store = build_checkpoint_store(effective_settings.checkpoint_backend)

    graph = StateGraph(InvestigationState)
    nodes = build_batch2_nodes(toolset)
    for name, node in nodes.items():
        graph.add_node(name, node)

    graph.add_conditional_edges(START, route_next_node, [*nodes, END])
    # Each node dispatches through the same router, which re-evaluates the audit
    # trail. This is what turns a failed run into a resumable one.
    for name in nodes:
        graph.add_conditional_edges(name, route_next_node, [*nodes, END])

    return graph.compile(checkpointer=checkpoint_store.saver())
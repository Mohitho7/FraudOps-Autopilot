"""LangGraph workflow assembly (Member 2).

Status
------
Batch 1 placeholder. ``langgraph`` is intentionally **not** installed yet, and
no graph is compiled. This module fixes the entry point and the node order so
that Batch 2 only has to implement the node bodies and wire the edges.

Planned shape (Agent System Design section 8)
---------------------------------------------
::

    START
      -> load_state
      -> check_evidence
           |- evidence sufficient   -> build_evidence
           |- evidence insufficient -> select_next_check
                                        -> call_tool -> validate_output
                                        -> persist_finding -> check_evidence
      build_evidence
      -> recommendation
      -> human_handoff            (when policy requires a reviewer)
      -> complete
      -> END

Checkpointing
-------------
The checkpointer is chosen by
:attr:`~app.agents.config.InvestigationSettings.checkpoint_backend`. It stays
``memory`` until Member 4 provides the PostgreSQL checkpointer that
``Agent System Design`` section 13 requires for resume-after-failure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.agents.graph.nodes import INVESTIGATION_NODE_SEQUENCE
from app.schemas.investigation import InvestigationStep

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.agents.config import InvestigationSettings
    from app.agents.tools.base import InvestigationToolset

__all__ = ["PLANNED_EDGES", "build_investigation_graph"]


PLANNED_EDGES: dict[InvestigationStep, tuple[InvestigationStep, ...]] = {
    InvestigationStep.LOAD_STATE: (InvestigationStep.CHECK_EVIDENCE,),
    InvestigationStep.CHECK_EVIDENCE: (
        InvestigationStep.SELECT_NEXT_CHECK,
        InvestigationStep.EVIDENCE_BUILD,
        InvestigationStep.HUMAN_HANDOFF,
    ),
    InvestigationStep.SELECT_NEXT_CHECK: (InvestigationStep.CALL_TOOL,),
    InvestigationStep.CALL_TOOL: (InvestigationStep.VALIDATE_OUTPUT,),
    InvestigationStep.VALIDATE_OUTPUT: (InvestigationStep.PERSIST_FINDING,),
    InvestigationStep.PERSIST_FINDING: (InvestigationStep.CHECK_EVIDENCE,),
    InvestigationStep.EVIDENCE_BUILD: (InvestigationStep.RECOMMENDATION,),
    InvestigationStep.RECOMMENDATION: (InvestigationStep.HUMAN_HANDOFF,),
    InvestigationStep.HUMAN_HANDOFF: (InvestigationStep.COMPLETE,),
    InvestigationStep.COMPLETE: (),
    InvestigationStep.FAILURE: (),
}
"""Documented transition table. Implemented as real edges in a later batch."""


def build_investigation_graph(
    toolset: InvestigationToolset,
    settings: InvestigationSettings,
) -> Any:
    """Compile the LangGraph investigation graph.

    Not implemented in Batch 1.

    Args:
        toolset: Approved tools the workflow may call.
        settings: Investigation settings, including the retry budget and the
            checkpointer backend.

    Returns:
        A compiled LangGraph graph whose state schema is
        :class:`~app.agents.graph.state.InvestigationState`.

    Raises:
        NotImplementedError: Always, until the Batch 2 implementation.
    """
    raise NotImplementedError(
        "The LangGraph investigation workflow is implemented in Batch 2. "
        f"Planned node order: {[step.value for step in INVESTIGATION_NODE_SEQUENCE]}"
    )

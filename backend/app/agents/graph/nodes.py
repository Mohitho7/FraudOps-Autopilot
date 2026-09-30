"""Investigation workflow nodes (Member 2).

The node vocabulary and order follow ``Agent System Design`` section 8::

    START -> Load State -> Check Evidence
      |- sufficient  -> Build Evidence
      |- insufficient-> Select Next Check
                        -> Call Approved Tool -> Validate Output
                        -> Persist Finding / Evidence
                        -> Re-evaluate Evidence
    Build Evidence -> Recommendation -> Human Handoff -> END

Batch 1 defines the node set and each node's contract. The node bodies are
implemented in a later batch, when LangGraph is wired in and Member 4's
persistence layer is available.
"""

from __future__ import annotations

from typing import Protocol

from app.agents.graph.state import InvestigationState
from app.schemas.investigation import InvestigationStep

__all__ = [
    "ANALYSIS_STEPS",
    "INVESTIGATION_NODE_SEQUENCE",
    "InvestigationNode",
    "NODE_DESCRIPTIONS",
    "TERMINAL_STEPS",
]

INVESTIGATION_NODE_SEQUENCE: tuple[InvestigationStep, ...] = (
    InvestigationStep.LOAD_STATE,
    InvestigationStep.CHECK_EVIDENCE,
    InvestigationStep.SELECT_NEXT_CHECK,
    InvestigationStep.CALL_TOOL,
    InvestigationStep.VALIDATE_OUTPUT,
    InvestigationStep.PERSIST_FINDING,
    InvestigationStep.BEHAVIORAL_ANALYSIS,
    InvestigationStep.BUSINESS_CONTEXT_ANALYSIS,
    InvestigationStep.RELATIONSHIP_ANALYSIS,
    InvestigationStep.EVIDENCE_BUILD,
    InvestigationStep.RECOMMENDATION,
    InvestigationStep.HUMAN_HANDOFF,
    InvestigationStep.COMPLETE,
)

ANALYSIS_STEPS: tuple[InvestigationStep, ...] = (
    InvestigationStep.BEHAVIORAL_ANALYSIS,
    InvestigationStep.BUSINESS_CONTEXT_ANALYSIS,
    InvestigationStep.RELATIONSHIP_ANALYSIS,
)

TERMINAL_STEPS: tuple[InvestigationStep, ...] = (
    InvestigationStep.COMPLETE,
    InvestigationStep.HUMAN_HANDOFF,
    InvestigationStep.FAILURE,
)

NODE_DESCRIPTIONS: dict[InvestigationStep, str] = {
    InvestigationStep.LOAD_STATE: (
        "Load the persisted investigation state and Member 1's fraud facts."
    ),
    InvestigationStep.CHECK_EVIDENCE: (
        "Decide whether the collected evidence is sufficient to form a case."
    ),
    InvestigationStep.SELECT_NEXT_CHECK: (
        "Choose which investigation capability or tool runs next."
    ),
    InvestigationStep.CALL_TOOL: (
        "Call one approved tool with explicit input identifiers."
    ),
    InvestigationStep.VALIDATE_OUTPUT: (
        "Validate the tool output against its contract before using it."
    ),
    InvestigationStep.PERSIST_FINDING: (
        "Store the finding and its evidence reference, then re-evaluate."
    ),
    InvestigationStep.BEHAVIORAL_ANALYSIS: (
        "Compare the transaction with the customer baseline."
    ),
    InvestigationStep.BUSINESS_CONTEXT_ANALYSIS: (
        "Compare the transaction with the merchant business profile."
    ),
    InvestigationStep.RELATIONSHIP_ANALYSIS: (
        "Assess links to other customers, devices, IPs and merchants."
    ),
    InvestigationStep.EVIDENCE_BUILD: (
        "Assemble the structured evidence pack and the analyst summary."
    ),
    InvestigationStep.RECOMMENDATION: (
        "Produce an advisory action: ALLOW, MONITOR, HOLD_FOR_REVIEW or ESCALATE."
    ),
    InvestigationStep.HUMAN_HANDOFF: (
        "Set the case to WAITING_HUMAN and surface it to the reviewer console."
    ),
    InvestigationStep.COMPLETE: "Finalise the investigation and persist the timeline.",
    InvestigationStep.FAILURE: "Record the failure and stop without claiming success.",
}


class InvestigationNode(Protocol):
    """A single LangGraph node.

    Nodes take the current state and return a partial state update. They must
    be side-effect free apart from the tools they call, must record their
    activity in the state timeline, and must never raise past the graph
    boundary without recording an :class:`InvestigationError`
    (``Agent System Design`` section 13).
    """

    step: InvestigationStep

    async def __call__(self, state: InvestigationState) -> dict[str, object]:
        """Run the node and return the state fields it updates."""
        ...

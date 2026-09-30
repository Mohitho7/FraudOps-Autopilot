"""Recommendation capability (Member 2).

Purpose
-------
Produces an **advisory** operational recommendation from the collected
evidence (``Agent System Design`` section 5.5)::

    ALLOW            No immediate fraud action recommended
    MONITOR          Continue observation without urgent review
    HOLD_FOR_REVIEW  Reviewer should make the next decision
    ESCALATE         Send the case to a higher-priority fraud workflow

Safety
------
Recommendations are never executed. Irreversible financial actions stay under
human control (``Agent System Design`` sections 5.5 and 9), and the reviewer
can always override the recommendation
(``Agent System Design`` section 16, definition of done).

Status
------
Interface only in Batch 1.
"""

from __future__ import annotations

from typing import Protocol

from app.agents.evidence.builder import EvidencePack
from app.agents.graph.state import InvestigationState
from app.schemas.investigation_result import Recommendation

__all__ = ["RecommendationAgent", "RecommendationAgentStub"]


class RecommendationAgent(Protocol):
    """Contract for the recommendation capability."""

    async def recommend(
        self,
        state: InvestigationState,
        evidence: EvidencePack,
    ) -> Recommendation:
        """Recommend the next operational action.

        Args:
            state: Current investigation state, including Member 1's severity
                and the capability findings.
            evidence: The evidence pack the recommendation must cite.

        Returns:
            Advisory recommendation with confidence, rationale and the evidence
            references it relies on.

        Raises:
            InvestigationToolError: When no reliable recommendation can be
                produced; the caller must then hand off to a human
                (``Agent System Design`` section 10).
        """
        ...


class RecommendationAgentStub:
    """Batch 1 stub: recommendation logic lands in a later batch."""

    async def recommend(
        self,
        state: InvestigationState,
        evidence: EvidencePack,
    ) -> Recommendation:
        """Not implemented in Batch 1."""

        raise NotImplementedError(
            "The recommendation agent is implemented in Batch 2. Batch 1 only "
            "defines the contract and the recommendation shape."
        )

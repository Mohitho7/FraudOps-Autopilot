"""Evidence builder (Member 2).

Purpose
-------
Converts the structured investigation results into an evidence pack. Every
narrative statement must reference a stored fact or a deterministic calculation
(``Agent System Design`` section 5.4), for example::

    - Amount anomaly: 434.8x customer average
    - Merchant anomaly: above merchant P99
    - Relationship: device shared by 2 flagged accounts

Explainability
--------------
Evidence items are tagged with :class:`~app.schemas.investigation.ClaimKind`
so the console can visually separate hard evidence from agent interpretation
(``Agent System Design`` section 11, ``Frontend Specification`` section 5).

LLM availability
----------------
``Agent System Design`` section 16 requires the system to keep working when the
LLM is unavailable. ``narrative_source`` records whether a summary was produced
deterministically or with model assistance
(:class:`~app.agents.evidence.builder.NarrativeSource`).

Status
------
Interface only in Batch 1.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.agents.graph.state import InvestigationState
from app.agents.tools.types import AwareDateTime
from app.schemas.investigation_result import EvidenceItem, InvestigationFinding

__all__ = [
    "EvidenceBuilder",
    "EvidenceBuilderStub",
    "EvidencePack",
    "NarrativeSource",
]


class NarrativeSource(StrEnum):
    """How the human-readable summary of an evidence pack was produced."""

    DETERMINISTIC = "DETERMINISTIC"
    """Templated summary built in Python; used when the LLM is unavailable."""

    LLM_ASSISTED = "LLM_ASSISTED"
    """Summary narrated by the model, constrained to the supplied evidence."""


class EvidencePack(BaseModel):
    """Structured evidence produced by the evidence builder."""

    model_config = ConfigDict(extra="forbid")

    evidence: list[EvidenceItem] = Field(
        default_factory=list,
        description="Evidence items, each with a source reference.",
    )
    findings: list[InvestigationFinding] = Field(
        default_factory=list, description="Findings the evidence supports."
    )
    summary: str = Field(
        min_length=1,
        max_length=8000,
        description=(
            "Reviewer-facing summary. When ``narrative_source`` is "
            "DETERMINISTIC this is a template filled from stored facts only."
        ),
    )
    narrative_source: NarrativeSource = Field(
        description="Whether the summary was templated or model-narrated."
    )
    missing_evidence: list[str] = Field(
        default_factory=list,
        description=(
            "Material evidence that could not be obtained. Non-empty values push "
            "the case towards human review (Agent System Design section 10)."
        ),
    )
    generated_at: AwareDateTime = Field(
        description="Timezone-aware time the pack was generated."
    )


class EvidenceBuilder(Protocol):
    """Contract for the evidence builder capability."""

    async def build(self, state: InvestigationState) -> EvidencePack:
        """Assemble the evidence pack for ``state``.

        Args:
            state: Current investigation state holding Member 1's facts, tool
                results and capability findings.

        Returns:
            Evidence pack whose items all carry a source reference and a
            claim kind.

        Raises:
            InvestigationToolError: When the pack cannot be assembled or
                persisted.
        """
        ...


class EvidenceBuilderStub:
    """Batch 1 stub: evidence assembly lands in a later batch."""

    async def build(self, state: InvestigationState) -> EvidencePack:
        """Not implemented in Batch 1."""

        raise NotImplementedError(
            "Evidence building is implemented in Batch 2. Batch 1 only defines "
            "the contract and the evidence pack shape."
        )

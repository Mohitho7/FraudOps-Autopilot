"""Shared result type for the three investigation capabilities (Member 2).

Behavioral, business-context and relationship analysis all answer the same
question in the same shape: *what did we observe, how confident are we, and is
that enough to keep going?* The orchestrator uses ``sufficient_evidence`` to
decide between running another check and building the evidence pack
(``Agent System Design`` section 8).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.investigation_result import InvestigationFinding

__all__ = ["AnalysisOutcome"]


class AnalysisOutcome(BaseModel):
    """Result of a single investigation capability."""

    model_config = ConfigDict(extra="forbid")

    findings: list[InvestigationFinding] = Field(
        default_factory=list,
        description="Structured findings, each citing its evidence references.",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Capability confidence, 0.0-1.0. ``None`` when undetermined.",
    )
    sufficient_evidence: bool = Field(
        default=False,
        description=(
            "True when the capability has enough deterministic material to "
            "support a conclusion. False means the orchestrator should gather "
            "more context or hand off to a human."
        ),
    )
    limitations: list[str] = Field(
        default_factory=list,
        description=(
            "Explicit statement of what could not be determined, e.g. "
            "'no merchant profile available'. Contradictory or missing evidence "
            "triggers human review (Agent System Design section 10)."
        ),
    )

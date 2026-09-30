"""Member 2 -> Member 3 contract: the investigation result.

This module defines what the reviewer console (Member 3) consumes. The
frontend must not recompute fraud logic; it renders backend truth.

Source of truth for the shape below:

* ``Four-Member Work Division`` section 6 -- "Agent Result" interface
  (investigation status, findings, evidence, related entities,
  recommendation, confidence).
* ``Frontend Specification`` section 5 -- Case Detail experience.
* ``Agent System Design`` sections 6, 11 and 12 -- state, explainability
  contract and audit trail.

BOUNDARY
--------
The response separates hard facts from agent interpretation through
:class:`~app.schemas.investigation.ClaimKind`. ``OBSERVED_FACT``,
``CALCULATED_METRIC`` and ``RULE_RESULT`` items come from deterministic code
and stored records; only ``AGENT_INTERPRETATION`` and ``RECOMMENDATION`` items
are model-generated. The timeline contains structured events only -- never
chain-of-thought (see ``Four-Member Work Division`` section 4, UX principle).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from app.schemas.investigation import (
    AnalysisCategory,
    ClaimKind,
    EntityType,
    EvidenceSourceType,
    InvestigationStatus,
    InvestigationStep,
    RecommendationAction,
    RelationType,
    RuleResultRecord,
    Severity,
)

__all__ = [
    "EvidenceItem",
    "HumanDecision",
    "HumanDecisionAction",
    "InvestigationActivity",
    "InvestigationError",
    "InvestigationFinding",
    "InvestigationResponse",
    "RelatedEntity",
    "Recommendation",
]


class HumanDecisionAction(StrEnum):
    """Reviewer outcomes recorded against a case.

    Mirrors the reviewer actions in ``Frontend Specification`` section 3
    (Clear / Confirm Fraud / Escalate / Mark Reviewed) and the
    ``review_actions`` table in ``Database Design`` section 3.
    """

    CLEAR = "CLEAR"
    CONFIRM_FRAUD = "CONFIRM_FRAUD"
    ESCALATE = "ESCALATE"
    MARK_REVIEWED = "MARK_REVIEWED"


class EvidenceItem(BaseModel):
    """One structured evidence record.

    Maps to the ``evidence`` table (``Database Design`` section 3):
    ``source_type``, ``source_ref``, ``title``, ``details_json``.
    """

    model_config = ConfigDict(extra="forbid")

    evidence_id: UUID = Field(description="Stable identifier of this evidence item.")
    source_type: EvidenceSourceType = Field(
        description="Which kind of system record the evidence came from."
    )
    source_ref: str = Field(
        min_length=1,
        max_length=500,
        description=(
            "Pointer back to the source record, e.g. 'transaction:<uuid>' or "
            "'rule:unusual_amount'. Required so every statement is traceable."
        ),
    )
    claim_kind: ClaimKind = Field(
        description=(
            "Explainability category. Facts, calculated metrics and rule results "
            "are deterministic; interpretations and recommendations come from the model."
        )
    )
    title: str = Field(
        min_length=1,
        max_length=300,
        description="Short evidence headline shown in the UI.",
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured detail payload backing the claim.",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence for this specific item, 0.0-1.0. Optional.",
    )
    observed_at: datetime | None = Field(
        default=None,
        description="Time the underlying fact was observed or calculated.",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def reference(self) -> str:
        """Evidence reference used by findings and recommendations."""

        return f"evidence:{self.evidence_id}"

    @model_validator(mode="before")
    @classmethod
    def _drop_computed_reference(cls, data: object) -> object:
        """Ignore ``reference`` when it comes from a serialised payload.

        ``reference`` is a computed field, so Pydantic emits it in
        ``model_dump`` but would otherwise reject it on validation. Dropping it
        on input keeps ``model_dump``/``model_validate`` round-trippable for
        Member 4's ``evidence`` table and for LangGraph checkpoints, while
        ``extra="forbid"`` still rejects genuinely unknown keys.
        """

        if isinstance(data, dict):
            data.pop("reference", None)
        return data


class InvestigationFinding(BaseModel):
    """A structured observation produced by one investigation capability."""

    model_config = ConfigDict(extra="forbid")

    finding_id: UUID = Field(description="Stable identifier of this finding.")
    category: AnalysisCategory = Field(
        description="Which investigation capability produced the finding."
    )
    title: str = Field(
        min_length=1,
        max_length=300,
        description="Short finding headline, e.g. 'Amount is 434.8x customer median'.",
    )
    summary: str = Field(
        min_length=1,
        max_length=4000,
        description="Explanation of the finding in reviewer-facing language.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in this finding, 0.0-1.0.",
    )
    severity_impact: Severity | None = Field(
        default=None,
        description="Severity the finding argues for, if any. Advisory only.",
    )
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Deterministic metrics behind the finding, e.g. "
            "{'amount_multiple_of_customer_average': 434.8}. Numbers must come "
            "from Python or the database, never from the language model."
        ),
    )
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="References to the evidence items supporting this finding.",
    )


class RelatedEntity(BaseModel):
    """An entity linked to the investigation.

    Maps to ``case_entities`` (``Database Design`` section 3):
    ``entity_type``, ``entity_ref``, ``relation_type``.
    """

    model_config = ConfigDict(extra="forbid")

    entity_type: EntityType = Field(description="Kind of linked entity.")
    entity_ref: str = Field(
        min_length=1,
        max_length=500,
        description="Identifier of the linked entity as stored in the database.",
    )
    relation_type: RelationType = Field(description="Why the entity is linked.")
    label: str | None = Field(
        default=None,
        max_length=300,
        description="Display label for the frontend.",
    )
    risk_note: str | None = Field(
        default=None,
        max_length=1000,
        description="Short note explaining the relevance of the link.",
    )
    related_case_id: UUID | None = Field(
        default=None,
        description="Case the linked entity was previously involved in, if any.",
    )


class Recommendation(BaseModel):
    """Advisory recommendation produced by the Recommendation Agent.

    ``action`` values are fixed by ``Agent System Design`` section 5.5. A
    recommendation is never an executed financial action
    (``Agent System Design`` section 9).
    """

    model_config = ConfigDict(extra="forbid")

    action: RecommendationAction = Field(
        description="Advisory action: ALLOW, MONITOR, HOLD_FOR_REVIEW or ESCALATE."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the recommendation, 0.0-1.0.",
    )
    rationale: str = Field(
        min_length=1,
        max_length=4000,
        description="Why this action is recommended, referencing stored facts.",
    )
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="Evidence references supporting the recommendation.",
    )
    requires_human_review: bool = Field(
        default=False,
        description="True when policy requires a reviewer decision before acting.",
    )


class HumanDecision(BaseModel):
    """Reviewer outcome recorded against the case.

    Maps to ``review_actions`` (``Database Design`` section 3):
    ``case_id``, ``reviewer_id``, ``action``, ``note``, ``created_at``.
    """

    model_config = ConfigDict(extra="forbid")

    action: HumanDecisionAction = Field(description="Reviewer action that was taken.")
    reviewer_id: str | None = Field(
        default=None,
        max_length=200,
        description="Reviewer identity as recorded by the audit layer.",
    )
    note: str | None = Field(
        default=None,
        max_length=4000,
        description="Free-text reviewer note.",
    )
    decided_at: datetime = Field(description="Timezone-aware decision time.")


class InvestigationActivity(BaseModel):
    """One entry of the agent activity timeline.

    This is a structured audit event (``Agent System Design`` section 12), not
    a model reasoning trace. ``summary`` must describe *what* was done and must
    never contain hidden chain-of-thought
    (``Four-Member Work Division`` section 4).
    """

    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(
        ge=0,
        description="Monotonic ordering of the event within the investigation.",
    )
    step: InvestigationStep = Field(description="Workflow step the event belongs to.")
    status: str = Field(
        min_length=1,
        max_length=30,
        description="Event status, e.g. 'COMPLETED', 'FAILED', 'SKIPPED'.",
    )
    summary: str = Field(
        min_length=1,
        max_length=1000,
        description="Short factual description of what happened.",
    )
    tool_name: str | None = Field(
        default=None,
        max_length=100,
        description="Approved tool that was called, when applicable.",
    )
    occurred_at: datetime = Field(description="Timezone-aware event time.")
    error: str | None = Field(
        default=None,
        max_length=2000,
        description="Error detail when the event failed.",
    )


class InvestigationError(BaseModel):
    """Failure detail recorded when an investigation cannot continue."""

    model_config = ConfigDict(extra="forbid")

    step: InvestigationStep | None = Field(
        default=None,
        description="Step that failed, when known.",
    )
    error_type: str = Field(
        min_length=1,
        max_length=200,
        description="Exception or error category name.",
    )
    message: str = Field(
        min_length=1,
        max_length=2000,
        description="Failure message safe to display to a reviewer.",
    )
    retryable: bool = Field(
        default=False,
        description="True when the documented retry policy allows another attempt.",
    )


class InvestigationResponse(BaseModel):
    """Full investigation payload consumed by the reviewer console.

The console renders this object; it must never derive risk or fraud logic
    locally (``Four-Member Work Division`` section 4, acceptance checks).

    Computed fields
    ---------------
    ``EvidenceItem.reference`` and ``InvestigationResponse.requires_human_review``
    are ``computed_field``s: Pydantic emits them in ``model_dump`` but does not
    accept them as input. Both models therefore drop these keys in a ``before``
    validator so that ``model_dump`` -> ``model_validate`` round-trips cleanly
    (Member 4 storage, LangGraph checkpoints). Because they are always re-derived,
    a value supplied by a stored payload is ignored rather than trusted.
    ``extra="forbid"`` still rejects genuinely unknown keys.
    """

    model_config = ConfigDict(extra="forbid")

    investigation_id: UUID = Field(description="Investigation instance identifier.")
    transaction_id: UUID = Field(description="Transaction under investigation.")
    case_id: UUID | None = Field(
        default=None, description="Fraud case id, when one exists."
    )
    status: InvestigationStatus = Field(description="Investigation lifecycle status.")
    risk_score: int = Field(
        ge=0,
        le=100,
        description="Risk score as computed by Member 1. Echoed, never recomputed.",
    )
    severity: Severity = Field(description="Severity as computed by Member 1.")
    triggered_rules: list[RuleResultRecord] = Field(
        default_factory=list,
        description="Rule results that fired, echoed for case explanation.",
    )
    findings: list[InvestigationFinding] = Field(
        default_factory=list,
        description="Findings from behavioral, business and relationship analysis.",
    )
    evidence: list[EvidenceItem] = Field(
        default_factory=list,
        description="Structured evidence pack backing the findings.",
    )
    related_entities: list[RelatedEntity] = Field(
        default_factory=list,
        description="Linked customers, devices, IPs, merchants and transactions.",
    )
    recommendation: Recommendation | None = Field(
        default=None,
        description="Advisory recommendation, when the investigation completed.",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Overall investigation confidence, 0.0-1.0.",
    )
    activity_timeline: list[InvestigationActivity] = Field(
        default_factory=list,
        description="Ordered agent activity events for the case timeline.",
    )
    human_decision: HumanDecision | None = Field(
        default=None,
        description="Reviewer outcome, populated after human handoff.",
    )
    error: InvestigationError | None = Field(
        default=None, description="Failure detail when status is FAILED."
    )
    started_at: datetime = Field(description="Investigation start time.")
    updated_at: datetime = Field(description="Last state update time.")
    completed_at: datetime | None = Field(
        default=None, description="Investigation completion time, when finished."
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def requires_human_review(self) -> bool:
        """True when the payload must wait for a reviewer decision.

        Derived here so the console does not re-implement the handoff policy
        from ``Agent System Design`` section 10.
        """

        if self.human_decision is not None:
            return False
        if self.status is InvestigationStatus.WAITING_HUMAN:
            return True
        if (
            self.recommendation is not None
            and self.recommendation.requires_human_review
        ):
            return True
        return self.status is InvestigationStatus.FAILED

    @model_validator(mode="before")
    @classmethod
    def _drop_computed_requires_human_review(cls, data: object) -> object:
        """Ignore the computed ``requires_human_review`` key on input.

        The field is always derived by the property above, so a value supplied
        by a persisted payload or a checkpoint must never override it. Dropping
        it keeps ``model_dump``/``model_validate`` round-trippable for Member 4's
        stored response payload.
        """

        if isinstance(data, dict):
            data.pop("requires_human_review", None)
        return data

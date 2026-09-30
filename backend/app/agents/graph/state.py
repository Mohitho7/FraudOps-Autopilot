"""Investigation state for the LangGraph investigation workflow (Member 2).

Source of truth: ``Agent System Design`` section 6 ("Agent State Model") plus
section 12 ("Audit Trail") and section 13 ("Failure and Retry Behavior").

Design
------
``InvestigationState`` is a Pydantic model so that every value crossing a
workflow boundary is validated and serialisable. LangGraph accepts a Pydantic
model as its state schema, and :meth:`InvestigationState.to_dict` /
:meth:`InvestigationState.from_dict` provide the plain-dict representation used
for checkpoints and for Member 4's ``investigations.state_json`` column.

BOUNDARY
--------
The state stores only:

* facts supplied by Member 1 (``risk_score``, ``severity``, ``triggered_rules``,
  ``context_signals``, ``transaction_context``),
* facts loaded through approved tools,
* structured findings, evidence and an advisory recommendation.

It never contains an LLM-authored number: ``metrics`` and ``details`` values
must be produced by Python or the database (``Agent System Design`` section 9).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agents.tools.types import CustomerContext, MerchantContext
from app.schemas.investigation import (
    ContextSignal,
    InvestigationRequest,
    InvestigationStatus,
    InvestigationStep,
    InvestigationTrigger,
    RuleResultRecord,
    Severity,
    TransactionContext,
)
from app.schemas.investigation_result import (
    EvidenceItem,
    HumanDecision,
    InvestigationActivity,
    InvestigationError,
    InvestigationFinding,
    InvestigationResponse,
    Recommendation,
    RelatedEntity,
)

__all__ = [
    "InvestigationState",
    "STATE_SCHEMA_VERSION",
]

STATE_SCHEMA_VERSION = "1.0"


def _utcnow() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(timezone.utc)


class InvestigationState(BaseModel):
    """Stateful record of one investigation.

    One instance corresponds to one investigation of one transaction. The
    state is checkpointed after every step so that a crashed or failed
    investigation can be resumed and fully replayed for audit
    (``Agent System Design`` sections 6 and 13).
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str = Field(
        default=STATE_SCHEMA_VERSION,
        description="Version of this state contract, for checkpoint compatibility.",
    )
    investigation_id: UUID = Field(
        default_factory=uuid4, description="Unique investigation instance identifier."
    )
    trigger: InvestigationTrigger = Field(
        default=InvestigationTrigger.RISK_THRESHOLD,
        description="Why the investigation was started.",
    )
    status: InvestigationStatus = Field(
        default=InvestigationStatus.RUNNING, description="Investigation lifecycle status."
    )
    transaction_id: UUID = Field(description="Transaction under investigation.")
    case_id: UUID | None = Field(
        default=None, description="Fraud case id, when one exists."
    )
    customer_id: UUID | None = Field(
        default=None, description="Customer id, when known."
    )
    merchant_id: UUID | None = Field(
        default=None, description="Merchant id, when known."
    )
    risk_score: int = Field(
        ge=0, le=100, description="Risk score supplied by Member 1's risk engine."
    )
    severity: Severity = Field(
        description="Severity supplied by Member 1's risk engine."
    )
    triggered_rules: list[RuleResultRecord] = Field(
        default_factory=list,
        description="Rule results supplied by Member 1, echoed for evidence citation.",
    )
    context_signals: list[ContextSignal] = Field(
        default_factory=list,
        description=(
            "Deterministic context signals from Member 1 ('risk_signals' in the "
            "Agent System Design state table)."
        ),
    )
    transaction_context: TransactionContext | None = Field(
        default=None, description="Transaction snapshot, when supplied by Member 1."
    )
    customer_context: CustomerContext | None = Field(
        default=None, description="Customer context loaded through approved tools."
    )
    merchant_context: MerchantContext | None = Field(
        default=None, description="Merchant context loaded through approved tools."
    )
    behavioral_findings: list[InvestigationFinding] = Field(
        default_factory=list, description="Findings from behavioral analysis."
    )
    business_findings: list[InvestigationFinding] = Field(
        default_factory=list, description="Findings from business context analysis."
    )
    relationship_findings: list[InvestigationFinding] = Field(
        default_factory=list, description="Findings from relationship analysis."
    )
    related_entities: list[RelatedEntity] = Field(
        default_factory=list, description="Linked entities discovered by tools."
    )
    evidence: list[EvidenceItem] = Field(
        default_factory=list, description="Structured evidence collected so far."
    )
    recommendation: Recommendation | None = Field(
        default=None, description="Advisory recommendation, when available."
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Overall investigation confidence, 0.0-1.0.",
    )
    current_step: InvestigationStep = Field(
        default=InvestigationStep.LOAD_STATE,
        description="Current workflow node, used to resume after a failure.",
    )
    completed_steps: list[InvestigationStep] = Field(
        default_factory=list,
        description="Steps already executed, so retries are idempotent.",
    )
    activity: list[InvestigationActivity] = Field(
        default_factory=list,
        description=(
            "Append-only agent activity timeline exposed to the console as "
            "structured events only (no chain-of-thought)."
        ),
    )
    human_decision: HumanDecision | None = Field(
        default=None, description="Reviewer outcome once human handoff happened."
    )
    error: InvestigationError | None = Field(
        default=None, description="Failure detail when the investigation failed."
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Bounded retry counter for the current failing step.",
    )
    requested_by: str | None = Field(
        default=None, description="Reviewer or service that requested the investigation."
    )
    started_at: datetime = Field(default_factory=_utcnow, description="Start time.")
    updated_at: datetime = Field(default_factory=_utcnow, description="Last update time.")
    completed_at: datetime | None = Field(
        default=None, description="Completion time, when finished."
    )
    last_checkpoint_at: datetime | None = Field(
        default=None,
        description=(
            "Last checkpoint time. Investigation resumes from this point after a "
            "crash (Agent System Design section 13)."
        ),
    )

    @field_validator(
        "started_at",
        "updated_at",
        "completed_at",
        "last_checkpoint_at",
        mode="after",
    )
    @classmethod
    def _require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("investigation timestamps must be timezone aware")
        return value

    @classmethod
    def from_request(
        cls,
        request: InvestigationRequest,
        *,
        investigation_id: UUID | None = None,
        now: datetime | None = None,
    ) -> Self:
        """Create the initial state from a Member 1 investigation request.

        The initial state performs no analysis: it only carries Member 1's facts
        and positions the workflow at ``LOAD_STATE``. When
        ``investigation_id`` is omitted a new UUID is generated; callers that
        retry a failed investigation must pass the previous id so the audit
        trail continues on the same instance.
        """

        timestamp = now or _utcnow()
        context = request.transaction_context
        identifiers: dict[str, Any] = {
            "trigger": request.trigger,
            "transaction_id": request.transaction_id,
            "case_id": request.case_id,
            "customer_id": request.customer_id
            or (context.customer_id if context is not None else None),
            "merchant_id": request.merchant_id
            or (context.merchant_id if context is not None else None),
            "risk_score": request.risk_score,
            "severity": request.severity,
            "triggered_rules": list(request.triggered_rules),
            "context_signals": list(request.context_signals),
            "transaction_context": request.transaction_context,
            "requested_by": request.requested_by,
            "current_step": InvestigationStep.LOAD_STATE,
            "started_at": timestamp,
            "updated_at": timestamp,
        }
        if investigation_id is not None:
            identifiers["investigation_id"] = investigation_id
        return cls(**identifiers)

    def mark_step_completed(self, step: InvestigationStep) -> None:
        """Record ``step`` as completed, keeping the list free of duplicates."""

        if step not in self.completed_steps:
            self.completed_steps.append(step)
        self.updated_at = _utcnow()

    def record_activity(
        self,
        *,
        step: InvestigationStep,
        status: str,
        summary: str,
        tool_name: str | None = None,
        error: str | None = None,
        occurred_at: datetime | None = None,
    ) -> InvestigationActivity:
        """Append a structured audit event to the activity timeline.

        Every tool call made by the workflow must be logged here with its input
        identifiers and output references (``System Design`` addendum, "Agent
        Tooling").
        """

        event = InvestigationActivity(
            sequence=len(self.activity),
            step=step,
            status=status,
            summary=summary,
            tool_name=tool_name,
            occurred_at=occurred_at or _utcnow(),
            error=error,
        )
        self.activity.append(event)
        self.updated_at = event.occurred_at
        return event

    def all_findings(self) -> list[InvestigationFinding]:
        """Return every finding in a stable order for the evidence builder."""

        return [
            *self.behavioral_findings,
            *self.business_findings,
            *self.relationship_findings,
        ]

    def to_dict(self) -> dict[str, Any]:
        """Plain-dict representation for LangGraph checkpoints and persistence."""

        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Self:
        """Rebuild a state from :meth:`to_dict` output or a database JSON column."""

        return cls.model_validate(payload)

    def to_response(self) -> InvestigationResponse:
        """Project the state into the Member 2 -> Member 3 payload."""

        return InvestigationResponse(
            investigation_id=self.investigation_id,
            transaction_id=self.transaction_id,
            case_id=self.case_id,
            status=self.status,
            risk_score=self.risk_score,
            severity=self.severity,
            triggered_rules=list(self.triggered_rules),
            findings=self.all_findings(),
            evidence=list(self.evidence),
            related_entities=list(self.related_entities),
            recommendation=self.recommendation,
            confidence=self.confidence,
            activity_timeline=list(self.activity),
            human_decision=self.human_decision,
            error=self.error,
            started_at=self.started_at,
            updated_at=self.updated_at,
            completed_at=self.completed_at,
        )

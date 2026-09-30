"""Member 1 -> Member 2 contract: the investigation request.

This module is the only way the deterministic fraud pipeline hands work to the
agentic investigation layer. It carries the facts that Member 1's rule engine
and risk engine already computed, so that the agentic layer never has to
recalculate them.

Source of truth for the field names below:

* ``Backend Specification`` section 6 -- Rule Result Contract.
* ``Database Design & Data Dictionary`` section 4 -- ``transactions`` columns.
* ``Four-Member Work Division`` section 6 -- "Fraud Result" interface
  (transaction id, risk score, triggered rules, structured evidence, context
  signals).

BOUNDARY
--------
Member 2 does **not** calculate, adjust, re-weight or re-derive ``risk_score``
or ``severity``. Member 1's rule engine and risk engine remain the single
source of truth for deterministic fraud detection. Everything in this module is
transport, typing and validation only.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = [
    "AnalysisCategory",
    "ClaimKind",
    "ContextSignal",
    "EntityType",
    "EvidenceSourceType",
    "InvestigationRequest",
    "InvestigationStatus",
    "InvestigationStep",
    "InvestigationTrigger",
    "RecommendationAction",
    "RelationType",
    "RuleResultRecord",
    "Severity",
    "TransactionContext",
    "TransactionStatus",
]


class Severity(StrEnum):
    """Risk severity bands.

    Mirrors ``fraud_cases.severity`` in the Database Design document
    (section 7) and the ``rule_results.severity`` values in the Backend
    Specification (section 6).
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TransactionStatus(StrEnum):
    """``transactions.status`` values (Database Design, section 4)."""

    NORMAL = "NORMAL"
    FLAGGED = "FLAGGED"
    REVIEWED = "REVIEWED"
    CLEARED = "CLEARED"
    CONFIRMED_FRAUD = "CONFIRMED_FRAUD"


class InvestigationStatus(StrEnum):
    """Investigation lifecycle states (Agent System Design, section 6)."""

    RUNNING = "RUNNING"
    WAITING_HUMAN = "WAITING_HUMAN"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class InvestigationTrigger(StrEnum):
    """Why an investigation was started (Agent System Design, section 4)."""

    RISK_THRESHOLD = "RISK_THRESHOLD"
    REVIEWER_REQUEST = "REVIEWER_REQUEST"


class InvestigationStep(StrEnum):
    """Workflow step vocabulary for the LangGraph investigation graph.

    The values follow the node names in ``Agent System Design`` section 8
    (``START -> Load State -> Check Evidence -> ... -> Build Evidence ->
    Recommendation -> Human Handoff -> END``) plus the three analysis
    capabilities from section 5.
    """

    LOAD_STATE = "LOAD_STATE"
    CHECK_EVIDENCE = "CHECK_EVIDENCE"
    SELECT_NEXT_CHECK = "SELECT_NEXT_CHECK"
    CALL_TOOL = "CALL_TOOL"
    VALIDATE_OUTPUT = "VALIDATE_OUTPUT"
    PERSIST_FINDING = "PERSIST_FINDING"
    BEHAVIORAL_ANALYSIS = "BEHAVIORAL_ANALYSIS"
    BUSINESS_CONTEXT_ANALYSIS = "BUSINESS_CONTEXT_ANALYSIS"
    RELATIONSHIP_ANALYSIS = "RELATIONSHIP_ANALYSIS"
    EVIDENCE_BUILD = "EVIDENCE_BUILD"
    RECOMMENDATION = "RECOMMENDATION"
    HUMAN_HANDOFF = "HUMAN_HANDOFF"
    COMPLETE = "COMPLETE"
    FAILURE = "FAILURE"


class AnalysisCategory(StrEnum):
    """Investigation capability that produced a finding.

    Matches the three analysis branches in the agent architecture diagram
    (System Design addendum / Agent System Design section 3).
    """

    BEHAVIORAL = "BEHAVIORAL"
    BUSINESS = "BUSINESS"
    RELATIONSHIP = "RELATIONSHIP"
    EVIDENCE = "EVIDENCE"
    RECOMMENDATION = "RECOMMENDATION"


class ClaimKind(StrEnum):
    """Explainability contract (Agent System Design, section 11).

    Every statement exposed to the reviewer console must declare which of
    these categories it belongs to, so that hard evidence and agent
    interpretation stay visually and structurally distinguishable.
    """

    OBSERVED_FACT = "OBSERVED_FACT"
    CALCULATED_METRIC = "CALCULATED_METRIC"
    RULE_RESULT = "RULE_RESULT"
    AGENT_INTERPRETATION = "AGENT_INTERPRETATION"
    RECOMMENDATION = "RECOMMENDATION"


class EvidenceSourceType(StrEnum):
    """``evidence.source_type`` values (Database Design, section 3)."""

    TRANSACTION = "TRANSACTION"
    CUSTOMER = "CUSTOMER"
    MERCHANT = "MERCHANT"
    RULE_RESULT = "RULE_RESULT"
    RELATIONSHIP = "RELATIONSHIP"
    PRIOR_CASE = "PRIOR_CASE"
    CALCULATION = "CALCULATION"


class EntityType(StrEnum):
    """``case_entities.entity_type`` values (Database Design, section 2/3)."""

    CUSTOMER = "CUSTOMER"
    ACCOUNT = "ACCOUNT"
    DEVICE = "DEVICE"
    IP_ADDRESS = "IP_ADDRESS"
    MERCHANT = "MERCHANT"
    TRANSACTION = "TRANSACTION"


class RelationType(StrEnum):
    """``case_entities.relation_type`` values.

    Derived from the relationship analysis list in ``Agent System Design``
    section 5.3 (shared device, shared IP, shared account, common merchant,
    location overlap, temporal clustering).
    """

    SHARED_DEVICE = "SHARED_DEVICE"
    SHARED_IP_ADDRESS = "SHARED_IP_ADDRESS"
    SHARED_ACCOUNT = "SHARED_ACCOUNT"
    SHARED_MERCHANT = "SHARED_MERCHANT"
    LOCATION_OVERLAP = "LOCATION_OVERLAP"
    TEMPORAL_CLUSTER = "TEMPORAL_CLUSTER"
    LINKED_TRANSACTION = "LINKED_TRANSACTION"


class RecommendationAction(StrEnum):
    """Advisory actions produced by the Recommendation Agent.

    Values are fixed by ``Agent System Design`` section 5.5. These are
    recommendations only; irreversible financial actions stay human-controlled
    (``Agent System Design`` section 9).
    """

    ALLOW = "ALLOW"
    MONITOR = "MONITOR"
    HOLD_FOR_REVIEW = "HOLD_FOR_REVIEW"
    ESCALATE = "ESCALATE"


class RuleResultRecord(BaseModel):
    """A single rule evaluation as produced by Member 1.

    Mirrors the Rule Result Contract in ``Backend Specification`` section 6 and
    the ``rule_results`` table in ``Database Design`` section 3.

    Member 2 treats this record as an immutable, already-computed fact. The
    agentic layer may cite it in evidence but must never recompute or modify
    it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str = Field(
        min_length=1,
        max_length=100,
        description="Rule code as registered in the rules table, e.g. 'unusual_amount'.",
    )
    rule_name: str = Field(
        min_length=1,
        max_length=200,
        description="Human readable rule name as registered by Member 1.",
    )
    triggered: bool = Field(
        description="True when Member 1's rule engine flagged this transaction.",
    )
    score: int = Field(
        ge=0,
        le=100,
        description="Rule contribution score computed by Member 1 (0-100).",
    )
    severity: Severity = Field(
        description="Severity assigned to this rule result by Member 1.",
    )
    reason: str = Field(
        min_length=1,
        max_length=2000,
        description="Deterministic explanation produced by the rule.",
    )
    evidence: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Structured evidence values used by the rule, e.g. "
            "{'amount': 1000000, 'customer_average': 80500, 'merchant_p95': 450000}."
        ),
    )

    @property
    def evidence_reference(self) -> str:
        """Stable evidence pointer for this rule result (``rule_result:<rule_id>``)."""

        return f"rule_result:{self.rule_id}"


class ContextSignal(BaseModel):
    """A deterministic context signal produced by Member 1's context enricher.

    Examples: a customer amount ratio, a merchant percentile band, a recent
    change of behaviour, a prior review outcome. Signals are facts with a
    source; the agentic layer may interpret them but may not invent them.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    signal_type: str = Field(
        min_length=1,
        max_length=100,
        description="Machine readable signal code, e.g. 'customer_amount_ratio'.",
    )
    description: str = Field(
        min_length=1,
        max_length=1000,
        description="Short human readable explanation of the signal.",
    )
    value: float | None = Field(
        default=None,
        description="Numeric value of the signal when the signal is quantitative.",
    )
    severity: Severity | None = Field(
        default=None,
        description="Severity contributed by this signal, if any.",
    )
    source: str = Field(
        min_length=1,
        max_length=200,
        description="Producer of the signal, e.g. 'context_enricher:merchant_profile'.",
    )
    observed_at: datetime | None = Field(
        default=None,
        description="Time the signal was computed. Must be timezone aware.",
    )

    @field_validator("observed_at")
    @classmethod
    def _require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("observed_at must be timezone aware (TIMESTAMPTZ)")
        return value


class TransactionContext(BaseModel):
    """Snapshot of the transaction under investigation.

    Field names follow the ``transactions`` table (Database Design, section 4).
    This snapshot is optional: the investigation layer can also load the same
    facts through :mod:`app.agents.tools.transaction_tools`. Member 2 never
    modifies the transaction.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_id: UUID = Field(description="Primary key of the transaction.")
    customer_id: UUID = Field(description="Customer making the transaction.")
    merchant_id: UUID = Field(description="Merchant receiving the transaction.")
    amount: Decimal = Field(gt=0, description="Transaction amount, NUMERIC(18,2).")
    currency: str = Field(
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
        description="ISO-style currency code, VARCHAR(3).",
    )
    timestamp: datetime = Field(
        description="Transaction event time, TIMESTAMPTZ. Must be timezone aware."
    )
    latitude: float | None = Field(
        default=None,
        ge=-90,
        le=90,
        description="Transaction latitude, NUMERIC(9,6).",
    )
    longitude: float | None = Field(
        default=None,
        ge=-180,
        le=180,
        description="Transaction longitude, NUMERIC(9,6).",
    )
    country: str | None = Field(
        default=None,
        max_length=100,
        description="Transaction country, VARCHAR(100).",
    )
    merchant_label: str | None = Field(
        default=None,
        max_length=200,
        description="Display-safe merchant name, VARCHAR(200).",
    )
    ip_address: str | None = Field(
        default=None,
        max_length=45,
        description="Source IP where available.",
    )
    device_id: str | None = Field(
        default=None,
        max_length=200,
        description="Device reference where available.",
    )
    status: TransactionStatus = Field(
        default=TransactionStatus.FLAGGED,
        description="Transaction status as persisted by Member 1.",
    )

    @field_validator("timestamp")
    @classmethod
    def _require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must be timezone aware (TIMESTAMPTZ)")
        return value

    @model_validator(mode="after")
    def _coordinates_are_paired(self) -> Self:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class InvestigationRequest(BaseModel):
    """Member 1 -> Member 2 payload that starts an investigation.

    The deterministic pipeline calls this contract after the risk engine has
    classified a transaction. The agentic layer accepts the facts, decides
    which analyses to run and produces an evidence pack plus a recommendation.

    Example payload::

        {
            "transaction_id": "0f3d1c1e-6b6a-4f4b-9f2a-1d2c3b4a5e6f",
            "customer_id": "6c1f0d2a-7b3c-4d5e-8f90-1a2b3c4d5e6f",
            "merchant_id": "9a8b7c6d-5e4f-4a3b-8c9d-0e1f2a3b4c5d",
            "risk_score": 94,
            "severity": "CRITICAL",
            "triggered_rules": [
                {
                    "rule_id": "unusual_amount",
                    "rule_name": "Unusual Transaction Amount",
                    "triggered": True,
                    "score": 35,
                    "severity": "HIGH",
                    "reason": "Amount is 434.8x customer baseline",
                    "evidence": {
                        "amount": "1000000.00",
                        "customer_average": "2300.00",
                        "merchant_p95": "6500.00"
                    }
                }
            ]
        }
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_id: UUID = Field(
        description="Transaction that triggered the investigation. Required.",
    )
    risk_score: int = Field(
        ge=0,
        le=100,
        description=(
            "Deterministic risk score produced by Member 1's risk engine (0-100). "
            "Member 2 never recalculates or modifies it."
        ),
    )
    severity: Severity = Field(
        description="Severity band produced by Member 1's risk engine.",
    )
    triggered_rules: list[RuleResultRecord] = Field(
        min_length=1,
        description=(
            "Rule results that fired for this transaction, as computed by "
            "Member 1. At least one rule result is required because an "
            "investigation is always started from a deterministic signal."
        ),
    )
    case_id: UUID | None = Field(
        default=None,
        description="Existing fraud case id, when Member 1 already created one.",
    )
    customer_id: UUID | None = Field(
        default=None,
        description="Customer id, when known. Loaded through tools when omitted.",
    )
    merchant_id: UUID | None = Field(
        default=None,
        description="Merchant id, when known. Loaded through tools when omitted.",
    )
    transaction_context: TransactionContext | None = Field(
        default=None,
        description=(
            "Optional transaction snapshot. Convenience only; the investigation "
            "tools can load the same facts from the database."
        ),
    )
    context_signals: list[ContextSignal] = Field(
        default_factory=list,
        description=(
            "Deterministic context signals from Member 1's context enricher. "
            "Known as 'risk_signals' in the Agent System Design state model."
        ),
    )
    trigger: InvestigationTrigger = Field(
        default=InvestigationTrigger.RISK_THRESHOLD,
        description="Why the investigation is being started.",
    )
    requested_by: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Reviewer or service identifier for the request, stored for audit. "
            "Authorization itself is enforced by Member 1's auth layer."
        ),
    )

    @model_validator(mode="after")
    def _context_ids_match_request(self) -> Self:
        context = self.transaction_context
        if context is None:
            return self
        if context.transaction_id != self.transaction_id:
            raise ValueError(
                "transaction_context.transaction_id must match transaction_id"
            )
        for field_name, expected in (
            ("customer_id", self.customer_id),
            ("merchant_id", self.merchant_id),
        ):
            actual = getattr(context, field_name)
            if expected is not None and actual != expected:
                raise ValueError(
                    f"transaction_context.{field_name} must match {field_name}"
                )
        return self

    @property
    def triggered_rule_ids(self) -> tuple[str, ...]:
        """Codes of the rules that fired, in the order supplied by Member 1."""

        return tuple(rule.rule_id for rule in self.triggered_rules)

"""Input/output types for the approved investigation tools (Member 2).

These models define what a tool returns. They are contract only: the database
queries that populate them are implemented in a later batch, once Member 4 has
provided the persistence layer.

BOUNDARY
--------
Every numeric field in this module is a **deterministic metric** computed by
Python or the database -- baselines, percentiles, counts, distances. The
language model consumes these values and narrates them; it never produces them
(``Agent System Design`` sections 2 and 9).

Field names mirror the ``transactions``, ``customers`` and ``merchants`` tables
in ``Database Design`` sections 3 to 5.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from app.schemas.investigation import RuleResultRecord, Severity
from app.schemas.investigation_result import RelatedEntity

__all__ = [
    "AmountStatistics",
    "AwareDateTime",
    "CustomerContext",
    "CustomerHistory",
    "MerchantContext",
    "MerchantObservedStatistics",
    "OperatingHours",
    "PriorCaseSummary",
    "PriorCasesResult",
    "RecentTransactionSet",
    "RelatedEntitiesResult",
    "RuleResultsResult",
    "TimeWindow",
    "TransactionSummary",
]

DEFAULT_HISTORY_WINDOW = timedelta(days=90)
"""Default behavioural baseline window (90 days, as in the audit-trail example)."""


def _require_aware(value: datetime) -> datetime:
    """Reject naive datetimes; the database stores TIMESTAMPTZ."""

    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone aware (TIMESTAMPTZ)")
    return value


AwareDateTime = Annotated[datetime, AfterValidator(_require_aware)]
"""A ``datetime`` that is guaranteed to carry timezone information."""


class TimeWindow(BaseModel):
    """A closed time range used by history tools."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    start: datetime = Field(description="Inclusive window start. Timezone aware.")
    end: datetime = Field(description="Exclusive window end. Timezone aware.")

    @model_validator(mode="after")
    def _validate_range(self) -> TimeWindow:
        for label, value in (("start", self.start), ("end", self.end)):
            if value.tzinfo is None:
                raise ValueError(f"{label} must be timezone aware (TIMESTAMPTZ)")
        if self.start >= self.end:
            raise ValueError("start must be earlier than end")
        return self


class TransactionSummary(BaseModel):
    """A stored transaction returned to the investigation layer.

    Read-only projection of the ``transactions`` table. Amounts stay
    :class:`~decimal.Decimal` to avoid binary floating point drift.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_id: UUID = Field(description="Primary key of the transaction.")
    customer_id: UUID = Field(description="Customer making the transaction.")
    merchant_id: UUID = Field(description="Merchant receiving the transaction.")
    amount: Decimal = Field(gt=0, description="Transaction amount.")
    currency: str = Field(
        min_length=3, max_length=3, pattern=r"^[A-Z]{3}$", description="ISO currency code."
    )
    timestamp: AwareDateTime = Field(description="Transaction event time.")
    country: str | None = Field(default=None, max_length=100, description="Country.")
    latitude: float | None = Field(
        default=None, ge=-90, le=90, description="Transaction latitude."
    )
    longitude: float | None = Field(
        default=None, ge=-180, le=180, description="Transaction longitude."
    )
    ip_address: str | None = Field(
        default=None, max_length=45, description="Source IP where available."
    )
    device_id: str | None = Field(
        default=None, max_length=200, description="Device reference where available."
    )


class AmountStatistics(BaseModel):
    """Deterministic amount distribution for a set of transactions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sample_size: int = Field(ge=0, description="Number of transactions in the sample.")
    minimum: Decimal | None = Field(default=None, description="Smallest amount.")
    maximum: Decimal | None = Field(default=None, description="Largest amount.")
    mean: Decimal | None = Field(default=None, description="Arithmetic mean amount.")
    median: Decimal | None = Field(
        default=None, description="Median amount, the behavioural baseline."
    )
    p95: Decimal | None = Field(
        default=None, description="95th percentile amount."
    )
    p99: Decimal | None = Field(default=None, description="99th percentile amount.")
    standard_deviation: Decimal | None = Field(
        default=None, description="Population standard deviation of the amounts."
    )

    @property
    def has_baseline(self) -> bool:
        """True when the sample is large enough to describe a baseline."""

        return self.sample_size > 0 and self.median is not None


class CustomerContext(BaseModel):
    """Customer profile plus baseline metrics used by behavioral analysis.

    Profile fields come from the ``customers`` table (``Database Design``
    section 3); the history summary comes from the customer history tool.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    customer_id: UUID = Field(description="Primary key of the customer.")
    country: str | None = Field(
        default=None, max_length=100, description="Customer country."
    )
    risk_baseline: Decimal | None = Field(
        default=None,
        ge=0,
        description="Stored customer risk baseline from the customers table.",
    )
    account_created_at: AwareDateTime | None = Field(
        default=None, description="Account creation time."
    )
    default_currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
        description="Typical transaction currency for this customer.",
    )
    amount_statistics: AmountStatistics | None = Field(
        default=None, description="Baseline amount distribution for the window."
    )
    transaction_count: int = Field(
        default=0, ge=0, description="Transactions inside the analysed window."
    )
    last_transaction_at: AwareDateTime | None = Field(
        default=None, description="Most recent transaction before the case."
    )


class CustomerHistory(BaseModel):
    """Result of ``get_customer_history``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    customer_id: UUID = Field(description="Customer the history belongs to.")
    window: TimeWindow = Field(description="Window the history was computed over.")
    context: CustomerContext = Field(description="Customer profile and baselines.")
    transactions: list[TransactionSummary] = Field(
        default_factory=list,
        description="Transactions inside the window, newest last.",
    )
    recent_review_outcomes: list[str] = Field(
        default_factory=list,
        description=(
            "Previous review outcomes for this customer, e.g. 'CONFIRMED_FRAUD'. "
            "Used as evidence, never as a score input."
        ),
    )
    reference: str = Field(
        min_length=1,
        description="Stable source reference, e.g. 'customer:<uuid>:history'.",
    )


class OperatingHours(BaseModel):
    """Parsed ``merchants.operating_hours`` (``Database Design`` section 5)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    opens_at: time = Field(description="Local opening time of the merchant.")
    closes_at: time = Field(description="Local closing time of the merchant.")

    def contains(self, moment: time) -> bool:
        """True when ``moment`` falls inside the operating window.

        Windows that wrap past midnight (for example 22:00-02:00) are handled.
        This is a pure time comparison; no LLM involvement.
        """

        if self.opens_at <= self.closes_at:
            return self.opens_at <= moment <= self.closes_at
        return moment >= self.opens_at or moment <= self.closes_at


class MerchantObservedStatistics(BaseModel):
    """Observed merchant transaction distribution for a window."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    window: TimeWindow = Field(description="Window the statistics cover.")
    transaction_count: int = Field(ge=0, description="Transactions in the window.")
    amount_statistics: AmountStatistics = Field(
        description="Observed amount distribution for the merchant."
    )
    average_daily_volume: Decimal | None = Field(
        default=None, ge=0, description="Observed average daily transaction count."
    )


class MerchantContext(BaseModel):
    """Merchant/business profile used by business context analysis.

    Field names mirror the ``merchants`` table (``Database Design`` section 5).
    The expected percentile bands are what make the unusual-amount rule
    contextual rather than a global threshold
    (``System Design`` section 7).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    merchant_id: UUID = Field(description="Primary key of the merchant.")
    name: str | None = Field(default=None, max_length=200, description="Merchant name.")
    category: str = Field(
        min_length=1,
        max_length=100,
        description="Business category, e.g. 'fuel_station' or 'gold_jewellery'.",
    )
    subcategory: str | None = Field(
        default=None, max_length=100, description="Optional business subcategory."
    )
    country: str | None = Field(
        default=None, max_length=100, description="Merchant country."
    )
    expected_p50: Decimal | None = Field(
        default=None, ge=0, description="Expected median ticket size."
    )
    expected_p95: Decimal | None = Field(
        default=None, ge=0, description="Expected high but common ticket size."
    )
    expected_p99: Decimal | None = Field(
        default=None, ge=0, description="Expected rare but plausible ticket size."
    )
    operating_hours: OperatingHours | None = Field(
        default=None, description="Local operating hours of the merchant."
    )
    daily_volume_baseline: Decimal | None = Field(
        default=None,
        ge=0,
        description="Expected daily transaction count, for merchant velocity context.",
    )
    observed: MerchantObservedStatistics | None = Field(
        default=None, description="Observed distribution for the analysed window."
    )
    reference: str = Field(
        min_length=1,
        description="Stable source reference, e.g. 'merchant:<uuid>:profile'.",
    )


class RecentTransactionSet(BaseModel):
    """Result of ``get_recent_transactions``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    customer_id: UUID | None = Field(
        default=None, description="Customer scope, when the query was customer based."
    )
    merchant_id: UUID | None = Field(
        default=None, description="Merchant scope, when the query was merchant based."
    )
    window: TimeWindow = Field(description="Window that was queried.")
    transactions: list[TransactionSummary] = Field(
        default_factory=list, description="Transactions inside the window, newest last."
    )
    amount_statistics: AmountStatistics = Field(
        default_factory=lambda: AmountStatistics(sample_size=0),
        description="Deterministic statistics for the returned set.",
    )

    @model_validator(mode="after")
    def _requires_a_single_scope(self) -> RecentTransactionSet:
        if (self.customer_id is None) == (self.merchant_id is None):
            raise ValueError(
                "exactly one of customer_id or merchant_id must be provided"
            )
        return self


class RelatedEntitiesResult(BaseModel):
    """Result of ``get_related_entities``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_id: UUID = Field(description="Transaction the search started from.")
    entities: list[RelatedEntity] = Field(
        default_factory=list,
        description="Linked customers, devices, IPs, merchants and transactions.",
    )
    generated_at: AwareDateTime = Field(description="Timezone-aware search time.")
    reference: str = Field(
        min_length=1,
        description="Stable source reference, e.g. 'transaction:<uuid>:entities'.",
    )

    @property
    def entity_count(self) -> int:
        """Number of linked entities found."""

        return len(self.entities)


class RuleResultsResult(BaseModel):
    """Result of ``get_rule_results`` for a transaction.

    Member 2 consumes this to cite Member 1's deterministic results. The
    investigation layer never recalculates a rule outcome.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_id: UUID = Field(description="Transaction the results belong to.")
    results: list[RuleResultRecord] = Field(
        default_factory=list, description="All stored rule results for the transaction."
    )
    reference: str = Field(
        min_length=1,
        description="Stable source reference, e.g. 'transaction:<uuid>:rule_results'.",
    )

    @property
    def triggered(self) -> list[RuleResultRecord]:
        """Only the rule results that fired."""

        return [result for result in self.results if result.triggered]

    @property
    def highest_severity(self) -> Severity | None:
        """Highest severity among triggered rules, or ``None`` when none fired."""

        triggered = self.triggered
        if not triggered:
            return None
        order = list(Severity)
        return max((result.severity for result in triggered), key=order.index)


class PriorCaseSummary(BaseModel):
    """A previous fraud case involving a customer or entity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: UUID = Field(description="Fraud case identifier.")
    transaction_id: UUID | None = Field(
        default=None, description="Primary transaction of the case."
    )
    severity: Severity = Field(description="Case severity.")
    risk_score: int = Field(ge=0, le=100, description="Case risk score.")
    status: str = Field(
        min_length=1,
        max_length=40,
        description=(
            "Case status, e.g. OPEN / UNDER_REVIEW / CLEARED / "
            "CONFIRMED_FRAUD / ESCALATED (Database Design section 7)."
        ),
    )
    summary: str | None = Field(
        default=None, max_length=4000, description="Stored investigation summary."
    )
    recommendation: str | None = Field(
        default=None, max_length=1000, description="Stored recommended action."
    )
    created_at: AwareDateTime = Field(description="Case creation time.")
    reference: str = Field(
        min_length=1, description="Stable source reference, e.g. 'case:<uuid>'."
    )


class PriorCasesResult(BaseModel):
    """Result of ``get_prior_cases``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    customer_id: UUID | None = Field(
        default=None, description="Customer scope, when queried by customer."
    )
    entity_ref: str | None = Field(
        default=None,
        max_length=500,
        description="Entity scope, when queried by device, IP or merchant.",
    )
    cases: list[PriorCaseSummary] = Field(
        default_factory=list, description="Previous cases, newest first."
    )
    reference: str = Field(
        min_length=1,
        description="Stable source reference for this prior-case query.",
    )

    @model_validator(mode="after")
    def _requires_a_single_scope(self) -> PriorCasesResult:
        if (self.customer_id is None) == (self.entity_ref is None):
            raise ValueError("exactly one of customer_id or entity_ref must be provided")
        return self

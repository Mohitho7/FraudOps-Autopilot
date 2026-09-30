"""Fake read tools for local runs and tests (Member 2, Batch 2).

READ THIS BEFORE USING ANYTHING FROM HERE
=========================================

Nothing in this module is real fraud data, and nothing it produces may be used
to support an investigation conclusion a human acts on. It exists for two
reasons only:

1. **Tests** need a deterministic, offline implementation of the Batch 1 tool
   protocols. The dataset below is fixed, so the same investigation always loads
   the same context and assertions can be exact.
2. **A local run** needs some data before Member 4's PostgreSQL read layer
   exists, so the orchestration engine can be exercised end to end.

Safety gate
-----------
:func:`require_fake_tools_enabled` refuses to run any of these tools unless
``FRAUDOPS_INVESTIGATION_ALLOW_FAKE_TOOLS`` is explicitly true. The check runs on
**every** tool call, so a toolset built while the gate was open stops working the
moment it is closed. ``tests/conftest.py`` enables it through the autouse
``fake_tools_enabled`` fixture, so the test suite never depends on a developer's
``.env``.

Every payload carries a ``FAKE-DATA`` reference prefix, so fake output can never
be mistaken for a database record.

What this module does not do
----------------------------
* No randomness: every number is a literal or arithmetic over literals.
* No fraud intelligence: it returns stored facts and plain
  :class:`~app.agents.tools.types.AmountStatistics` arithmetic. It does not score,
  rank or conclude anything.
* No SQL, no database connection, no network access.

Member 4 owns the real read layer; these are development and test adapters
behind the unchanged Batch 1 protocols.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from app.agents.tools.base import InvestigationToolError
from app.agents.tools.types import (
    AmountStatistics,
    CustomerContext,
    CustomerHistory,
    MerchantContext,
    MerchantObservedStatistics,
    OperatingHours,
    PriorCaseSummary,
    RecentTransactionSet,
    RuleResultsResult,
    TimeWindow,
    TransactionSummary,
)
from app.schemas.investigation import RuleResultRecord, Severity
from app.schemas.investigation_result import RelatedEntity

__all__ = [
    "ALLOW_FAKE_TOOLS_ENV",
    "FAKE_CASE_ID",
    "FAKE_CUSTOMER_ID",
    "FAKE_DATA_MARKER",
    "FAKE_DEVICE_ID",
    "FAKE_EVENT_TIME",
    "FAKE_IP_ADDRESS",
    "FAKE_MAX_ROWS",
    "FAKE_MERCHANT_ID",
    "FAKE_PRIOR_CASE_ID",
    "FAKE_RELATED_CUSTOMER_ID",
    "FAKE_TRANSACTION_ID",
    "FakeCustomerHistoryTool",
    "FakeInvestigationToolset",
    "FakeMerchantProfileTool",
    "FakePriorCasesTool",
    "FakeRecentTransactionsTool",
    "FakeRelatedEntitiesTool",
    "FakeRuleResultsTool",
    "FakeToolsetError",
    "build_fake_toolset",
    "compute_amount_statistics",
    "require_fake_tools_enabled",
]

FAKE_DATA_MARKER = "FAKE-DATA"
"""Prefix placed in every ``reference`` so fake output is self-identifying."""

ALLOW_FAKE_TOOLS_ENV = "FRAUDOPS_INVESTIGATION_ALLOW_FAKE_TOOLS"
"""Environment variable that must be ``true`` before any fake tool runs."""

FAKE_MAX_ROWS = 500
"""Hard ceiling on rows a fake tool returns.

The Batch 1 tool contracts leave the row bound to the implementation. This cap
keeps the agent's context small, which is the guardrail ``Agent System Design``
section 5 asks for: a tool must not be able to flood the context window.
"""

# --- Fixed dataset ----------------------------------------------------------
# Values mirror the documented demo scenario: a fuel-station transaction whose
# amount is far above the customer's baseline, with a device shared across
# accounts. Every id is a literal; nothing is generated at runtime.

FAKE_CUSTOMER_ID = UUID("6c1f0d2a-7b3c-4d5e-8f90-1a2b3c4d5e6f")
FAKE_RELATED_CUSTOMER_ID = UUID("7d2e1f3b-8c4d-4e6f-9a01-2b3c4d5e6f70")
FAKE_MERCHANT_ID = UUID("9a8b7c6d-5e4f-4a3b-8c9d-0e1f2a3b4c5d")
FAKE_TRANSACTION_ID = UUID("0f3d1c1e-6b6a-4f4b-9f2a-1d2c3b4a5e6f")
FAKE_PRIOR_TRANSACTION_ID = UUID("1b2c3d4e-5f6a-4b7c-8d9e-0f1a2b3c4d5e")
FAKE_CASE_ID = UUID("1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d")
FAKE_PRIOR_CASE_ID = UUID("2b3c4d5e-6f7a-4b8c-9d0e-1f2a3b4c5d6f")
FAKE_DEVICE_ID = "device-abc-123"
FAKE_IP_ADDRESS = "203.0.113.10"
FAKE_ACCOUNT_CREATED_AT = datetime(2021, 3, 14, 9, 0, tzinfo=timezone.utc)
FAKE_EVENT_TIME = datetime(2026, 9, 30, 10, 30, tzinfo=timezone.utc)
FAKE_CURRENCY = "INR"

# Customer baseline: ten small fuel purchases. The investigated transaction is
# three orders of magnitude larger, which is the scenario Batch 1 documents.
FAKE_BASELINE_AMOUNTS: tuple[str, ...] = (
    "1500.00",
    "1800.00",
    "2000.00",
    "2100.00",
    "2200.00",
    "2300.00",
    "2400.00",
    "2500.00",
    "2600.00",
    "2800.00",
)

FAKE_TRANSACTION_AMOUNT = Decimal("1000000.00")

# Rule results are literals in the shape Member 1 emits. The investigation layer
# cites them; it never re-evaluates a rule.
FAKE_RULE_RESULTS: tuple[RuleResultRecord, ...] = (
    RuleResultRecord(
        rule_id="unusual_amount",
        rule_name="Unusual Transaction Amount",
        triggered=True,
        score=35,
        severity=Severity.HIGH,
        reason="Amount is 434.8x customer baseline",
        evidence={
            "amount": "1000000.00",
            "customer_average": "2300.00",
            "merchant_p95": "6500.00",
        },
    ),
    RuleResultRecord(
        rule_id="velocity_24h",
        rule_name="Transaction Velocity (24h)",
        triggered=True,
        score=25,
        severity=Severity.MEDIUM,
        reason="4 transactions in the last 24 hours",
        evidence={"count": 4, "window_hours": 24},
    ),
    RuleResultRecord(
        rule_id="new_device",
        rule_name="Unseen Device",
        triggered=False,
        score=0,
        severity=Severity.LOW,
        reason="Device not seen in the last 90 days",
        evidence={"device_id": FAKE_DEVICE_ID},
    ),
)

FAKE_MERCHANT_BASELINE_AMOUNTS: tuple[str, ...] = (
    "1200.00",
    "1800.00",
    "2500.00",
    "3000.00",
    "4000.00",
    "5000.00",
    "6500.00",
)

FAKE_ENABLE_VALUES = frozenset({"1", "true", "yes", "on"})
"""Values accepted for the gate variable, compared case-insensitively."""


class FakeToolsetError(InvestigationToolError):
    """A fake tool was asked for something the fixed dataset does not contain.

    Raised instead of inventing data, for the same reason the Batch 1 stubs
    raise: an unknown entity must never be answered with a plausible-looking
    fabrication.
    """


def require_fake_tools_enabled() -> None:
    """Refuse to run fake tools unless the gate is explicitly open.

    Raises:
        FakeToolsetError: When ``FRAUDOPS_INVESTIGATION_ALLOW_FAKE_TOOLS`` is not
            one of :data:`FAKE_ENABLE_VALUES`.
    """

    raw = os.environ.get(ALLOW_FAKE_TOOLS_ENV, "").strip().lower()
    if raw in FAKE_ENABLE_VALUES:
        return
    raise FakeToolsetError(
        f"fake investigation tools are disabled. Set {ALLOW_FAKE_TOOLS_ENV}=true "
        "to use them. They contain fabricated data and must never be used in a "
        "deployment: Member 4 owns the real read layer."
    )


def _checked_limit(limit: int) -> int:
    """Validate a caller-supplied ``limit`` and clamp it to :data:`FAKE_MAX_ROWS`.

    Raises:
        InvestigationToolError: When ``limit`` is not a positive integer.
    """

    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise InvestigationToolError(f"limit must be a positive integer, got {limit!r}")
    return min(limit, FAKE_MAX_ROWS)


def _window_for(
    time_window: TimeWindow | None,
    *,
    default_days: int = 90,
) -> TimeWindow:
    """Return ``time_window``, or a deterministic default ending at the event.

    The default is the documented 90-day behavioural baseline ending at the
    transaction timestamp, so a caller that omits the window still gets a
    reproducible range.
    """

    if time_window is not None:
        return time_window
    return TimeWindow(
        start=FAKE_EVENT_TIME - timedelta(days=default_days),
        end=FAKE_EVENT_TIME,
    )


def _percentile(sorted_values: list[Decimal], fraction: Decimal) -> Decimal | None:
    """Linear-interpolated percentile over pre-sorted values.

    Plain arithmetic, mirroring the ``PERCENTILE_CONT`` aggregate the production
    read layer is expected to use. Deterministic and independent of any AI
    component (``Agent System Design`` sections 2 and 9).
    """

    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = Decimal(len(sorted_values) - 1) * fraction
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    remainder = position - Decimal(lower_index)
    lower = sorted_values[lower_index]
    upper = sorted_values[upper_index]
    return (lower + (upper - lower) * remainder).quantize(Decimal("0.01"))


def compute_amount_statistics(amounts: list[Decimal]) -> AmountStatistics:
    """Compute the deterministic amount distribution for ``amounts``.

    Exposed because the fake tools and the later analysis capability must use
    exactly the same definition. Every value here is arithmetic; no language
    model is involved and none may be.
    """

    if not amounts:
        return AmountStatistics(sample_size=0)
    ordered = sorted(amounts)
    total = sum(ordered)
    count = Decimal(len(ordered))
    mean = (total / count).quantize(Decimal("0.01"))
    variance = sum(((value - mean) ** 2 for value in ordered), Decimal(0)) / count
    deviation = variance.sqrt().quantize(Decimal("0.01"))
    midpoint = len(ordered) // 2
    if len(ordered) % 2 == 1:
        median = ordered[midpoint]
    else:
        median = ((ordered[midpoint - 1] + ordered[midpoint]) / 2).quantize(
            Decimal("0.01")
        )
    return AmountStatistics(
        sample_size=len(ordered),
        minimum=ordered[0],
        maximum=ordered[-1],
        mean=mean,
        median=median,
        p95=_percentile(ordered, Decimal("0.95")),
        p99=_percentile(ordered, Decimal("0.99")),
        standard_deviation=deviation,
    )


def _baseline_transactions(customer_id: UUID) -> list[TransactionSummary]:
    """Build the customer's deterministic baseline history."""

    return [
        TransactionSummary(
            transaction_id=UUID(int=FAKE_TRANSACTION_ID.int + index + 1),
            customer_id=customer_id,
            merchant_id=FAKE_MERCHANT_ID,
            amount=Decimal(amount),
            currency=FAKE_CURRENCY,
            timestamp=FAKE_EVENT_TIME - timedelta(days=days_before, hours=2),
            country="IN",
            latitude=17.385,
            longitude=78.4867,
            ip_address=FAKE_IP_ADDRESS,
            device_id=FAKE_DEVICE_ID,
        )
        for index, (amount, days_before) in enumerate(
            zip(
                FAKE_BASELINE_AMOUNTS,
                range(len(FAKE_BASELINE_AMOUNTS), 0, -1),
            )
        )
    ]


def _investigated_transaction() -> TransactionSummary:
    """The transaction under investigation, as a stored row."""

    return TransactionSummary(
        transaction_id=FAKE_TRANSACTION_ID,
        customer_id=FAKE_CUSTOMER_ID,
        merchant_id=FAKE_MERCHANT_ID,
        amount=FAKE_TRANSACTION_AMOUNT,
        currency=FAKE_CURRENCY,
        timestamp=FAKE_EVENT_TIME,
        country="IN",
        latitude=17.385,
        longitude=78.4867,
        ip_address=FAKE_IP_ADDRESS,
        device_id=FAKE_DEVICE_ID,
    )


class FakeCustomerHistoryTool:
    """Deterministic ``get_customer_history`` implementation."""

    def __init__(self, customers: dict[UUID, CustomerContext] | None = None) -> None:
        self._customers = customers or {}

    async def get_customer_history(
        self,
        customer_id: UUID,
        time_window: TimeWindow | None = None,
    ) -> CustomerHistory:
        """Return the fixed baseline for ``customer_id``.

        Raises:
            FakeToolsetError: When the customer is not part of the fixed dataset.
        """

        require_fake_tools_enabled()
        context = self._customers.get(customer_id)
        if context is None and customer_id != FAKE_CUSTOMER_ID:
            raise FakeToolsetError(f"fake dataset has no customer {customer_id}")
        window = _window_for(time_window)
        baseline = _baseline_transactions(customer_id)
        if context is None:
            context = CustomerContext(
                customer_id=customer_id,
                country="IN",
                risk_baseline=Decimal("18.40"),
                account_created_at=FAKE_ACCOUNT_CREATED_AT,
                default_currency=FAKE_CURRENCY,
                transaction_count=len(baseline),
                last_transaction_at=baseline[-1].timestamp,
            )
        return CustomerHistory(
            customer_id=customer_id,
            window=window,
            context=context.model_copy(
                update={
                    "amount_statistics": compute_amount_statistics(
                        [item.amount for item in baseline]
                    ),
                    "transaction_count": len(baseline),
                    "last_transaction_at": baseline[-1].timestamp,
                }
            ),
            transactions=baseline,
            recent_review_outcomes=["CLEARED"],
            reference=f"{FAKE_DATA_MARKER}:customer:{customer_id}:history",
        )


class FakeRecentTransactionsTool:
    """Deterministic ``get_recent_transactions`` implementation."""

    async def get_recent_transactions(
        self,
        *,
        customer_id: UUID | None = None,
        merchant_id: UUID | None = None,
        time_window: TimeWindow | None = None,
        limit: int = 100,
    ) -> RecentTransactionSet:
        """Return the fixed rows for exactly one subject.

        Raises:
            InvestigationToolError: When both or neither scope is supplied, or
                when ``limit`` is not a positive integer.
            FakeToolsetError: When the subject is not in the fixed dataset.
        """

        require_fake_tools_enabled()
        if (customer_id is None) == (merchant_id is None):
            raise InvestigationToolError(
                "exactly one of customer_id or merchant_id must be provided"
            )
        bounded_limit = _checked_limit(limit)
        window = _window_for(time_window)
        if customer_id is not None:
            if customer_id != FAKE_CUSTOMER_ID:
                raise FakeToolsetError(
                    f"fake dataset has no customer {customer_id}"
                )
            rows = [
                *_baseline_transactions(customer_id),
                _investigated_transaction(),
            ]
        else:
            if merchant_id != FAKE_MERCHANT_ID:
                raise FakeToolsetError(
                    f"fake dataset has no merchant {merchant_id}"
                )
            rows = [
                TransactionSummary(
                    transaction_id=UUID(int=FAKE_TRANSACTION_ID.int + 100 + index),
                    customer_id=FAKE_CUSTOMER_ID,
                    merchant_id=FAKE_MERCHANT_ID,
                    amount=Decimal(amount),
                    currency=FAKE_CURRENCY,
                    timestamp=FAKE_EVENT_TIME - timedelta(days=index + 1),
                    country="IN",
                    device_id=FAKE_DEVICE_ID,
                )
                for index, amount in enumerate(FAKE_MERCHANT_BASELINE_AMOUNTS)
            ]
        limited = rows[:bounded_limit]
        return RecentTransactionSet(
            customer_id=customer_id,
            merchant_id=merchant_id,
            window=window,
            transactions=limited,
            amount_statistics=compute_amount_statistics(
                [item.amount for item in limited]
            ),
        )


class FakeRuleResultsTool:
    """Deterministic ``get_rule_results`` implementation.

    Returns literals that mimic Member 1's stored records. The investigation
    layer cites them verbatim and never re-evaluates a rule.
    """

    async def get_rule_results(self, transaction_id: UUID) -> RuleResultsResult:
        """Return the fixed rule results for ``transaction_id``.

        Raises:
            FakeToolsetError: When the transaction is not in the fixed dataset.
        """

        require_fake_tools_enabled()
        if transaction_id != FAKE_TRANSACTION_ID:
            raise FakeToolsetError(
                f"fake dataset has no transaction {transaction_id}"
            )
        return RuleResultsResult(
            transaction_id=transaction_id,
            results=list(FAKE_RULE_RESULTS),
            reference=f"{FAKE_DATA_MARKER}:transaction:{transaction_id}:rule_results",
        )


class FakeMerchantProfileTool:
    """Deterministic ``get_merchant_profile`` implementation."""

    async def get_merchant_profile(self, merchant_id: UUID) -> MerchantContext:
        """Return the fixed merchant profile.

        Raises:
            FakeToolsetError: When the merchant is not in the fixed dataset.
        """

        require_fake_tools_enabled()
        if merchant_id != FAKE_MERCHANT_ID:
            raise FakeToolsetError(
                f"fake dataset has no merchant {merchant_id}"
            )
        amounts = [Decimal(value) for value in FAKE_MERCHANT_BASELINE_AMOUNTS]
        window = _window_for(None)
        observed_days = Decimal((window.end - window.start).days or 1)
        return MerchantContext(
            merchant_id=merchant_id,
            name="M-FUEL-019",
            category="fuel_station",
            subcategory="retail_fuel",
            country="IN",
            expected_p50=Decimal("2500.00"),
            expected_p95=Decimal("6500.00"),
            expected_p99=Decimal("12000.00"),
            operating_hours=OperatingHours(
                opens_at=datetime(2026, 1, 1, 6, 0).time(),
                closes_at=datetime(2026, 1, 1, 22, 0).time(),
            ),
            daily_volume_baseline=Decimal("40"),
            observed=MerchantObservedStatistics(
                window=window,
                transaction_count=len(amounts),
                amount_statistics=compute_amount_statistics(amounts),
                average_daily_volume=(
                    Decimal(len(amounts)) / observed_days
                ).quantize(Decimal("0.01")),
            ),
            reference=f"{FAKE_DATA_MARKER}:merchant:{merchant_id}:profile",
        )


class FakeRelatedEntitiesTool:
    """Deterministic ``get_related_entities`` implementation."""

    async def get_related_entities(
        self,
        transaction_id: UUID,
        *,
        limit: int = 50,
    ) -> list[RelatedEntity]:
        """Return the fixed linked entities for ``transaction_id``.

        Raises:
            InvestigationToolError: When ``limit`` is not a positive integer.
            FakeToolsetError: When the transaction is not in the fixed dataset.
        """

        require_fake_tools_enabled()
        if transaction_id != FAKE_TRANSACTION_ID:
            raise FakeToolsetError(
                f"fake dataset has no transaction {transaction_id}"
            )
        bounded_limit = _checked_limit(limit)
        entities = [
            RelatedEntity(
                entity_type="DEVICE",
                entity_ref=FAKE_DEVICE_ID,
                relation_type="SHARED_DEVICE",
                label=FAKE_DEVICE_ID,
                risk_note=(
                    f"{FAKE_DATA_MARKER}: device also seen on "
                    f"{FAKE_RELATED_CUSTOMER_ID}"
                ),
            ),
            RelatedEntity(
                entity_type="IP_ADDRESS",
                entity_ref=FAKE_IP_ADDRESS,
                relation_type="SHARED_IP_ADDRESS",
                label=FAKE_IP_ADDRESS,
                risk_note=f"{FAKE_DATA_MARKER}: shared source address",
            ),
            RelatedEntity(
                entity_type="CUSTOMER",
                entity_ref=str(FAKE_RELATED_CUSTOMER_ID),
                relation_type="SHARED_DEVICE",
                label="linked-account",
                risk_note=(
                    f"{FAKE_DATA_MARKER}: shares device {FAKE_DEVICE_ID}"
                ),
                related_case_id=FAKE_PRIOR_CASE_ID,
            ),
        ]
        return entities[:bounded_limit]


class FakePriorCasesTool:
    """Deterministic ``get_prior_cases`` implementation.

    Wired into the toolset for completeness. The Batch 2 workflow does **not**
    call it, because the frozen Batch 1 ``InvestigationState`` has no field to
    carry prior cases; see ``docs/member2/agent-workflow.md``.
    """

    async def get_prior_cases(
        self,
        *,
        customer_id: UUID | None = None,
        entity_ref: str | None = None,
        limit: int = 20,
    ) -> list[PriorCaseSummary]:
        """Return the fixed previous case for exactly one scope.

        Raises:
            InvestigationToolError: When both or neither scope is supplied, or
                when ``limit`` is not a positive integer.
            FakeToolsetError: When the scope is not in the fixed dataset.
        """

        require_fake_tools_enabled()
        if (customer_id is None) == (entity_ref is None):
            raise InvestigationToolError(
                "exactly one of customer_id or entity_ref must be provided"
            )
        bounded_limit = _checked_limit(limit)
        if customer_id is not None and customer_id != FAKE_CUSTOMER_ID:
            raise FakeToolsetError(f"fake dataset has no customer {customer_id}")
        if entity_ref is not None and entity_ref not in {
            FAKE_DEVICE_ID,
            FAKE_IP_ADDRESS,
            str(FAKE_RELATED_CUSTOMER_ID),
        }:
            raise FakeToolsetError(f"fake dataset has no entity {entity_ref}")
        cases = [
            PriorCaseSummary(
                case_id=FAKE_PRIOR_CASE_ID,
                transaction_id=FAKE_PRIOR_TRANSACTION_ID,
                severity=Severity.MEDIUM,
                risk_score=61,
                status="CLEARED",
                summary=f"{FAKE_DATA_MARKER}: prior case reviewed and cleared",
                recommendation="MONITOR",
                created_at=FAKE_EVENT_TIME - timedelta(days=45),
                reference=f"{FAKE_DATA_MARKER}:case:{FAKE_PRIOR_CASE_ID}",
            )
        ]
        return cases[:bounded_limit]


@dataclass(frozen=True, slots=True)
class FakeInvestigationToolset:
    """The Batch 1 ``InvestigationToolset`` protocol, backed by fakes.

    Satisfies :class:`~app.agents.tools.base.InvestigationToolset`, so the graph
    cannot tell a fake toolset from a real one. That is the point: Member 4
    swaps the implementation, not the graph.
    """

    customer_history_tool: FakeCustomerHistoryTool = field(
        default_factory=FakeCustomerHistoryTool
    )
    transaction_history_tool: FakeRecentTransactionsTool = field(
        default_factory=FakeRecentTransactionsTool
    )
    rule_results_tool: FakeRuleResultsTool = field(default_factory=FakeRuleResultsTool)
    merchant_profile_tool: FakeMerchantProfileTool = field(
        default_factory=FakeMerchantProfileTool
    )
    relationship_tool: FakeRelatedEntitiesTool = field(
        default_factory=FakeRelatedEntitiesTool
    )
    case_history_tool: FakePriorCasesTool = field(default_factory=FakePriorCasesTool)


def build_fake_toolset() -> FakeInvestigationToolset:
    """Return a fake toolset.

    A new instance per call: the toolset holds no mutable run state, and building
    fresh keeps it obvious that the gate is evaluated on every tool call rather
    than once at construction.

    Raises:
        FakeToolsetError: When the gate variable is not enabled.
    """

    require_fake_tools_enabled()
    return FakeInvestigationToolset()
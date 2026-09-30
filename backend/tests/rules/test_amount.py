"""
Unit tests for UnusualAmountRule.
"""

from datetime import datetime, timezone
from decimal import Decimal
import pytest

from app.rules.amount import UnusualAmountRule
from app.schemas.context import FraudEvaluationContext
from app.schemas.rule import RuleExecutionStatus, Severity
from app.schemas.transaction import PreviousTransaction, Transaction


def make_transaction(amount: str = "5000.00") -> Transaction:
    return Transaction(
        transaction_id="tx-curr",
        customer_id="cust-1",
        merchant_id="merch-1",
        amount=Decimal(amount),
        currency="INR",
        timestamp=datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc),
    )


def make_previous(
    tx_id: str,
    amount: str,
    timestamp: datetime = None,
) -> PreviousTransaction:
    return PreviousTransaction(
        transaction_id=tx_id,
        timestamp=timestamp or datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc),
        amount=Decimal(amount),
        merchant_id="merch-1",
    )


class TestUnusualAmountRule:
    @pytest.mark.asyncio
    async def test_empty_history_insufficient_data(self):
        rule = UnusualAmountRule(minimum_history=3, amount_multiplier_threshold=3.0)
        tx = make_transaction(amount="80000.00")
        ctx = FraudEvaluationContext()

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.triggered is False
        assert result.score == 0
        assert result.severity == Severity.NONE
        assert result.evidence["insufficient_historical_data"] is True
        assert "Insufficient historical data" in result.reason

    @pytest.mark.asyncio
    async def test_fewer_than_minimum_history_insufficient_data(self):
        rule = UnusualAmountRule(minimum_history=3, amount_multiplier_threshold=3.0)
        tx = make_transaction(amount="80000.00")
        recent = [
            make_previous("p1", "10000.00"),
            make_previous("p2", "20000.00"),
        ]
        ctx = FraudEvaluationContext(recent_transactions=recent)

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.triggered is False
        assert result.score == 0
        assert result.severity == Severity.NONE
        assert result.evidence["insufficient_historical_data"] is True

    @pytest.mark.asyncio
    async def test_normal_amount_below_multiplier(self):
        # Historical: 10000, 20000, 20000 -> median 20000
        # Current: 40000 -> ratio 2.0 < 3.0 -> CLEAN
        rule = UnusualAmountRule(minimum_history=3, amount_multiplier_threshold=3.0)
        tx = make_transaction(amount="40000.00")
        recent = [
            make_previous("p1", "10000.00"),
            make_previous("p2", "20000.00"),
            make_previous("p3", "20000.00"),
        ]
        ctx = FraudEvaluationContext(recent_transactions=recent)

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.triggered is False
        assert result.score == 0
        assert result.severity == Severity.NONE
        assert result.evidence["median_baseline"] == "20000.00"
        assert result.evidence["multiplier_ratio"] == 2.0

    @pytest.mark.asyncio
    async def test_exact_multiplier_threshold_triggers(self):
        # Historical: 10000, 20000, 20000 -> median 20000
        # Current: 60000 -> ratio 3.0 == threshold 3.0 -> TRIGGER
        rule = UnusualAmountRule(minimum_history=3, amount_multiplier_threshold=3.0)
        tx = make_transaction(amount="60000.00")
        recent = [
            make_previous("p1", "10000.00"),
            make_previous("p2", "20000.00"),
            make_previous("p3", "20000.00"),
        ]
        ctx = FraudEvaluationContext(recent_transactions=recent)

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.triggered is True
        assert result.score == 60
        assert result.severity == Severity.MEDIUM
        assert result.evidence["multiplier_ratio"] == 3.0
        assert "Unusually large transaction" in result.reason

    @pytest.mark.asyncio
    async def test_above_multiplier_threshold_scaling(self):
        # Historical: 10000, 20000, 20000 -> median 20000
        # Current: 80000 -> ratio 4.0 (deviation 1.0) -> score 60 + 1*20 = 80 (HIGH)
        rule = UnusualAmountRule(minimum_history=3, amount_multiplier_threshold=3.0)
        tx = make_transaction(amount="80000.00")
        recent = [
            make_previous("p1", "10000.00"),
            make_previous("p2", "20000.00"),
            make_previous("p3", "20000.00"),
        ]
        ctx = FraudEvaluationContext(recent_transactions=recent)

        result = await rule.evaluate(tx, ctx)

        assert result.triggered is True
        assert result.score == 80
        assert result.severity == Severity.HIGH
        assert result.evidence["multiplier_ratio"] == 4.0

    @pytest.mark.asyncio
    async def test_extreme_multiplier_score_capped_at_100(self):
        # Historical median: 1000
        # Current: 10000 -> ratio 10.0 (deviation 7.0) -> score capped at 100 (CRITICAL)
        rule = UnusualAmountRule(minimum_history=3, amount_multiplier_threshold=3.0)
        tx = make_transaction(amount="10000.00")
        recent = [
            make_previous("p1", "1000.00"),
            make_previous("p2", "1000.00"),
            make_previous("p3", "1000.00"),
        ]
        ctx = FraudEvaluationContext(recent_transactions=recent)

        result = await rule.evaluate(tx, ctx)

        assert result.triggered is True
        assert result.score == 100
        assert result.severity == Severity.CRITICAL

    @pytest.mark.asyncio
    async def test_exact_minimum_history_evaluated(self):
        # Exactly 3 historical items
        rule = UnusualAmountRule(minimum_history=3, amount_multiplier_threshold=3.0)
        tx = make_transaction(amount="3000.00")
        recent = [
            make_previous("p1", "500.00"),
            make_previous("p2", "1000.00"),
            make_previous("p3", "1500.00"),
        ]
        ctx = FraudEvaluationContext(recent_transactions=recent)

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.evidence["insufficient_historical_data"] is False
        assert result.evidence["median_baseline"] == "1000.00"
        # 3000 / 1000 = 3.0 -> triggers
        assert result.triggered is True
        assert result.score == 60

    @pytest.mark.asyncio
    async def test_deterministic_repeatability(self):
        rule = UnusualAmountRule(minimum_history=3, amount_multiplier_threshold=3.0)
        tx = make_transaction(amount="75000.00")
        recent = [
            make_previous("p1", "10000.00"),
            make_previous("p2", "20000.00"),
            make_previous("p3", "30000.00"),
        ]
        ctx = FraudEvaluationContext(recent_transactions=recent)

        r1 = await rule.evaluate(tx, ctx)
        r2 = await rule.evaluate(tx, ctx)

        assert r1.triggered == r2.triggered
        assert r1.score == r2.score
        assert r1.severity == r2.severity
        assert r1.evidence == r2.evidence

    def test_invalid_config_raises_error(self):
        with pytest.raises(ValueError, match="minimum_history must be positive"):
            UnusualAmountRule(minimum_history=0)
        with pytest.raises(ValueError, match="amount_multiplier_threshold must be greater than 1.0"):
            UnusualAmountRule(amount_multiplier_threshold=1.0)

    # -------------------------------------------------------------------------
    # REGRESSION TESTS FOR F-01: Exclude Future-Dated Transactions from Baseline
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_future_dated_transaction_excluded_from_historical_median(self):
        """
        REGRESSION TEST FOR F-01:
        Current transaction at 10:00:00 for ₹60,000.
        Valid history before 10:00:
          - 09:00 -> ₹10,000
          - 09:15 -> ₹20,000
          - 09:30 -> ₹30,000
          Valid median = ₹20,000.
          Current amount ₹60,000 is 3.0x median -> TRIGGERS (score=60).

        Future-dated transaction:
          - 10:30 (30 mins in future relative to current tx) -> ₹100,000.

        WITHOUT FIX:
          Future transaction is incorrectly included:
          History = [10k, 20k, 30k, 100k] -> median = (20k + 30k)/2 = ₹25,000.
          Current amount 60,000 / 25,000 = 2.4x < 3.0x -> FAILS TO TRIGGER (score=0, triggered=False).

        WITH FIX:
          Future transaction is excluded:
          History = [10k, 20k, 30k] -> median = ₹20,000.
          Current amount 60,000 / 20,000 = 3.0x >= 3.0x -> TRIGGERS (score=60, triggered=True).
        """
        t_curr = datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
        rule = UnusualAmountRule(minimum_history=3, amount_multiplier_threshold=3.0)
        tx = Transaction(
            transaction_id="tx-curr-1000",
            customer_id="cust-1",
            merchant_id="merch-1",
            amount=Decimal("60000.00"),
            currency="INR",
            timestamp=t_curr,
        )

        recent = [
            make_previous("p1", "10000.00", timestamp=datetime(2026, 3, 15, 9, 0, 0, tzinfo=timezone.utc)),
            make_previous("p2", "20000.00", timestamp=datetime(2026, 3, 15, 9, 15, 0, tzinfo=timezone.utc)),
            make_previous("p3", "30000.00", timestamp=datetime(2026, 3, 15, 9, 30, 0, tzinfo=timezone.utc)),
            # Future-dated transaction (MUST be excluded)
            make_previous("p_future", "100000.00", timestamp=datetime(2026, 3, 15, 10, 30, 0, tzinfo=timezone.utc)),
        ]
        ctx = FraudEvaluationContext(recent_transactions=recent)

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.evidence["historical_transaction_count"] == 3
        assert "100000.00" not in result.evidence["historical_amounts"]
        assert result.evidence["median_baseline"] == "20000.00"
        assert result.evidence["multiplier_ratio"] == 3.0
        assert result.triggered is True
        assert result.score == 60
        assert result.severity == Severity.MEDIUM

    @pytest.mark.asyncio
    async def test_exact_current_timestamp_included_and_microsecond_future_excluded(self):
        """
        Verify exact boundary condition:
        - Transaction at exactly t_curr is INCLUDED.
        - Transaction at t_curr + 1 microsecond is EXCLUDED.
        """
        from datetime import timedelta

        t_curr = datetime(2026, 3, 15, 10, 0, 0, 0, tzinfo=timezone.utc)
        rule = UnusualAmountRule(minimum_history=3, amount_multiplier_threshold=3.0)
        tx = Transaction(
            transaction_id="tx-curr-boundary",
            customer_id="cust-1",
            merchant_id="merch-1",
            amount=Decimal("15000.00"),
            currency="INR",
            timestamp=t_curr,
        )

        recent = [
            make_previous("p1", "5000.00", timestamp=t_curr - timedelta(minutes=10)),
            make_previous("p2", "5000.00", timestamp=t_curr - timedelta(minutes=5)),
            # Exactly on the boundary: must be included to satisfy minimum_history=3
            make_previous("p_exact", "5000.00", timestamp=t_curr),
            # 1 microsecond in future: must be excluded
            make_previous("p_future_us", "500000.00", timestamp=t_curr + timedelta(microseconds=1)),
        ]
        ctx = FraudEvaluationContext(recent_transactions=recent)

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.evidence["historical_transaction_count"] == 3
        assert "500000.00" not in result.evidence["historical_amounts"]
        assert result.evidence["median_baseline"] == "5000.00"
        assert result.triggered is True
        assert result.score == 60

    @pytest.mark.asyncio
    async def test_multiple_future_transactions_with_enormous_amounts_ignored(self):
        """
        Multiple future-dated transactions with massive amounts must not pollute baseline.
        """
        t_curr = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        rule = UnusualAmountRule(minimum_history=3, amount_multiplier_threshold=3.0)
        tx = make_transaction(amount="3000.00")  # tx timestamp is 12:00:00

        recent = [
            make_previous("p1", "1000.00", timestamp=datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc)),
            make_previous("p2", "1000.00", timestamp=datetime(2026, 3, 15, 11, 0, 0, tzinfo=timezone.utc)),
            make_previous("p3", "1000.00", timestamp=datetime(2026, 3, 15, 11, 30, 0, tzinfo=timezone.utc)),
            # Multiple future transactions
            make_previous("pf1", "9999999.00", timestamp=datetime(2026, 3, 15, 12, 1, 0, tzinfo=timezone.utc)),
            make_previous("pf2", "8888888.00", timestamp=datetime(2026, 3, 15, 13, 0, 0, tzinfo=timezone.utc)),
            make_previous("pf3", "7777777.00", timestamp=datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)),
        ]
        ctx = FraudEvaluationContext(recent_transactions=recent)

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.evidence["historical_transaction_count"] == 3
        assert result.evidence["median_baseline"] == "1000.00"
        assert result.triggered is True
        assert result.score == 60

    @pytest.mark.asyncio
    async def test_current_transaction_in_history_excluded_by_id(self):
        """
        Verify that if the current transaction ID appears in the history collection,
        it remains excluded by transaction ID even if its timestamp is <= current timestamp.
        """
        t_curr = datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
        rule = UnusualAmountRule(minimum_history=3, amount_multiplier_threshold=3.0)
        tx = Transaction(
            transaction_id="tx-curr-dup",
            customer_id="cust-1",
            merchant_id="merch-1",
            amount=Decimal("60000.00"),
            currency="INR",
            timestamp=t_curr,
        )

        recent = [
            make_previous("p1", "20000.00", timestamp=datetime(2026, 3, 15, 9, 0, 0, tzinfo=timezone.utc)),
            make_previous("p2", "20000.00", timestamp=datetime(2026, 3, 15, 9, 15, 0, tzinfo=timezone.utc)),
            make_previous("p3", "20000.00", timestamp=datetime(2026, 3, 15, 9, 30, 0, tzinfo=timezone.utc)),
            # Duplicate of current transaction in history:
            make_previous("tx-curr-dup", "60000.00", timestamp=t_curr),
            # Future transaction:
            make_previous("p_future", "100000.00", timestamp=datetime(2026, 3, 15, 10, 30, 0, tzinfo=timezone.utc)),
        ]
        ctx = FraudEvaluationContext(recent_transactions=recent)

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.evidence["historical_transaction_count"] == 3
        assert result.evidence["median_baseline"] == "20000.00"
        assert result.triggered is True
        assert result.score == 60


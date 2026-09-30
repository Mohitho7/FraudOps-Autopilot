"""
Unit tests for TransactionVelocityRule.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest

from app.rules.velocity import TransactionVelocityRule
from app.schemas.context import FraudEvaluationContext
from app.schemas.rule import RuleExecutionStatus, Severity
from app.schemas.transaction import PreviousTransaction, Transaction


@pytest.fixture
def base_time():
    return datetime(2026, 3, 15, 10, 10, 0, tzinfo=timezone.utc)


def make_transaction(
    tx_id: str = "tx-curr",
    amount: str = "5000.00",
    timestamp: datetime = None,
    customer_id: str = "cust-1",
    merchant_id: str = "merch-1",
) -> Transaction:
    return Transaction(
        transaction_id=tx_id,
        customer_id=customer_id,
        merchant_id=merchant_id,
        amount=Decimal(amount),
        currency="INR",
        timestamp=timestamp or datetime(2026, 3, 15, 10, 10, 0, tzinfo=timezone.utc),
    )


def make_previous(
    tx_id: str,
    timestamp: datetime,
    amount: str = "1000.00",
) -> PreviousTransaction:
    return PreviousTransaction(
        transaction_id=tx_id,
        timestamp=timestamp,
        amount=Decimal(amount),
        merchant_id="merch-1",
    )


class TestTransactionVelocityRule:
    @pytest.mark.asyncio
    async def test_empty_history_below_threshold(self, base_time):
        rule = TransactionVelocityRule(window_minutes=10, transaction_threshold=5)
        tx = make_transaction(timestamp=base_time)
        ctx = FraudEvaluationContext()

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.triggered is False
        assert result.score == 0
        assert result.severity == Severity.NONE
        assert result.evidence["transaction_count"] == 1
        assert result.evidence["transaction_threshold"] == 5

    @pytest.mark.asyncio
    async def test_below_threshold_four_transactions(self, base_time):
        # 3 previous + 1 current = 4 (threshold=5)
        rule = TransactionVelocityRule(window_minutes=10, transaction_threshold=5)
        tx = make_transaction(timestamp=base_time)
        recent = [
            make_previous("p1", base_time - timedelta(minutes=2)),
            make_previous("p2", base_time - timedelta(minutes=5)),
            make_previous("p3", base_time - timedelta(minutes=8)),
        ]
        ctx = FraudEvaluationContext(recent_transactions=recent)

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.triggered is False
        assert result.score == 0
        assert result.severity == Severity.NONE
        assert result.evidence["transaction_count"] == 4

    @pytest.mark.asyncio
    async def test_exactly_at_threshold_triggers(self, base_time):
        # 4 previous + 1 current = 5 (threshold=5) -> TRIGGER
        rule = TransactionVelocityRule(window_minutes=10, transaction_threshold=5)
        tx = make_transaction(timestamp=base_time)
        recent = [
            make_previous("p1", base_time - timedelta(minutes=1)),
            make_previous("p2", base_time - timedelta(minutes=3)),
            make_previous("p3", base_time - timedelta(minutes=6)),
            make_previous("p4", base_time - timedelta(minutes=9)),
        ]
        ctx = FraudEvaluationContext(recent_transactions=recent)

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.triggered is True
        assert result.score == 60
        assert result.severity == Severity.MEDIUM
        assert result.evidence["transaction_count"] == 5
        assert "High transaction velocity detected" in result.reason

    @pytest.mark.asyncio
    async def test_above_threshold_score_scaling(self, base_time):
        # 5 previous + 1 current = 6 -> score = 60 + (6-5)*10 = 70 (HIGH)
        rule = TransactionVelocityRule(window_minutes=10, transaction_threshold=5)
        tx = make_transaction(timestamp=base_time)
        recent = [
            make_previous(f"p{i}", base_time - timedelta(minutes=i))
            for i in range(1, 6)
        ]
        ctx = FraudEvaluationContext(recent_transactions=recent)

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.triggered is True
        assert result.score == 70
        assert result.severity == Severity.HIGH
        assert result.evidence["transaction_count"] == 6

    @pytest.mark.asyncio
    async def test_score_capped_at_100(self, base_time):
        # 10 previous + 1 current = 11 -> score = min(100, 60 + 6*10) = 100 (CRITICAL)
        rule = TransactionVelocityRule(window_minutes=10, transaction_threshold=5)
        tx = make_transaction(timestamp=base_time)
        recent = [
            make_previous(f"p{i}", base_time - timedelta(minutes=i % 8))
            for i in range(1, 11)
        ]
        ctx = FraudEvaluationContext(recent_transactions=recent)

        result = await rule.evaluate(tx, ctx)

        assert result.triggered is True
        assert result.score == 100
        assert result.severity == Severity.CRITICAL

    @pytest.mark.asyncio
    async def test_transactions_outside_window_are_ignored(self, base_time):
        # 3 within window, 2 outside (11m and 20m ago) -> total counted: 3 + 1 = 4 -> CLEAN
        rule = TransactionVelocityRule(window_minutes=10, transaction_threshold=5)
        tx = make_transaction(timestamp=base_time)
        recent = [
            make_previous("p_in1", base_time - timedelta(minutes=2)),
            make_previous("p_in2", base_time - timedelta(minutes=5)),
            make_previous("p_in3", base_time - timedelta(minutes=9)),
            make_previous("p_out1", base_time - timedelta(minutes=11)),
            make_previous("p_out2", base_time - timedelta(minutes=25)),
        ]
        ctx = FraudEvaluationContext(recent_transactions=recent)

        result = await rule.evaluate(tx, ctx)

        assert result.triggered is False
        assert result.evidence["transaction_count"] == 4
        assert "p_out1" not in result.evidence["qualifying_transaction_ids"]
        assert "p_out2" not in result.evidence["qualifying_transaction_ids"]

    @pytest.mark.asyncio
    async def test_future_dated_transactions_are_ignored(self, base_time):
        # 3 within window, 2 in the future relative to current tx -> total counted: 4 -> CLEAN
        rule = TransactionVelocityRule(window_minutes=10, transaction_threshold=5)
        tx = make_transaction(timestamp=base_time)
        recent = [
            make_previous("p1", base_time - timedelta(minutes=2)),
            make_previous("p2", base_time - timedelta(minutes=4)),
            make_previous("p3", base_time - timedelta(minutes=7)),
            make_previous("p_future1", base_time + timedelta(minutes=1)),
            make_previous("p_future2", base_time + timedelta(minutes=10)),
        ]
        ctx = FraudEvaluationContext(recent_transactions=recent)

        result = await rule.evaluate(tx, ctx)

        assert result.triggered is False
        assert result.evidence["transaction_count"] == 4
        assert "p_future1" not in result.evidence["qualifying_transaction_ids"]

    @pytest.mark.asyncio
    async def test_exact_boundary_conditions(self, base_time):
        # Exactly on lower window boundary (base_time - 10 minutes) must be counted
        rule = TransactionVelocityRule(window_minutes=10, transaction_threshold=2)
        tx = make_transaction(timestamp=base_time)
        recent = [
            make_previous("p_exact_lower", base_time - timedelta(minutes=10)),
        ]
        ctx = FraudEvaluationContext(recent_transactions=recent)

        result = await rule.evaluate(tx, ctx)

        assert result.triggered is True
        assert result.evidence["transaction_count"] == 2
        assert "p_exact_lower" in result.evidence["qualifying_transaction_ids"]

    @pytest.mark.asyncio
    async def test_unordered_history_handled_deterministically(self, base_time):
        rule = TransactionVelocityRule(window_minutes=10, transaction_threshold=4)
        tx = make_transaction(timestamp=base_time)
        recent = [
            make_previous("p3", base_time - timedelta(minutes=7)),
            make_previous("p1", base_time - timedelta(minutes=1)),
            make_previous("p4", base_time - timedelta(minutes=9)),
            make_previous("p2", base_time - timedelta(minutes=3)),
        ]
        ctx = FraudEvaluationContext(recent_transactions=recent)

        result1 = await rule.evaluate(tx, ctx)
        # Reverse the input list
        ctx_reversed = FraudEvaluationContext(recent_transactions=list(reversed(recent)))
        result2 = await rule.evaluate(tx, ctx_reversed)

        assert result1.triggered is True
        assert result1.score == result2.score
        assert result1.evidence["qualifying_transaction_ids"] == result2.evidence["qualifying_transaction_ids"]

    def test_invalid_parameters_raise_error(self):
        with pytest.raises(ValueError, match="window_minutes must be positive"):
            TransactionVelocityRule(window_minutes=0)
        with pytest.raises(ValueError, match="transaction_threshold must be positive"):
            TransactionVelocityRule(transaction_threshold=0)

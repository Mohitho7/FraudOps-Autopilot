"""
Unit tests for ImpossibleLocationRule.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest

from app.rules.location import ImpossibleLocationRule
from app.schemas.context import FraudEvaluationContext
from app.schemas.rule import RuleExecutionStatus, Severity
from app.schemas.transaction import PreviousTransaction, Transaction


def make_transaction(
    lat: float = 19.0760,
    lon: float = 72.8777,
    timestamp: datetime = None,
) -> Transaction:
    return Transaction(
        transaction_id="tx-curr",
        customer_id="cust-1",
        merchant_id="merch-1",
        amount=Decimal("500.00"),
        currency="INR",
        timestamp=timestamp or datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc),
        latitude=lat,
        longitude=lon,
    )


def make_previous(
    tx_id: str,
    lat: float,
    lon: float,
    timestamp: datetime,
) -> PreviousTransaction:
    return PreviousTransaction(
        transaction_id=tx_id,
        timestamp=timestamp,
        amount=Decimal("200.00"),
        merchant_id="merch-1",
        latitude=lat,
        longitude=lon,
    )


class TestImpossibleLocationRule:
    @pytest.mark.asyncio
    async def test_same_location_clean(self):
        rule = ImpossibleLocationRule(max_implied_speed_kmh=900.0)
        now = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        tx = make_transaction(lat=19.0760, lon=72.8777, timestamp=now)
        prior = make_previous(
            "p1",
            lat=19.0760,
            lon=72.8777,
            timestamp=now - timedelta(minutes=5),
        )
        ctx = FraudEvaluationContext(recent_transactions=[prior])

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.triggered is False
        assert result.score == 0
        assert result.severity == Severity.NONE
        assert result.evidence["implied_speed_kmh"] == 0.0

    @pytest.mark.asyncio
    async def test_normal_travel_speed_clean(self):
        # 10 km in 30 minutes = 20 km/h (within 900 km/h limit)
        rule = ImpossibleLocationRule(max_implied_speed_kmh=900.0)
        now = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        # Lat offset of approx 0.09 degrees ~ 10 km
        tx = make_transaction(lat=19.0760, lon=72.8777, timestamp=now)
        prior = make_previous(
            "p1",
            lat=18.9860,
            lon=72.8777,
            timestamp=now - timedelta(minutes=30),
        )
        ctx = FraudEvaluationContext(recent_transactions=[prior])

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.triggered is False
        assert result.score == 0
        assert result.severity == Severity.NONE
        assert result.evidence["implied_speed_kmh"] < 50.0

    @pytest.mark.asyncio
    async def test_impossible_travel_triggers(self):
        # Mumbai (19.0760, 72.8777) to Delhi (28.6139, 77.2090) ~ 1148 km in 15 minutes!
        # Implied speed ~ 4590 km/h >> 900 km/h
        rule = ImpossibleLocationRule(max_implied_speed_kmh=900.0)
        now = datetime(2026, 3, 15, 12, 15, 0, tzinfo=timezone.utc)
        tx = make_transaction(lat=28.6139, lon=77.2090, timestamp=now)  # Delhi
        prior = make_previous(
            "p1",
            lat=19.0760,
            lon=72.8777,  # Mumbai
            timestamp=now - timedelta(minutes=15),
        )
        ctx = FraudEvaluationContext(recent_transactions=[prior])

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.triggered is True
        assert result.score >= 90
        assert result.severity == Severity.CRITICAL
        assert result.evidence["implied_speed_kmh"] > 4000.0
        assert "Impossible travel detected" in result.reason

    @pytest.mark.asyncio
    async def test_strict_greater_than_boundary(self):
        rule = ImpossibleLocationRule(max_implied_speed_kmh=100.0)
        now = datetime(2026, 3, 15, 13, 0, 0, tzinfo=timezone.utc)
        # Prior is 1 hour ago
        # Let's mock a distance of approx 100 km (0.9 degrees latitude ~ 100.07 km)
        tx = make_transaction(lat=10.9000, lon=70.0000, timestamp=now)
        prior = make_previous(
            "p1",
            lat=10.0000,
            lon=70.0000,
            timestamp=now - timedelta(hours=1),
        )
        ctx = FraudEvaluationContext(recent_transactions=[prior])

        # Distance is ~ 100.07 km in 1.0 h -> speed = 100.07 km/h > 100.0 km/h -> triggers
        result = await rule.evaluate(tx, ctx)
        assert result.triggered is True

        # Now test with threshold set to 150.0 km/h -> speed 100.07 <= 150 -> clean
        rule_lenient = ImpossibleLocationRule(max_implied_speed_kmh=150.0)
        result_lenient = await rule_lenient.evaluate(tx, ctx)
        assert result_lenient.triggered is False

    @pytest.mark.asyncio
    async def test_missing_current_coordinates(self):
        rule = ImpossibleLocationRule(max_implied_speed_kmh=900.0)
        tx = Transaction(
            transaction_id="tx-curr",
            customer_id="c1",
            merchant_id="m1",
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc),
            latitude=None,
            longitude=None,
        )
        prior = make_previous("p1", 19.0, 72.0, datetime(2026, 3, 15, 11, 0, 0, tzinfo=timezone.utc))
        ctx = FraudEvaluationContext(recent_transactions=[prior])

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.triggered is False
        assert result.score == 0
        assert result.severity == Severity.NONE
        assert result.evidence["missing_location_data"] is True

    @pytest.mark.asyncio
    async def test_missing_previous_coordinates(self):
        rule = ImpossibleLocationRule(max_implied_speed_kmh=900.0)
        now = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        tx = make_transaction(timestamp=now)
        prior = PreviousTransaction(
            transaction_id="p1",
            timestamp=now - timedelta(minutes=10),
            amount=Decimal("100.00"),
            merchant_id="m1",
            latitude=None,
            longitude=None,
        )
        ctx = FraudEvaluationContext(recent_transactions=[prior])

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.triggered is False
        assert result.score == 0
        assert result.evidence["missing_location_data"] is True

    @pytest.mark.asyncio
    async def test_no_previous_history(self):
        rule = ImpossibleLocationRule(max_implied_speed_kmh=900.0)
        tx = make_transaction()
        ctx = FraudEvaluationContext()

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.triggered is False
        assert result.evidence["missing_location_data"] is True

    @pytest.mark.asyncio
    async def test_zero_elapsed_time(self):
        rule = ImpossibleLocationRule(max_implied_speed_kmh=900.0)
        now = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        tx = make_transaction(lat=19.0760, lon=72.8777, timestamp=now)
        # Prior has identical timestamp
        prior = make_previous("p1", lat=28.6139, lon=77.2090, timestamp=now)
        ctx = FraudEvaluationContext(recent_transactions=[prior])

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.triggered is False
        assert result.score == 0
        assert "Non-positive elapsed time" in result.reason

    @pytest.mark.asyncio
    async def test_future_dated_history_ignored(self):
        rule = ImpossibleLocationRule(max_implied_speed_kmh=900.0)
        now = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        tx = make_transaction(timestamp=now)
        # Prior is in the future
        prior = make_previous("p_future", lat=28.6139, lon=77.2090, timestamp=now + timedelta(hours=1))
        ctx = FraudEvaluationContext(recent_transactions=[prior])

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.triggered is False
        assert result.evidence["missing_location_data"] is True

    @pytest.mark.asyncio
    async def test_unordered_history_selects_most_recent(self):
        # 3 historical transactions:
        # p1: 2 hours ago, Delhi
        # p2: 10 minutes ago, same city as current tx (Mumbai)
        # p3: 4 hours ago, London
        # Passed in random order. Rule must pick p2 (10 mins ago, same city), so speed is low.
        rule = ImpossibleLocationRule(max_implied_speed_kmh=900.0)
        now = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        tx = make_transaction(lat=19.0760, lon=72.8777, timestamp=now)
        recent = [
            make_previous("p3", 51.5074, -0.1278, now - timedelta(hours=4)),
            make_previous("p1", 28.6139, 77.2090, now - timedelta(hours=2)),
            make_previous("p2", 19.0760, 72.8777, now - timedelta(minutes=10)),
        ]
        ctx = FraudEvaluationContext(recent_transactions=recent)

        result = await rule.evaluate(tx, ctx)

        assert result.evidence["previous_transaction_id"] == "p2"
        assert result.triggered is False
        assert result.score == 0

    def test_invalid_config_raises_error(self):
        with pytest.raises(ValueError, match="max_implied_speed_kmh must be positive"):
            ImpossibleLocationRule(max_implied_speed_kmh=0.0)

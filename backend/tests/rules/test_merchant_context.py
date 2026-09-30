"""
Unit tests for MerchantContextRule.
Includes mandatory contextual differentiation test across business domains.
"""

from datetime import datetime, timezone
from decimal import Decimal
import pytest

from app.rules.merchant_context import MerchantContextRule
from app.schemas.context import FraudEvaluationContext
from app.schemas.merchant import Merchant, MerchantStatistics, OperatingHours
from app.schemas.rule import RuleExecutionStatus, Severity
from app.schemas.transaction import Transaction


def make_transaction(
    amount: str = "60000.00",
    merchant_id: str = "merch-1",
    timestamp: datetime = None,
) -> Transaction:
    return Transaction(
        transaction_id="tx-curr",
        customer_id="cust-1",
        merchant_id=merchant_id,
        amount=Decimal(amount),
        currency="INR",
        timestamp=timestamp or datetime(2026, 3, 15, 14, 0, 0, tzinfo=timezone.utc),
    )


class TestMerchantContextRule:
    @pytest.mark.asyncio
    async def test_mandatory_contextual_differentiation(self):
        """
        MANDATORY TEST: Proves contextual differentiation.
        Merchant A: Jewellery, p95 = 75,000
        Merchant B: Fuel Station, p95 = 20,000
        Same transaction: amount = 60,000
        Expected:
        Merchant A: clean (60k <= 75k)
        Merchant B: triggered (60k > 20k)
        """
        rule = MerchantContextRule()
        tx = make_transaction(amount="60000.00")

        # Merchant A (Jewellery)
        merchant_a = Merchant(
            merchant_id="jewel-1",
            merchant_name="Royal Jewellers",
            category="JEWELRY",
            statistics=MerchantStatistics(
                p50=Decimal("30000.00"),
                p95=Decimal("75000.00"),
                p99=Decimal("150000.00"),
            ),
        )
        ctx_a = FraudEvaluationContext(merchant_context=merchant_a)

        # Merchant B (Fuel)
        merchant_b = Merchant(
            merchant_id="fuel-1",
            merchant_name="City Fuel Station",
            category="FUEL",
            statistics=MerchantStatistics(
                p50=Decimal("3000.00"),
                p95=Decimal("20000.00"),
                p99=Decimal("35000.00"),
            ),
        )
        ctx_b = FraudEvaluationContext(merchant_context=merchant_b)

        result_a = await rule.evaluate(tx, ctx_a)
        result_b = await rule.evaluate(tx, ctx_b)

        # Merchant A must be CLEAN
        assert result_a.status == RuleExecutionStatus.SUCCESS
        assert result_a.triggered is False
        assert result_a.score == 0
        assert result_a.severity == Severity.NONE
        assert result_a.evidence["baseline_type"] == "p95"
        assert result_a.evidence["baseline_value"] == "75000.00"

        # Merchant B must be TRIGGERED
        assert result_b.status == RuleExecutionStatus.SUCCESS
        assert result_b.triggered is True
        assert result_b.score >= 85  # 60k > p99 (35k) -> strong anomaly
        assert result_b.severity in (Severity.HIGH, Severity.CRITICAL)
        assert result_b.evidence["baseline_type"] == "p95"
        assert result_b.evidence["baseline_value"] == "20000.00"

    @pytest.mark.asyncio
    async def test_below_p95_clean(self):
        rule = MerchantContextRule()
        tx = make_transaction(amount="4000.00")
        stats = MerchantStatistics(p95=Decimal("5000.00"), p99=Decimal("10000.00"))
        ctx = FraudEvaluationContext(merchant_statistics=stats)

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.triggered is False
        assert result.score == 0
        assert result.severity == Severity.NONE
        assert result.evidence["baseline_type"] == "p95"

    @pytest.mark.asyncio
    async def test_above_p95_below_p99_triggers_medium_high(self):
        rule = MerchantContextRule()
        tx = make_transaction(amount="7000.00")
        stats = MerchantStatistics(p95=Decimal("5000.00"), p99=Decimal("10000.00"))
        ctx = FraudEvaluationContext(merchant_statistics=stats)

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.triggered is True
        assert 65 <= result.score < 85
        assert result.severity == Severity.MEDIUM or result.severity == Severity.HIGH
        assert result.evidence["baseline_type"] == "p95"

    @pytest.mark.asyncio
    async def test_above_p99_triggers_strong_anomaly(self):
        rule = MerchantContextRule()
        tx = make_transaction(amount="15000.00")
        stats = MerchantStatistics(p95=Decimal("5000.00"), p99=Decimal("10000.00"))
        ctx = FraudEvaluationContext(merchant_statistics=stats)

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.triggered is True
        assert result.score >= 85
        assert result.severity in (Severity.HIGH, Severity.CRITICAL)

    @pytest.mark.asyncio
    async def test_p95_unavailable_uses_p99(self):
        rule = MerchantContextRule()
        tx = make_transaction(amount="12000.00")
        stats = MerchantStatistics(p95=None, p99=Decimal("10000.00"))
        ctx = FraudEvaluationContext(merchant_statistics=stats)

        result = await rule.evaluate(tx, ctx)

        assert result.status == RuleExecutionStatus.SUCCESS
        assert result.triggered is True
        assert result.evidence["baseline_type"] == "p99"
        assert result.evidence["baseline_value"] == "10000.00"

    @pytest.mark.asyncio
    async def test_p95_and_p99_unavailable_uses_p50_fallback(self):
        rule = MerchantContextRule(fallback_multiplier=3.0)
        stats = MerchantStatistics(p50=Decimal("1000.00"))
        ctx = FraudEvaluationContext(merchant_statistics=stats)

        # 2500 <= 3 * 1000 -> clean
        tx_clean = make_transaction(amount="2500.00")
        res_clean = await rule.evaluate(tx_clean, ctx)
        assert res_clean.triggered is False
        assert res_clean.evidence["baseline_type"] == "p50"

        # 4000 > 3 * 1000 -> triggered
        tx_trig = make_transaction(amount="4000.00")
        res_trig = await rule.evaluate(tx_trig, ctx)
        assert res_trig.triggered is True
        assert res_trig.score >= 65
        assert res_trig.evidence["baseline_type"] == "p50"

    @pytest.mark.asyncio
    async def test_only_average_available_uses_average_fallback(self):
        rule = MerchantContextRule(fallback_multiplier=3.0)
        stats = MerchantStatistics(average_transaction_amount=Decimal("500.00"))
        ctx = FraudEvaluationContext(merchant_statistics=stats)

        # 2000 > 3 * 500 = 1500 -> triggered
        tx = make_transaction(amount="2000.00")
        res = await rule.evaluate(tx, ctx)

        assert res.status == RuleExecutionStatus.SUCCESS
        assert res.triggered is True
        assert res.evidence["baseline_type"] == "average"
        assert res.evidence["baseline_value"] == "500.00"

    @pytest.mark.asyncio
    async def test_no_statistics_returns_clean(self):
        rule = MerchantContextRule()
        tx = make_transaction(amount="50000.00")
        ctx = FraudEvaluationContext()

        res = await rule.evaluate(tx, ctx)

        assert res.status == RuleExecutionStatus.SUCCESS
        assert res.triggered is False
        assert res.score == 0
        assert res.severity == Severity.NONE
        assert res.evidence["insufficient_merchant_statistics"] is True

    @pytest.mark.asyncio
    async def test_operating_hours_evaluated_in_evidence(self):
        rule = MerchantContextRule()
        now = datetime(2026, 3, 15, 23, 30, tzinfo=timezone.utc)
        tx = make_transaction(amount="100.00", timestamp=now)
        merchant = Merchant(
            merchant_id="m1",
            merchant_name="Day Shop",
            category="RETAIL",
            operating_hours=OperatingHours(start_time="09:00", end_time="18:00", timezone="UTC"),
            statistics=MerchantStatistics(p95=Decimal("500.00")),
        )
        ctx = FraudEvaluationContext(merchant_context=merchant)

        res = await rule.evaluate(tx, ctx)

        assert res.evidence["operating_hours_status"] == "OUTSIDE_HOURS"
        assert res.evidence["within_operating_hours"] is False

    @pytest.mark.asyncio
    async def test_deterministic_repeatability(self):
        rule = MerchantContextRule()
        tx = make_transaction(amount="12000.00")
        stats = MerchantStatistics(p95=Decimal("5000.00"), p99=Decimal("10000.00"))
        ctx = FraudEvaluationContext(merchant_statistics=stats)

        r1 = await rule.evaluate(tx, ctx)
        r2 = await rule.evaluate(tx, ctx)

        assert r1.triggered == r2.triggered
        assert r1.score == r2.score
        assert r1.severity == r2.severity
        assert r1.evidence == r2.evidence

    def test_invalid_config_raises_error(self):
        with pytest.raises(ValueError, match="fallback_multiplier must be greater than 1.0"):
            MerchantContextRule(fallback_multiplier=1.0)

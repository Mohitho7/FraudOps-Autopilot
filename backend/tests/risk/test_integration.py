"""
End-to-end integration tests connecting RuleRegistry, RuleEngine, and RiskEngine.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest

from app.risk import RiskConfiguration, RiskEngine, RiskEvaluationStatus, RiskLevel
from app.rules import (
    RuleEngine,
    RuleExecutionStatus,
    RuleRegistry,
    create_default_rule_registry,
)
from app.schemas.context import FraudEvaluationContext
from app.schemas.merchant import Merchant, MerchantStatistics, OperatingHours
from app.schemas.transaction import PreviousTransaction, Transaction


@pytest.fixture
def base_time():
    return datetime(2026, 3, 15, 14, 0, 0, tzinfo=timezone.utc)


class TestRiskEngineEndToEndIntegration:
    @pytest.mark.asyncio
    async def test_full_pipeline_clean_transaction(self, base_time):
        """
        End-to-end execution of a clean transaction:
        RuleEngine executes all 4 Batch 3 rules -> RiskEngine aggregates -> FraudEvaluation.
        """
        registry = create_default_rule_registry()
        rule_engine = RuleEngine(registry=registry)
        risk_engine = RiskEngine()

        tx = Transaction(
            transaction_id="tx_clean_e2e",
            customer_id="cust-1",
            merchant_id="merch-grocer",
            amount=Decimal("1200.00"),
            currency="INR",
            timestamp=base_time,
            latitude=19.0760,
            longitude=72.8777,
        )

        recent = [
            PreviousTransaction(
                transaction_id="pt1",
                timestamp=base_time - timedelta(hours=2),
                amount=Decimal("1100.00"),
                merchant_id="merch-grocer",
                latitude=19.0750,
                longitude=72.8770,
            ),
            PreviousTransaction(
                transaction_id="pt2",
                timestamp=base_time - timedelta(days=1),
                amount=Decimal("1300.00"),
                merchant_id="merch-grocer",
                latitude=19.0760,
                longitude=72.8777,
            ),
            PreviousTransaction(
                transaction_id="pt3",
                timestamp=base_time - timedelta(days=2),
                amount=Decimal("1250.00"),
                merchant_id="merch-grocer",
                latitude=19.0760,
                longitude=72.8777,
            ),
        ]

        merchant = Merchant(
            merchant_id="merch-grocer",
            merchant_name="Fresh Mart",
            category="GROCERY",
            operating_hours=OperatingHours(start_time="08:00", end_time="22:00", timezone="UTC"),
            statistics=MerchantStatistics(
                p50=Decimal("1000.00"),
                p95=Decimal("3000.00"),
                p99=Decimal("5000.00"),
            ),
        )

        context = FraudEvaluationContext(
            recent_transactions=recent,
            merchant_context=merchant,
        )

        # 1. Rule Engine execution
        raw_evaluation = await rule_engine.evaluate_transaction(tx, context)
        assert len(raw_evaluation.rule_results) == 4
        assert raw_evaluation.risk_score is None

        # 2. Risk Engine aggregation
        final_evaluation = risk_engine.evaluate_evaluation(raw_evaluation)

        # 3. Verification of synthesized case risk
        assert final_evaluation.transaction_id == "tx_clean_e2e"
        assert final_evaluation.risk_score == 0
        assert final_evaluation.risk_level == RiskLevel.LOW.value
        assert final_evaluation.evaluation_status == RiskEvaluationStatus.COMPLETE.value
        assert final_evaluation.coverage_ratio == 1.0
        assert len(final_evaluation.triggered_rules) == 0
        assert len(final_evaluation.clean_rules) == 4
        assert len(final_evaluation.failed_rules) == 0

    @pytest.mark.asyncio
    async def test_full_pipeline_multi_anomaly_transaction(self, base_time):
        """
        End-to-end execution of a highly anomalous transaction:
        - Velocity: 6 txs in 10m -> score 70 (wt: 0.20) -> 14.0
        - Amount: 95,000 / 2,000 = 47.5x -> score 100 (wt: 0.25) -> 25.0
        - Location: Mumbai to Delhi in 1 min -> score 100 (wt: 0.30) -> 30.0
        - Merchant: 95,000 > p99 (25,000) for fuel -> score >= 85 (wt: 0.25)
        """
        registry = create_default_rule_registry()
        rule_engine = RuleEngine(registry=registry)
        risk_engine = RiskEngine()

        tx = Transaction(
            transaction_id="tx_fraud_e2e",
            customer_id="cust-1",
            merchant_id="merch-fuel",
            amount=Decimal("95000.00"),
            currency="INR",
            timestamp=base_time,
            latitude=28.6139,
            longitude=77.2090,  # Delhi
        )

        # 5 recent transactions within 10 minutes from Mumbai (19.0760, 72.8777)
        recent = [
            PreviousTransaction(
                transaction_id=f"pt_{i}",
                timestamp=base_time - timedelta(minutes=i),
                amount=Decimal("2000.00"),
                merchant_id="merch-fuel",
                latitude=19.0760,
                longitude=72.8777,
            )
            for i in range(1, 6)
        ]

        merchant = Merchant(
            merchant_id="merch-fuel",
            merchant_name="Highway Fuel",
            category="FUEL",
            statistics=MerchantStatistics(
                p50=Decimal("1500.00"),
                p95=Decimal("10000.00"),
                p99=Decimal("25000.00"),
            ),
        )

        context = FraudEvaluationContext(
            recent_transactions=recent,
            merchant_context=merchant,
        )

        # Execute full pipeline
        raw_evaluation = await rule_engine.evaluate_transaction(tx, context)
        final_evaluation = risk_engine.evaluate_evaluation(raw_evaluation)

        assert final_evaluation.risk_score is not None
        assert final_evaluation.risk_score >= 85
        assert final_evaluation.risk_level in (RiskLevel.HIGH.value, RiskLevel.CRITICAL.value)
        assert final_evaluation.evaluation_status == RiskEvaluationStatus.COMPLETE.value
        assert len(final_evaluation.triggered_rules) == 4
        assert len(final_evaluation.clean_rules) == 0

    @pytest.mark.asyncio
    async def test_full_pipeline_with_rule_execution_error(self, base_time):
        """
        Verify pipeline behavior when a rule crashes under fail_fast=False:
        RuleEngine produces status=ERROR -> RiskEngine excludes it from available weight
        -> evaluation_status=PARTIAL -> coverage < 1.0.
        """
        from app.rules.base import FraudRule

        class CrashingLocationRule(FraudRule):
            rule_id = "impossible_location"
            rule_name = "Crashing Location Rule"

            async def evaluate(self, transaction, context):
                raise RuntimeError("Hardware GPS sensor timeout")

        registry = RuleRegistry()
        from app.rules import (
            MerchantContextRule,
            TransactionVelocityRule,
            UnusualAmountRule,
        )
        registry.register(TransactionVelocityRule())
        registry.register(UnusualAmountRule())
        registry.register(CrashingLocationRule())
        registry.register(MerchantContextRule())

        rule_engine = RuleEngine(registry=registry, fail_fast=False)
        risk_engine = RiskEngine()

        tx = Transaction(
            transaction_id="tx_error_resilience",
            customer_id="cust-1",
            merchant_id="m1",
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=base_time,
        )
        context = FraudEvaluationContext()

        raw_evaluation = await rule_engine.evaluate_transaction(tx, context)
        final_evaluation = risk_engine.evaluate_evaluation(raw_evaluation)

        assert final_evaluation.evaluation_status == RiskEvaluationStatus.PARTIAL.value
        assert final_evaluation.coverage_ratio == 0.70  # 1.0 - 0.30 = 0.70
        assert final_evaluation.failed_rules == ["impossible_location"]
        assert len(final_evaluation.clean_rules) == 3  # velocity, amount, merchant
        assert final_evaluation.risk_score == 0
        assert final_evaluation.risk_level == RiskLevel.LOW.value

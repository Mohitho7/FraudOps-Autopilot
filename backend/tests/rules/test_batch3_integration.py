"""
Integration tests for Batch 3 deterministic fraud rules executing through RuleEngine.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest

from app.rules import (
    ImpossibleLocationRule,
    MerchantContextRule,
    RuleEngine,
    RuleExecutionStatus,
    RuleRegistry,
    Severity,
    TransactionVelocityRule,
    UnusualAmountRule,
    create_default_rule_registry,
)
from app.schemas.context import FraudEvaluationContext
from app.schemas.merchant import Merchant, MerchantStatistics, OperatingHours
from app.schemas.transaction import PreviousTransaction, Transaction


@pytest.fixture
def base_time():
    return datetime(2026, 3, 15, 14, 0, 0, tzinfo=timezone.utc)


class TestBatch3RuleEngineIntegration:
    @pytest.mark.asyncio
    async def test_all_four_rules_registered_and_evaluated_clean(self, base_time):
        """
        Verify all 4 rules run through RuleEngine and evaluate as clean on a normal transaction.
        """
        registry = create_default_rule_registry()
        assert len(registry) == 4

        engine = RuleEngine(registry=registry)

        tx = Transaction(
            transaction_id="tx-normal",
            customer_id="cust-100",
            merchant_id="merch-grocer",
            amount=Decimal("1500.00"),
            currency="INR",
            timestamp=base_time,
            latitude=19.0760,
            longitude=72.8777,
        )

        recent_txs = [
            PreviousTransaction(
                transaction_id="p1",
                timestamp=base_time - timedelta(minutes=45),
                amount=Decimal("1200.00"),
                merchant_id="merch-grocer",
                latitude=19.0750,
                longitude=72.8770,
            ),
            PreviousTransaction(
                transaction_id="p2",
                timestamp=base_time - timedelta(days=1),
                amount=Decimal("1500.00"),
                merchant_id="merch-grocer",
                latitude=19.0760,
                longitude=72.8777,
            ),
            PreviousTransaction(
                transaction_id="p3",
                timestamp=base_time - timedelta(days=2),
                amount=Decimal("1800.00"),
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
                p95=Decimal("3500.00"),
                p99=Decimal("6000.00"),
            ),
        )

        context = FraudEvaluationContext(
            recent_transactions=recent_txs,
            merchant_context=merchant,
        )

        evaluation = await engine.evaluate_transaction(tx, context)

        assert evaluation.transaction_id == "tx-normal"
        assert len(evaluation.rule_results) == 4

        rule_ids = {r.rule_id for r in evaluation.rule_results}
        assert rule_ids == {
            "transaction_velocity",
            "unusual_amount",
            "impossible_location",
            "merchant_context",
        }

        # All four rules must execute successfully with clean outcome
        for res in evaluation.rule_results:
            assert res.status == RuleExecutionStatus.SUCCESS
            assert res.triggered is False
            assert res.score == 0
            assert res.severity == Severity.NONE
            assert res.execution_time_ms is not None
            assert isinstance(res.evidence, dict)

    @pytest.mark.asyncio
    async def test_all_four_rules_triggered_simultaneously(self, base_time):
        """
        Verify multi-rule anomaly scenario where all 4 rules trigger with valid scores and evidence.
        """
        registry = create_default_rule_registry()
        engine = RuleEngine(registry=registry)

        # Current transaction:
        # Amount: 95,000 (huge!)
        # Location: Delhi (28.6139, 77.2090)
        # Time: base_time
        tx = Transaction(
            transaction_id="tx-fraud",
            customer_id="cust-100",
            merchant_id="merch-fuel",
            amount=Decimal("95000.00"),
            currency="INR",
            timestamp=base_time,
            latitude=28.6139,
            longitude=77.2090,
        )

        # 5 recent transactions within 10 minutes from Mumbai (19.0760, 72.8777)
        # Previous median amounts around 2,000
        recent_txs = [
            PreviousTransaction(
                transaction_id=f"pt-{i}",
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
            merchant_name="Highway Petrol",
            category="FUEL",
            statistics=MerchantStatistics(
                p50=Decimal("1500.00"),
                p95=Decimal("10000.00"),
                p99=Decimal("25000.00"),
            ),
        )

        context = FraudEvaluationContext(
            recent_transactions=recent_txs,
            merchant_context=merchant,
        )

        evaluation = await engine.evaluate_transaction(tx, context)

        results_by_id = {r.rule_id: r for r in evaluation.rule_results}
        assert len(results_by_id) == 4

        # 1. Velocity: 6 txs in 10 mins (threshold 5) -> triggered
        vel = results_by_id["transaction_velocity"]
        assert vel.triggered is True
        assert vel.status == RuleExecutionStatus.SUCCESS
        assert vel.score >= 60

        # 2. Amount: 95,000 / 2,000 = 47.5x median -> triggered
        amt = results_by_id["unusual_amount"]
        assert amt.triggered is True
        assert amt.status == RuleExecutionStatus.SUCCESS
        assert amt.score == 100

        # 3. Location: Mumbai to Delhi (1150 km) in 1 minute -> triggered
        loc = results_by_id["impossible_location"]
        assert loc.triggered is True
        assert loc.status == RuleExecutionStatus.SUCCESS
        assert loc.score >= 90

        # 4. Merchant context: 95,000 > p99 (25,000) for Fuel -> triggered
        merch = results_by_id["merchant_context"]
        assert merch.triggered is True
        assert merch.status == RuleExecutionStatus.SUCCESS
        assert merch.score >= 85

    @pytest.mark.asyncio
    async def test_rule_failure_not_masked_as_clean_or_success(self, base_time):
        """
        Verify that an unhandled crash in a rule produces status=ERROR and is NOT masked as clean.
        """
        from app.rules.base import FraudRule

        class CrashingRule(FraudRule):
            rule_id = "crashing_rule"
            rule_name = "Crashing Rule"

            async def evaluate(self, transaction, context):
                raise RuntimeError("Simulated internal rule failure")

        registry = RuleRegistry()
        registry.register(TransactionVelocityRule())
        registry.register(CrashingRule())

        engine = RuleEngine(registry=registry, fail_fast=False)

        tx = Transaction(
            transaction_id="tx-test",
            customer_id="c1",
            merchant_id="m1",
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=base_time,
        )
        context = FraudEvaluationContext()

        evaluation = await engine.evaluate_transaction(tx, context)

        results = {r.rule_id: r for r in evaluation.rule_results}
        assert results["transaction_velocity"].status == RuleExecutionStatus.SUCCESS
        assert results["transaction_velocity"].triggered is False

        assert results["crashing_rule"].status == RuleExecutionStatus.ERROR
        assert results["crashing_rule"].triggered is False
        assert "Simulated internal rule failure" in results["crashing_rule"].reason

    def test_registry_isolation(self):
        """
        Verify that factory-created registries are independent instances.
        """
        reg1 = create_default_rule_registry()
        reg2 = create_default_rule_registry()

        assert reg1 is not reg2
        assert len(reg1) == 4
        assert len(reg2) == 4

        reg1.unregister("transaction_velocity")
        assert len(reg1) == 3
        assert len(reg2) == 4

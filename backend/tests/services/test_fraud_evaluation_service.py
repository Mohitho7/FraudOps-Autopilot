"""
Unit tests for FraudEvaluationService application service (Batch 6).
Verifies orchestration across ContextService, RuleEngine, RiskEngine, and EvaluationStore.
"""

from datetime import datetime, timezone
from decimal import Decimal
import pytest

from app.repositories.context_provider import InMemoryContextProvider
from app.repositories.evaluation_store import InMemoryEvaluationStore
from app.risk.engine import RiskEngine
from app.rules.base import FraudRule
from app.rules.engine import RuleEngine
from app.rules.registry import RuleRegistry, create_default_rule_registry
from app.schemas.context import FraudEvaluationContext
from app.schemas.customer import CustomerContext
from app.schemas.evaluation import FraudEvaluation, RiskEvaluationStatus, RiskLevel
from app.schemas.merchant import Merchant, MerchantStatistics
from app.schemas.rule import RuleExecutionStatus, RuleResult, Severity
from app.schemas.transaction import PreviousTransaction, Transaction
from app.services.context_service import ContextService
from app.services.exceptions import ContextRetrievalError
from app.services.fraud_evaluation_service import FraudEvaluationService


def make_transaction(
    tx_id: str = "tx-eval-1",
    amount: str = "10000.00",
    customer_id: str = "cust-1",
    merchant_id: str = "merch-1",
) -> Transaction:
    return Transaction(
        transaction_id=tx_id,
        customer_id=customer_id,
        merchant_id=merchant_id,
        amount=Decimal(amount),
        currency="INR",
        timestamp=datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc),
    )


class TestFraudEvaluationService:
    @pytest.mark.asyncio
    async def test_successful_orchestration_clean_transaction(self):
        provider = InMemoryContextProvider()
        store = InMemoryEvaluationStore()
        context_service = ContextService(provider=provider)
        service = FraudEvaluationService(context_service=context_service, evaluation_store=store)

        tx = make_transaction()
        evaluation = await service.evaluate(tx)

        assert isinstance(evaluation, FraudEvaluation)
        assert evaluation.transaction_id == "tx-eval-1"
        assert evaluation.risk_score == 0
        assert evaluation.risk_level == RiskLevel.LOW.value
        assert evaluation.evaluation_status == RiskEvaluationStatus.COMPLETE.value
        assert evaluation.coverage_ratio == 1.0
        assert len(evaluation.rule_results) == 4
        assert len(evaluation.clean_rules) == 4
        assert len(evaluation.triggered_rules) == 0
        assert len(evaluation.failed_rules) == 0

        # Verified stored
        stored = await service.get_evaluation("tx-eval-1")
        assert stored is not None
        assert stored.transaction_id == "tx-eval-1"

    @pytest.mark.asyncio
    async def test_successful_orchestration_high_risk_transaction(self):
        # Trigger amount anomaly: baseline median = 1,000, current = 50,000 (50x multiplier)
        provider = InMemoryContextProvider()
        t_curr = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        history = [
            PreviousTransaction(
                transaction_id=f"pt-{i}",
                timestamp=datetime(2026, 3, 15, 10, i, 0, tzinfo=timezone.utc),
                amount=Decimal("1000.00"),
                merchant_id="merch-1",
            )
            for i in range(1, 5)
        ]
        provider.set_transaction_history("cust-1", history)

        context_service = ContextService(provider=provider)
        service = FraudEvaluationService(context_service=context_service)

        tx = make_transaction(amount="50000.00")
        evaluation = await service.evaluate(tx)

        assert evaluation.transaction_id == "tx-eval-1"
        assert evaluation.risk_score > 0
        assert "unusual_amount" in evaluation.triggered_rules
        assert evaluation.evaluation_status == RiskEvaluationStatus.COMPLETE.value

    @pytest.mark.asyncio
    async def test_context_retrieval_failure_propagates_unconverted(self):
        class FailingProvider(InMemoryContextProvider):
            async def get_customer_context(self, customer_id: str):
                raise RuntimeError("Database connection pool exhausted")

        context_service = ContextService(provider=FailingProvider())
        service = FraudEvaluationService(context_service=context_service)

        tx = make_transaction()
        with pytest.raises(ContextRetrievalError, match="Database connection pool exhausted"):
            await service.evaluate(tx)

    @pytest.mark.asyncio
    async def test_partial_rule_failure_returns_partial_status(self):
        # Register a broken rule alongside default rules
        class CrashingRule(FraudRule):
            rule_id = "crashing_rule"
            rule_name = "Crashing Rule"

            async def evaluate(self, transaction, context):
                raise ZeroDivisionError("Simulated crash")

        from app.risk.config import RiskConfiguration

        registry = create_default_rule_registry()
        registry.register(CrashingRule())

        # Weights including the crashing rule
        weights = {
            "transaction_velocity": Decimal("0.20"),
            "unusual_amount": Decimal("0.20"),
            "impossible_location": Decimal("0.20"),
            "merchant_context": Decimal("0.20"),
            "crashing_rule": Decimal("0.20"),
        }
        risk_config = RiskConfiguration(rule_weights=weights, require_all_batch3_rules=False)
        risk_engine = RiskEngine(config=risk_config)
        rule_engine = RuleEngine(registry=registry)

        provider = InMemoryContextProvider()
        context_service = ContextService(provider=provider)
        service = FraudEvaluationService(
            context_service=context_service,
            rule_engine=rule_engine,
            risk_engine=risk_engine,
        )

        tx = make_transaction()
        evaluation = await service.evaluate(tx)

        assert evaluation.evaluation_status == RiskEvaluationStatus.PARTIAL.value
        assert "crashing_rule" in evaluation.failed_rules
        assert evaluation.coverage_ratio == 0.80

    @pytest.mark.asyncio
    async def test_deterministic_repeatability_of_service(self):
        provider = InMemoryContextProvider()
        context_service = ContextService(provider=provider)
        service = FraudEvaluationService(context_service=context_service)

        tx = make_transaction()
        e1 = await service.evaluate(tx)
        e2 = await service.evaluate(tx)

        assert e1.risk_score == e2.risk_score
        assert e1.risk_level == e2.risk_level
        assert e1.evaluation_status == e2.evaluation_status
        assert e1.coverage_ratio == e2.coverage_ratio
        assert e1.triggered_rules == e2.triggered_rules
        assert e1.clean_rules == e2.clean_rules
        assert e1.failed_rules == e2.failed_rules

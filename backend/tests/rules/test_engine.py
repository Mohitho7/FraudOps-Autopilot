"""
Tests for RuleEngine execution, failure handling, and extensibility.
"""

from datetime import datetime, timezone
from decimal import Decimal
import pytest

from app.rules.base import FraudRule
from app.rules.engine import RuleEngine
from app.rules.exceptions import RuleExecutionError
from app.rules.registry import RuleRegistry
from app.schemas.context import FraudEvaluationContext
from app.schemas.evaluation import FraudEvaluation
from app.schemas.rule import RuleExecutionStatus, RuleResult, Severity
from app.schemas.transaction import Transaction
from tests.rules.doubles import DummyCleanRule, DummyFailingRule, DummyTriggeredRule


@pytest.fixture
def sample_transaction() -> Transaction:
    return Transaction(
        transaction_id="tx_test_001",
        customer_id="cust_test_001",
        merchant_id="merch_test_001",
        amount=Decimal("4999.99"),
        currency="INR",
        timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_context() -> FraudEvaluationContext:
    return FraudEvaluationContext(metadata={"test_run": True})


@pytest.mark.asyncio
async def test_engine_executes_registered_rule(sample_transaction, sample_context):
    registry = RuleRegistry()
    rule = DummyTriggeredRule(score=25, severity=Severity.MEDIUM)
    registry.register(rule)

    engine = RuleEngine(registry=registry)
    results = await engine.evaluate_all(sample_transaction, sample_context)

    assert len(results) == 1
    assert results[0].rule_id == "test_dummy_triggered"
    assert results[0].triggered is True
    assert results[0].score == 25
    assert results[0].severity == Severity.MEDIUM
    assert results[0].execution_time_ms is not None
    assert results[0].evidence["dummy_key"] == "dummy_value"


@pytest.mark.asyncio
async def test_engine_handles_multiple_rules_in_order(sample_transaction, sample_context):
    registry = RuleRegistry()
    r1 = DummyCleanRule()
    r2 = DummyTriggeredRule(score=10, severity=Severity.LOW)
    registry.register(r1)
    registry.register(r2)

    engine = RuleEngine(registry=registry)
    results = await engine.evaluate_all(sample_transaction, sample_context)

    assert len(results) == 2
    assert results[0].rule_id == "test_dummy_clean"
    assert results[0].triggered is False
    assert results[1].rule_id == "test_dummy_triggered"
    assert results[1].triggered is True


@pytest.mark.asyncio
async def test_engine_handles_no_registered_rules(sample_transaction, sample_context):
    registry = RuleRegistry()
    engine = RuleEngine(registry=registry)
    results = await engine.evaluate_all(sample_transaction, sample_context)

    assert results == []


@pytest.mark.asyncio
async def test_engine_skips_disabled_rules(sample_transaction, sample_context):
    registry = RuleRegistry()
    r1 = DummyTriggeredRule()
    r2 = DummyCleanRule()
    r2.is_enabled = False  # Disabled
    registry.register(r1)
    registry.register(r2)

    engine = RuleEngine(registry=registry)
    results = await engine.evaluate_all(sample_transaction, sample_context)

    assert len(results) == 1
    assert results[0].rule_id == "test_dummy_triggered"


@pytest.mark.asyncio
async def test_engine_handles_rule_failure_gracefully_by_default(sample_transaction, sample_context):
    """
    By default (fail_fast=False), a failing rule should not crash the engine.
    Instead, it records a transparent error RuleResult without swallowing the failure.
    """
    registry = RuleRegistry()
    r1 = DummyCleanRule()
    r_fail = DummyFailingRule()
    r2 = DummyTriggeredRule()
    registry.register(r1)
    registry.register(r_fail)
    registry.register(r2)

    engine = RuleEngine(registry=registry, fail_fast=False)
    results = await engine.evaluate_all(sample_transaction, sample_context)

    assert len(results) == 3
    # First rule executed successfully (clean)
    assert results[0].rule_id == "test_dummy_clean"
    assert results[0].triggered is False
    assert results[0].status == RuleExecutionStatus.SUCCESS

    # Second rule failed gracefully with explicit ERROR status
    assert results[1].rule_id == "test_dummy_failing"
    assert results[1].triggered is False
    assert results[1].status == RuleExecutionStatus.ERROR
    # Mandatory requirement: Failed rule is strictly NOT treated as a clean success
    assert results[1].status != RuleExecutionStatus.SUCCESS
    assert results[1].evidence.get("execution_failed") is True
    assert "Simulated rule failure" in results[1].evidence.get("error", "")
    assert "Rule evaluation failed with error" in results[1].reason

    # Third rule still executed successfully (triggered)
    assert results[2].rule_id == "test_dummy_triggered"
    assert results[2].triggered is True
    assert results[2].status == RuleExecutionStatus.SUCCESS


@pytest.mark.asyncio
async def test_engine_raises_when_fail_fast_enabled(sample_transaction, sample_context):
    registry = RuleRegistry()
    registry.register(DummyFailingRule())

    engine = RuleEngine(registry=registry, fail_fast=True)
    with pytest.raises(RuleExecutionError) as exc_info:
        await engine.evaluate_all(sample_transaction, sample_context)

    assert exc_info.value.rule_id == "test_dummy_failing"
    assert "Simulated rule failure" in str(exc_info.value)


@pytest.mark.asyncio
async def test_evaluate_transaction_packages_fraud_evaluation(sample_transaction, sample_context):
    registry = RuleRegistry()
    registry.register(DummyTriggeredRule(score=30, severity=Severity.MEDIUM))

    engine = RuleEngine(registry=registry)
    evaluation = await engine.evaluate_transaction(sample_transaction, sample_context)

    assert isinstance(evaluation, FraudEvaluation)
    assert evaluation.transaction_id == sample_transaction.transaction_id
    assert len(evaluation.rule_results) == 1
    assert evaluation.risk_score is None  # Deferred to Risk Engine
    assert evaluation.risk_level is None  # Deferred to Risk Engine


@pytest.mark.asyncio
async def test_rule_engine_extensibility_demonstration(sample_transaction, sample_context):
    """
    Demonstrates critical Batch 2 requirement:
    A completely new rule can be implemented and registered WITHOUT modifying RuleEngine code.
    """
    class CustomNewPluginRule(FraudRule):
        rule_id = "custom_plugin_extensibility_test"
        rule_name = "Custom Plugin Rule"
        description = "Demonstrates adding a rule without touching the engine"

        async def evaluate(self, transaction: Transaction, context: FraudEvaluationContext) -> RuleResult:
            is_above_threshold = transaction.amount > Decimal("1000.00")
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                triggered=is_above_threshold,
                score=50 if is_above_threshold else 0,
                severity=Severity.HIGH if is_above_threshold else Severity.NONE,
                reason="Amount exceeded arbitrary custom threshold",
                evidence={"threshold": "1000.00", "actual": str(transaction.amount)},
            )

    registry = RuleRegistry()
    registry.register(CustomNewPluginRule())

    engine = RuleEngine(registry=registry)
    results = await engine.evaluate_all(sample_transaction, sample_context)

    assert len(results) == 1
    assert results[0].rule_id == "custom_plugin_extensibility_test"
    assert results[0].triggered is True
    assert results[0].score == 50
    assert results[0].severity == Severity.HIGH
    assert results[0].status == RuleExecutionStatus.SUCCESS


def test_engine_registry_isolation():
    """
    Verify Fix 3: Two RuleEngine instances created without arguments
    have isolated registries and do not share mutable state.
    """
    engine_a = RuleEngine()
    engine_b = RuleEngine()

    assert engine_a.registry is not engine_b.registry

    # Register rule only into engine_a
    rule_a = DummyCleanRule()
    engine_a.registry.register(rule_a)

    assert len(engine_a.registry) == 1
    assert len(engine_b.registry) == 0
    assert "test_dummy_clean" in engine_a.registry
    assert "test_dummy_clean" not in engine_b.registry


def test_engine_custom_registry_injection():
    """
    Verify Fix 3: An explicitly supplied RuleRegistry is used by RuleEngine.
    """
    custom_registry = RuleRegistry()
    rule = DummyTriggeredRule()
    custom_registry.register(rule)

    engine = RuleEngine(registry=custom_registry)
    assert engine.registry is custom_registry
    assert len(engine.registry) == 1
    assert engine.registry.get("test_dummy_triggered") is rule


@pytest.mark.asyncio
async def test_failed_rule_is_not_treated_as_clean_rule(sample_transaction, sample_context):
    """
    Verify Fix 1: A failed rule produces status=ERROR, whereas a clean rule
    produces status=SUCCESS and triggered=False. A consumer checking status
    will never confuse a failed rule with a clean evaluation.
    """
    registry = RuleRegistry()
    registry.register(DummyCleanRule())
    registry.register(DummyFailingRule())

    engine = RuleEngine(registry=registry, fail_fast=False)
    results = await engine.evaluate_all(sample_transaction, sample_context)

    clean_result = results[0]
    failed_result = results[1]

    # Clean rule: executed successfully, didn't trigger
    assert clean_result.status == RuleExecutionStatus.SUCCESS
    assert clean_result.triggered is False

    # Failed rule: execution error, status is ERROR
    assert failed_result.status == RuleExecutionStatus.ERROR
    assert failed_result.triggered is False

    # Crucial assertion: status prevents confusion
    assert clean_result.status != failed_result.status
    assert failed_result.status != RuleExecutionStatus.SUCCESS

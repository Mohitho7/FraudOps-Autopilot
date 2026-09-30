"""
Tests for the FraudRule abstract base class and interface contract.
"""

from decimal import Decimal
from datetime import datetime, timezone
import pytest

from app.rules.base import FraudRule
from app.schemas.context import FraudEvaluationContext
from app.schemas.rule import RuleResult, Severity
from app.schemas.transaction import Transaction


def test_cannot_instantiate_abstract_fraud_rule_directly():
    with pytest.raises(TypeError):
        FraudRule()  # Can't instantiate abstract class without evaluate


@pytest.mark.asyncio
async def test_concrete_subclass_implements_interface():
    class TestConcreteRule(FraudRule):
        rule_id = "test_rule_1"
        rule_name = "Test Rule 1"
        description = "Test description"

        async def evaluate(self, transaction: Transaction, context: FraudEvaluationContext) -> RuleResult:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                triggered=False,
                score=0,
                severity=Severity.NONE,
                reason="Pass",
            )

    rule = TestConcreteRule()
    assert rule.rule_id == "test_rule_1"
    assert rule.rule_name == "Test Rule 1"
    assert rule.is_enabled is True

    tx = Transaction(
        transaction_id="tx_1",
        customer_id="c_1",
        merchant_id="m_1",
        amount=Decimal("100.00"),
        timestamp=datetime.now(timezone.utc),
    )
    context = FraudEvaluationContext()

    result = await rule.evaluate(tx, context)
    assert isinstance(result, RuleResult)
    assert result.triggered is False

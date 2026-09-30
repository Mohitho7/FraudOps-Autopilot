"""
Test doubles and dummy rules for testing the rule engine framework.
THESE ARE NOT PRODUCTION FRAUD RULES.
"""

from app.rules.base import FraudRule
from app.schemas.context import FraudEvaluationContext
from app.schemas.rule import RuleResult, Severity
from app.schemas.transaction import Transaction


class DummyTriggeredRule(FraudRule):
    """
    Test double that always triggers with a predefined score and severity.
    Used exclusively for framework verification.
    """
    rule_id = "test_dummy_triggered"
    rule_name = "Test Dummy Triggered Rule"
    description = "Test double that always triggers for unit testing"

    def __init__(self, score: int = 15, severity: Severity = Severity.LOW, is_enabled: bool = True):
        super().__init__(is_enabled=is_enabled)
        self.score = score
        self.severity = severity

    async def evaluate(self, transaction: Transaction, context: FraudEvaluationContext) -> RuleResult:
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            triggered=True,
            score=self.score,
            severity=self.severity,
            reason="Dummy rule triggered for test verification",
            evidence={"dummy_key": "dummy_value", "amount": str(transaction.amount)},
        )


class DummyCleanRule(FraudRule):
    """
    Test double that evaluates to not triggered (clean).
    """
    rule_id = "test_dummy_clean"
    rule_name = "Test Dummy Clean Rule"
    description = "Test double that never triggers"

    async def evaluate(self, transaction: Transaction, context: FraudEvaluationContext) -> RuleResult:
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            triggered=False,
            score=0,
            severity=Severity.NONE,
            reason="Dummy rule passed cleanly",
            evidence={},
        )


class DummyFailingRule(FraudRule):
    """
    Test double that raises an unhandled exception to test error handling in the engine.
    """
    rule_id = "test_dummy_failing"
    rule_name = "Test Dummy Failing Rule"
    description = "Test double designed to simulate rule crash"

    async def evaluate(self, transaction: Transaction, context: FraudEvaluationContext) -> RuleResult:
        raise RuntimeError("Simulated rule failure for error resilience testing")

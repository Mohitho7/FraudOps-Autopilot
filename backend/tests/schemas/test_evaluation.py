"""
Tests for FraudEvaluation aggregate schema.
"""

from app.schemas.evaluation import FraudEvaluation
from app.schemas.rule import RuleResult, Severity


def test_fraud_evaluation_creation_without_premature_risk_scoring():
    r1 = RuleResult(
        rule_id="r1",
        rule_name="Rule 1",
        triggered=True,
        score=20,
        severity=Severity.LOW,
        reason="Triggered",
        evidence={"detail": "data"},
    )
    r2 = RuleResult(
        rule_id="r2",
        rule_name="Rule 2",
        triggered=False,
        score=0,
        severity=Severity.NONE,
        reason="Passed",
        evidence={},
    )

    evaluation = FraudEvaluation(
        transaction_id="tx_eval_1",
        rule_results=[r1, r2],
    )

    assert evaluation.transaction_id == "tx_eval_1"
    assert len(evaluation.rule_results) == 2
    # Verify risk_score and risk_level are NOT calculated by Batch 2
    assert evaluation.risk_score is None
    assert evaluation.risk_level is None
    assert evaluation.evaluation_timestamp is not None

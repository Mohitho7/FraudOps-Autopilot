"""
Unit tests for the RiskEngine domain service.
Covers all minimum required scenarios from the Batch 4 specification.
"""

from decimal import Decimal
import pytest

from app.risk.config import RiskConfiguration
from app.risk.engine import RiskEngine
from app.risk.exceptions import (
    DuplicateRuleResultError,
    EmptyRuleResultsError,
    InvalidScoreError,
    UnknownRuleResultError,
)
from app.schemas.evaluation import RiskEvaluationStatus, RiskLevel
from app.schemas.rule import RuleExecutionStatus, RuleResult, Severity


def make_result(
    rule_id: str,
    score: int = 0,
    triggered: bool = False,
    status: RuleExecutionStatus = RuleExecutionStatus.SUCCESS,
    reason: str = "Test reason",
    evidence: dict = None,
) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        rule_name=rule_id.replace("_", " ").title(),
        triggered=triggered,
        score=score,
        severity=Severity.HIGH if triggered else Severity.NONE,
        reason=reason,
        evidence=evidence or {"sample_key": "sample_val"},
        status=status,
    )


class TestRiskEngine:
    # ------------------------------------------------------------
    # 1. ALL RULES CLEAN
    # ------------------------------------------------------------
    def test_all_rules_clean(self):
        engine = RiskEngine()
        results = [
            make_result("transaction_velocity", 0, triggered=False),
            make_result("unusual_amount", 0, triggered=False),
            make_result("impossible_location", 0, triggered=False),
            make_result("merchant_context", 0, triggered=False),
        ]

        evaluation = engine.evaluate(results, transaction_id="tx_clean_1")

        assert evaluation.transaction_id == "tx_clean_1"
        assert evaluation.risk_score == 0
        assert evaluation.risk_level == RiskLevel.LOW.value
        assert evaluation.evaluation_status == RiskEvaluationStatus.COMPLETE.value
        assert evaluation.coverage_ratio == 1.0
        assert len(evaluation.triggered_rules) == 0
        assert len(evaluation.clean_rules) == 4
        assert len(evaluation.failed_rules) == 0

    # ------------------------------------------------------------
    # 2. SINGLE RULE TRIGGER
    # ------------------------------------------------------------
    def test_single_rule_trigger(self):
        # Velocity triggered (score=60, weight=0.20), others clean (score=0)
        # Expected: 60 * 0.20 + 0 = 12.0 -> score = 12 (LOW)
        engine = RiskEngine()
        results = [
            make_result("transaction_velocity", 60, triggered=True),
            make_result("unusual_amount", 0, triggered=False),
            make_result("impossible_location", 0, triggered=False),
            make_result("merchant_context", 0, triggered=False),
        ]

        evaluation = engine.evaluate(results, transaction_id="tx_single_1")

        assert evaluation.risk_score == 12
        assert evaluation.risk_level == RiskLevel.LOW.value
        assert evaluation.evaluation_status == RiskEvaluationStatus.COMPLETE.value
        assert evaluation.triggered_rules == ["transaction_velocity"]
        assert len(evaluation.clean_rules) == 3

    # ------------------------------------------------------------
    # 3. MULTIPLE RULES TRIGGER
    # ------------------------------------------------------------
    def test_multiple_rules_trigger(self):
        # Velocity triggered (score=60, wt=0.20) -> 12.0
        # Amount triggered   (score=80, wt=0.25) -> 20.0
        # Location clean     (score=0,  wt=0.30) -> 0.0
        # Merchant clean     (score=0,  wt=0.25) -> 0.0
        # Total = 32.0 -> score = 32 (LOW)
        engine = RiskEngine()
        results = [
            make_result("transaction_velocity", 60, triggered=True),
            make_result("unusual_amount", 80, triggered=True),
            make_result("impossible_location", 0, triggered=False),
            make_result("merchant_context", 0, triggered=False),
        ]

        evaluation = engine.evaluate(results, transaction_id="tx_multi_1")

        assert evaluation.risk_score == 32
        assert evaluation.risk_level == RiskLevel.LOW.value
        assert evaluation.evaluation_status == RiskEvaluationStatus.COMPLETE.value
        assert set(evaluation.triggered_rules) == {"transaction_velocity", "unusual_amount"}

    # ------------------------------------------------------------
    # 4. WEIGHTED CALCULATION (HAND-CALCULATED)
    # ------------------------------------------------------------
    def test_exact_weighted_calculation(self):
        # velocity = 60 (wt: 0.20) -> 12.0
        # amount = 80   (wt: 0.25) -> 20.0
        # location = 40 (wt: 0.30) -> 12.0
        # merchant = 20 (wt: 0.25) -> 5.0
        # weighted_sum = 12.0 + 20.0 + 12.0 + 5.0 = 49.0
        engine = RiskEngine()
        results = [
            make_result("transaction_velocity", 60, triggered=True),
            make_result("unusual_amount", 80, triggered=True),
            make_result("impossible_location", 40, triggered=True),
            make_result("merchant_context", 20, triggered=True),
        ]

        evaluation = engine.evaluate(results, transaction_id="tx_exact_1")

        assert evaluation.risk_score == 49
        assert evaluation.risk_level == RiskLevel.MEDIUM.value
        assert evaluation.metadata["raw_weighted_sum"] == 49.0
        assert evaluation.metadata["available_weight"] == 1.0

    # ------------------------------------------------------------
    # 5. EXACT RISK BOUNDARIES (0, 39, 40, 69, 70, 89, 90, 100)
    # ------------------------------------------------------------
    @pytest.mark.parametrize(
        "target_score, expected_level",
        [
            (0, RiskLevel.LOW),
            (39, RiskLevel.LOW),
            (40, RiskLevel.MEDIUM),
            (69, RiskLevel.MEDIUM),
            (70, RiskLevel.HIGH),
            (89, RiskLevel.HIGH),
            (90, RiskLevel.CRITICAL),
            (100, RiskLevel.CRITICAL),
        ],
    )
    def test_exact_risk_boundaries(self, target_score, expected_level):
        engine = RiskEngine()
        # Set all rules to target_score -> weighted sum is exactly target_score
        results = [
            make_result("transaction_velocity", target_score, triggered=(target_score > 0)),
            make_result("unusual_amount", target_score, triggered=(target_score > 0)),
            make_result("impossible_location", target_score, triggered=(target_score > 0)),
            make_result("merchant_context", target_score, triggered=(target_score > 0)),
        ]

        evaluation = engine.evaluate(results)
        assert evaluation.risk_score == target_score
        assert evaluation.risk_level == expected_level.value

    # ------------------------------------------------------------
    # 6. FAILED RULE (PARTIAL EVALUATION & NORMALIZATION)
    # ------------------------------------------------------------
    def test_failed_rule_normalized_properly(self):
        # Location failed (status=ERROR, wt: 0.30)
        # Velocity: 60 (wt: 0.20) -> 12.0
        # Amount:   80 (wt: 0.25) -> 20.0
        # Merchant: 40 (wt: 0.25) -> 10.0
        # Available weight = 0.20 + 0.25 + 0.25 = 0.70
        # Normalized score = (12 + 20 + 10) / 0.70 = 42.0 / 0.70 = 60.0
        engine = RiskEngine()
        results = [
            make_result("transaction_velocity", 60, triggered=True),
            make_result("unusual_amount", 80, triggered=True),
            make_result("impossible_location", 0, status=RuleExecutionStatus.ERROR),
            make_result("merchant_context", 40, triggered=True),
        ]

        evaluation = engine.evaluate(results, transaction_id="tx_partial_1")

        assert evaluation.risk_score == 60
        assert evaluation.risk_level == RiskLevel.MEDIUM.value
        assert evaluation.evaluation_status == RiskEvaluationStatus.PARTIAL.value
        assert evaluation.coverage_ratio == 0.70
        assert evaluation.failed_rules == ["impossible_location"]
        assert len(evaluation.clean_rules) == 0
        assert "impossible_location" not in evaluation.clean_rules
        assert evaluation.metadata["failed_rule_count"] == 1

    # ------------------------------------------------------------
    # 7. ALL RULES FAILED (NO_VALID_SIGNALS)
    # ------------------------------------------------------------
    def test_all_rules_failed_state(self):
        engine = RiskEngine()
        results = [
            make_result("transaction_velocity", 0, status=RuleExecutionStatus.ERROR),
            make_result("unusual_amount", 0, status=RuleExecutionStatus.ERROR),
            make_result("impossible_location", 0, status=RuleExecutionStatus.ERROR),
            make_result("merchant_context", 0, status=RuleExecutionStatus.ERROR),
        ]

        evaluation = engine.evaluate(results, transaction_id="tx_all_failed")

        assert evaluation.evaluation_status == RiskEvaluationStatus.NO_VALID_SIGNALS.value
        assert evaluation.risk_score is None
        assert evaluation.risk_level is None
        assert evaluation.coverage_ratio == 0.0
        assert len(evaluation.failed_rules) == 4
        assert len(evaluation.successful_rules if hasattr(evaluation, "successful_rules") else []) == 0
        assert evaluation.metadata["successful_rule_count"] == 0

    # ------------------------------------------------------------
    # 8. MANDATORY TEST: CLEAN VS ERROR DIFFERENTIATION
    # ------------------------------------------------------------
    def test_mandatory_clean_vs_error_differentiation(self):
        """
        MANDATORY TEST:
        Explicitly proves that SUCCESS + triggered=False is fundamentally different from ERROR.
        Case A: 1 rule triggered (80), 3 rules clean (score=0).
                Denominator is 1.0. Score = 80 * 0.25 / 1.0 = 20 (LOW).
        Case B: 1 rule triggered (80), 3 rules failed (ERROR).
                Denominator is 0.25. Score = 80 * 0.25 / 0.25 = 80 (HIGH).
        """
        engine = RiskEngine()

        # Case A: Clean rules provide positive proof of normalcy
        results_clean = [
            make_result("unusual_amount", 80, triggered=True),
            make_result("transaction_velocity", 0, triggered=False, status=RuleExecutionStatus.SUCCESS),
            make_result("impossible_location", 0, triggered=False, status=RuleExecutionStatus.SUCCESS),
            make_result("merchant_context", 0, triggered=False, status=RuleExecutionStatus.SUCCESS),
        ]
        eval_clean = engine.evaluate(results_clean)
        assert eval_clean.risk_score == 20
        assert eval_clean.risk_level == RiskLevel.LOW.value
        assert eval_clean.evaluation_status == RiskEvaluationStatus.COMPLETE.value

        # Case B: Failed rules represent missing information (cannot dilute the anomaly)
        results_error = [
            make_result("unusual_amount", 80, triggered=True),
            make_result("transaction_velocity", 0, status=RuleExecutionStatus.ERROR),
            make_result("impossible_location", 0, status=RuleExecutionStatus.ERROR),
            make_result("merchant_context", 0, status=RuleExecutionStatus.ERROR),
        ]
        eval_error = engine.evaluate(results_error)
        assert eval_error.risk_score == 80
        assert eval_error.risk_level == RiskLevel.HIGH.value
        assert eval_error.evaluation_status == RiskEvaluationStatus.PARTIAL.value

        # They must be mathematically different!
        assert eval_clean.risk_score != eval_error.risk_score
        assert eval_clean.risk_level != eval_error.risk_level

    # ------------------------------------------------------------
    # 9. DUPLICATE RULE RESULTS VALIDATION
    # ------------------------------------------------------------
    def test_duplicate_rule_result_raises_error(self):
        engine = RiskEngine()
        results = [
            make_result("transaction_velocity", 60),
            make_result("transaction_velocity", 60),  # Duplicate
            make_result("unusual_amount", 80),
            make_result("impossible_location", 40),
        ]
        with pytest.raises(DuplicateRuleResultError, match="Duplicate RuleResult detected for rule_id 'transaction_velocity'"):
            engine.evaluate(results)

    # ------------------------------------------------------------
    # 10. UNKNOWN RULE RESULT VALIDATION
    # ------------------------------------------------------------
    def test_unknown_rule_result_raises_error(self):
        engine = RiskEngine()
        results = [
            make_result("transaction_velocity", 60),
            make_result("unusual_amount", 80),
            make_result("impossible_location", 40),
            make_result("merchant_context", 20),
            make_result("unregistered_experimental_rule", 90),
        ]
        with pytest.raises(UnknownRuleResultError, match="has no configured weight in RiskConfiguration"):
            engine.evaluate(results)

    # ------------------------------------------------------------
    # 11. INVALID SCORE INPUTS
    # ------------------------------------------------------------
    def test_score_out_of_range_rejected(self):
        engine = RiskEngine()
        # Score -5
        bad_res1 = RuleResult(
            rule_id="transaction_velocity",
            rule_name="Velocity",
            triggered=False,
            score=0,  # Construct valid model first
        )
        # Using object.__setattr__ to bypass frozen Pydantic validation and test RiskEngine defensive check
        object.__setattr__(bad_res1, "score", -5)

        with pytest.raises(InvalidScoreError, match="Score must be a number between 0 and 100"):
            engine.evaluate([bad_res1])

        bad_res2 = RuleResult(
            rule_id="transaction_velocity",
            rule_name="Velocity",
            triggered=True,
            score=0,
        )
        object.__setattr__(bad_res2, "score", 105)

        with pytest.raises(InvalidScoreError, match="Score must be a number between 0 and 100"):
            engine.evaluate([bad_res2])

    # ------------------------------------------------------------
    # 12. EMPTY RULE RESULTS VALIDATION
    # ------------------------------------------------------------
    def test_empty_rule_results_raises_error(self):
        engine = RiskEngine()
        with pytest.raises(EmptyRuleResultsError, match="Cannot aggregate risk on an empty sequence"):
            engine.evaluate([])

    # ------------------------------------------------------------
    # 13. DETERMINISTIC REPEATABILITY
    # ------------------------------------------------------------
    def test_deterministic_repeatability(self):
        engine = RiskEngine()
        results = [
            make_result("transaction_velocity", 70, triggered=True),
            make_result("unusual_amount", 85, triggered=True),
            make_result("impossible_location", 0, triggered=False),
            make_result("merchant_context", 65, triggered=True),
        ]

        e1 = engine.evaluate(results, transaction_id="tx_repeat")
        e2 = engine.evaluate(results, transaction_id="tx_repeat")

        assert e1.risk_score == e2.risk_score
        assert e1.risk_level == e2.risk_level
        assert e1.coverage_ratio == e2.coverage_ratio
        assert e1.triggered_rules == e2.triggered_rules
        assert e1.clean_rules == e2.clean_rules
        assert e1.failed_rules == e2.failed_rules
        assert e1.metadata == e2.metadata

    # ------------------------------------------------------------
    # 14. ORIGINAL RULE RESULTS PRESERVATION
    # ------------------------------------------------------------
    def test_rule_result_preservation(self):
        engine = RiskEngine()
        r1 = make_result("transaction_velocity", 60, triggered=True, reason="High velocity", evidence={"window": 10})
        r2 = make_result("unusual_amount", 80, triggered=True, reason="High amount", evidence={"multiplier": 4.0})
        r3 = make_result("impossible_location", 0, triggered=False, reason="Normal travel", evidence={"speed": 20.0})
        r4 = make_result("merchant_context", 40, triggered=False, reason="Below p95", evidence={"p95": 50000})

        evaluation = engine.evaluate([r1, r2, r3, r4], transaction_id="tx_preserve")

        assert len(evaluation.rule_results) == 4
        res_map = {r.rule_id: r for r in evaluation.rule_results}

        assert res_map["transaction_velocity"].evidence == {"window": 10}
        assert res_map["transaction_velocity"].reason == "High velocity"
        assert res_map["unusual_amount"].evidence == {"multiplier": 4.0}
        assert res_map["impossible_location"].evidence == {"speed": 20.0}
        assert res_map["merchant_context"].evidence == {"p95": 50000}

    # ------------------------------------------------------------
    # 15. COVERAGE CALCULATIONS (100%, 75%, 50%, 0%)
    # ------------------------------------------------------------
    def test_coverage_ratios_across_scenarios(self):
        # Custom equal weights (0.25 each) for transparent coverage checks
        weights = {
            "transaction_velocity": Decimal("0.25"),
            "unusual_amount": Decimal("0.25"),
            "impossible_location": Decimal("0.25"),
            "merchant_context": Decimal("0.25"),
        }
        engine = RiskEngine(config=RiskConfiguration(rule_weights=weights))

        # 4 succeed -> 100%
        e4 = engine.evaluate([
            make_result("transaction_velocity", status=RuleExecutionStatus.SUCCESS),
            make_result("unusual_amount", status=RuleExecutionStatus.SUCCESS),
            make_result("impossible_location", status=RuleExecutionStatus.SUCCESS),
            make_result("merchant_context", status=RuleExecutionStatus.SUCCESS),
        ])
        assert e4.coverage_ratio == 1.0
        assert e4.evaluation_status == RiskEvaluationStatus.COMPLETE.value

        # 3 succeed, 1 fail -> 75%
        e3 = engine.evaluate([
            make_result("transaction_velocity", status=RuleExecutionStatus.SUCCESS),
            make_result("unusual_amount", status=RuleExecutionStatus.SUCCESS),
            make_result("impossible_location", status=RuleExecutionStatus.SUCCESS),
            make_result("merchant_context", status=RuleExecutionStatus.ERROR),
        ])
        assert e3.coverage_ratio == 0.75
        assert e3.evaluation_status == RiskEvaluationStatus.PARTIAL.value

        # 2 succeed, 2 fail -> 50%
        e2 = engine.evaluate([
            make_result("transaction_velocity", status=RuleExecutionStatus.SUCCESS),
            make_result("unusual_amount", status=RuleExecutionStatus.SUCCESS),
            make_result("impossible_location", status=RuleExecutionStatus.ERROR),
            make_result("merchant_context", status=RuleExecutionStatus.ERROR),
        ])
        assert e2.coverage_ratio == 0.50
        assert e2.evaluation_status == RiskEvaluationStatus.PARTIAL.value

        # 0 succeed, 4 fail -> 0%
        e0 = engine.evaluate([
            make_result("transaction_velocity", status=RuleExecutionStatus.ERROR),
            make_result("unusual_amount", status=RuleExecutionStatus.ERROR),
            make_result("impossible_location", status=RuleExecutionStatus.ERROR),
            make_result("merchant_context", status=RuleExecutionStatus.ERROR),
        ])
        assert e0.coverage_ratio == 0.0
        assert e0.evaluation_status == RiskEvaluationStatus.NO_VALID_SIGNALS.value

    # ------------------------------------------------------------
    # 16. EVALUATE EVALUATION HELPER
    # ------------------------------------------------------------
    def test_evaluate_evaluation_helper(self):
        from app.schemas.evaluation import FraudEvaluation

        raw_eval = FraudEvaluation(
            transaction_id="tx_raw_1",
            rule_results=[
                make_result("transaction_velocity", 60, triggered=True),
                make_result("unusual_amount", 80, triggered=True),
                make_result("impossible_location", 40, triggered=True),
                make_result("merchant_context", 20, triggered=True),
            ],
            metadata={"source": "upstream_system"},
        )

        engine = RiskEngine()
        enriched = engine.evaluate_evaluation(raw_eval)

        assert enriched.transaction_id == "tx_raw_1"
        assert enriched.risk_score == 49
        assert enriched.risk_level == RiskLevel.MEDIUM.value
        assert enriched.metadata["source"] == "upstream_system"
        assert enriched.metadata["evaluation_status"] == RiskEvaluationStatus.COMPLETE.value

    # ------------------------------------------------------------
    # 17. F-03: PARTIAL EVALUATION SAFETY & HANDOFF CONTRACT
    # ------------------------------------------------------------
    def test_partial_evaluation_safety_handoff_and_serialization(self):
        """
        Finding F-03:
        When three rules succeed with score=0 and one rule fails with ERROR:
        - evaluation_status is PARTIAL (NOT COMPLETE)
        - coverage_ratio is 0.70 (< 1.0)
        - risk_score is 0
        - risk_level is LOW (strictly as score classification, NOT as verified safe signal)
        - failed_rules contains the failed rule ID
        - clean_rules contains the 3 successful rules
        - triggered_rules is empty
        - All metadata survives JSON serialization/deserialization for Member 2 consumption
        """
        from app.schemas.evaluation import FraudEvaluation

        engine = RiskEngine()
        results = [
            make_result("transaction_velocity", 0, triggered=False, status=RuleExecutionStatus.SUCCESS),
            make_result("unusual_amount", 0, triggered=False, status=RuleExecutionStatus.SUCCESS),
            make_result("merchant_context", 0, triggered=False, status=RuleExecutionStatus.SUCCESS),
            make_result("impossible_location", 0, status=RuleExecutionStatus.ERROR, reason="GPS service timeout"),
        ]

        evaluation = engine.evaluate(results, transaction_id="tx_partial_handoff")

        # Core assertions required by F-03:
        assert evaluation.evaluation_status == RiskEvaluationStatus.PARTIAL.value
        assert evaluation.coverage_ratio == 0.70
        assert evaluation.coverage_ratio < 1.0
        assert evaluation.risk_score == 0
        assert evaluation.risk_level == RiskLevel.LOW.value
        assert evaluation.failed_rules == ["impossible_location"]
        assert set(evaluation.clean_rules) == {"transaction_velocity", "unusual_amount", "merchant_context"}
        assert evaluation.triggered_rules == []

        # Downstream visibility assertions:
        assert evaluation.metadata["failed_rule_count"] == 1
        assert evaluation.metadata["successful_rule_count"] == 3
        assert evaluation.metadata["available_weight"] == 0.70
        assert evaluation.metadata["total_configured_weight"] == 1.0

        # Verify JSON serialization / deserialization roundtrip for Member 2 handoff:
        json_str = evaluation.model_dump_json()
        deserialized = FraudEvaluation.model_validate_json(json_str)

        assert deserialized.transaction_id == "tx_partial_handoff"
        assert deserialized.evaluation_status == "PARTIAL"
        assert deserialized.coverage_ratio == 0.70
        assert deserialized.risk_score == 0
        assert deserialized.risk_level == "LOW"
        assert deserialized.failed_rules == ["impossible_location"]
        assert len(deserialized.rule_results) == 4
        # Failed rule preserves ERROR status in serialized handoff
        failed_res = next(r for r in deserialized.rule_results if r.rule_id == "impossible_location")
        assert failed_res.status == RuleExecutionStatus.ERROR
        assert failed_res.reason == "GPS service timeout"


"""
Unit tests for deterministic risk engine helpers (mapping, weighting, coverage).
"""

from decimal import Decimal
import pytest

from app.risk.config import DEFAULT_RULE_WEIGHTS
from app.risk.helpers import (
    calculate_coverage,
    calculate_weighted_score,
    map_score_to_risk_level,
)
from app.schemas.evaluation import RiskLevel
from app.schemas.rule import RuleExecutionStatus, RuleResult, Severity


def make_result(
    rule_id: str,
    score: int,
    status: RuleExecutionStatus = RuleExecutionStatus.SUCCESS,
    triggered: bool = True,
) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        rule_name=rule_id.replace("_", " ").title(),
        triggered=triggered,
        score=score,
        severity=Severity.HIGH if triggered else Severity.NONE,
        status=status,
    )


class TestMapScoreToRiskLevel:
    @pytest.mark.parametrize(
        "score, expected",
        [
            (None, None),
            (0, RiskLevel.LOW),
            (25, RiskLevel.LOW),
            (39, RiskLevel.LOW),     # Exact boundary
            (40, RiskLevel.MEDIUM),  # Exact boundary
            (55, RiskLevel.MEDIUM),
            (69, RiskLevel.MEDIUM),  # Exact boundary
            (70, RiskLevel.HIGH),    # Exact boundary
            (80, RiskLevel.HIGH),
            (89, RiskLevel.HIGH),    # Exact boundary
            (90, RiskLevel.CRITICAL),# Exact boundary
            (95, RiskLevel.CRITICAL),
            (100, RiskLevel.CRITICAL),# Exact boundary
        ],
    )
    def test_exact_risk_boundaries(self, score, expected):
        assert map_score_to_risk_level(score) == expected


class TestCalculateCoverage:
    def test_full_coverage(self):
        assert calculate_coverage(Decimal("1.00"), Decimal("1.00")) == 1.0

    def test_partial_coverage(self):
        assert calculate_coverage(Decimal("0.70"), Decimal("1.00")) == 0.70

    def test_half_coverage(self):
        assert calculate_coverage(Decimal("0.50"), Decimal("1.00")) == 0.50

    def test_zero_coverage(self):
        assert calculate_coverage(Decimal("0.00"), Decimal("1.00")) == 0.0

    def test_zero_total_weight(self):
        assert calculate_coverage(Decimal("0.00"), Decimal("0.00")) == 0.0


class TestCalculateWeightedScore:
    def test_hand_calculated_weighted_score(self):
        # velocity = 60 (wt: 0.20) -> 12.0
        # amount = 80   (wt: 0.25) -> 20.0
        # location = 40 (wt: 0.30) -> 12.0
        # merchant = 20 (wt: 0.25) -> 5.0
        # sum = 49.0 / 1.00 = 49
        results = [
            make_result("transaction_velocity", 60),
            make_result("unusual_amount", 80),
            make_result("impossible_location", 40),
            make_result("merchant_context", 20),
        ]
        score, raw_sum, avail_wt = calculate_weighted_score(results, DEFAULT_RULE_WEIGHTS)
        assert score == 49
        assert raw_sum == Decimal("49.00")
        assert avail_wt == Decimal("1.00")

    def test_partial_normalized_weighted_score(self):
        # location rule failed, so only 3 rules available:
        # velocity = 60 (wt: 0.20) -> 12.0
        # amount = 80   (wt: 0.25) -> 20.0
        # merchant = 40 (wt: 0.25) -> 10.0
        # raw sum = 42.0
        # available weight = 0.20 + 0.25 + 0.25 = 0.70
        # normalized = 42.0 / 0.70 = 60.0 -> score = 60
        results = [
            make_result("transaction_velocity", 60),
            make_result("unusual_amount", 80),
            make_result("merchant_context", 40),
        ]
        score, raw_sum, avail_wt = calculate_weighted_score(results, DEFAULT_RULE_WEIGHTS)
        assert score == 60
        assert raw_sum == Decimal("42.00")
        assert avail_wt == Decimal("0.70")

    def test_empty_results_returns_none(self):
        score, raw_sum, avail_wt = calculate_weighted_score([], DEFAULT_RULE_WEIGHTS)
        assert score is None
        assert raw_sum == Decimal("0.00")
        assert avail_wt == Decimal("0.00")

    def test_round_half_up_midpoint_behavior(self):
        """
        Finding F-04:
        Verify that score normalization uses Decimal ROUND_HALF_UP:
        - 69.49 rounds to 69
        - 69.50 rounds upward to 70 (exact midpoint)
        - 69.51 rounds to 70
        - 68.50 rounds upward to 69 (differs from Python's built-in round(68.5)==68 banker's rounding)
        """
        # Scenario 1: 69.49 -> 69
        # 70 * 0.49 + 69 * 0.51 = 34.30 + 35.19 = 69.49
        weights_49 = {"r1": Decimal("0.49"), "r2": Decimal("0.51")}
        results_49 = [make_result("r1", 70), make_result("r2", 69)]
        score_49, raw_49, _ = calculate_weighted_score(results_49, weights_49)
        assert raw_49 == Decimal("69.49")
        assert score_49 == 69

        # Scenario 2: 69.50 -> 70 (exact midpoint rounds upward)
        # 70 * 0.50 + 69 * 0.50 = 35.00 + 34.50 = 69.50
        weights_50 = {"r1": Decimal("0.50"), "r2": Decimal("0.50")}
        results_50 = [make_result("r1", 70), make_result("r2", 69)]
        score_50, raw_50, _ = calculate_weighted_score(results_50, weights_50)
        assert raw_50 == Decimal("69.50")
        assert score_50 == 70

        # Scenario 3: 69.51 -> 70
        # 70 * 0.51 + 69 * 0.49 = 35.70 + 33.81 = 69.51
        weights_51 = {"r1": Decimal("0.51"), "r2": Decimal("0.49")}
        results_51 = [make_result("r1", 70), make_result("r2", 69)]
        score_51, raw_51, _ = calculate_weighted_score(results_51, weights_51)
        assert raw_51 == Decimal("69.51")
        assert score_51 == 70

        # Scenario 4: Even midpoint 68.50 -> 69
        # Python's round(68.5) == 68, but Decimal ROUND_HALF_UP produces 69
        results_even_mid = [make_result("r1", 68), make_result("r2", 69)]
        score_even, raw_even, _ = calculate_weighted_score(results_even_mid, weights_50)
        assert raw_even == Decimal("68.50")
        assert score_even == 69


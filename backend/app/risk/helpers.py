"""
Deterministic helper functions for risk score calculation, normalization, and categorization.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional, Sequence, Tuple

from app.schemas.evaluation import RiskLevel
from app.schemas.rule import RuleResult


def calculate_coverage(available_weight: Decimal, total_weight: Decimal) -> float:
    """
    Calculate the proportion of configured rule weight that was available/evaluated.

    Returns:
        float: Rounded to 4 decimal places, clamped between 0.0 and 1.0.
    """
    if total_weight <= Decimal("0.00"):
        return 0.0
    ratio = available_weight / total_weight
    clamped = min(Decimal("1.0"), max(Decimal("0.0"), ratio))
    return float(round(clamped, 4))


def map_score_to_risk_level(
    score: Optional[int],
    low_threshold: int = 39,
    medium_threshold: int = 69,
    high_threshold: int = 89,
) -> Optional[RiskLevel]:
    """
    Map a deterministic risk score (0-100) to a case-level RiskLevel.

    Deterministic boundaries:
    0  to 39  -> LOW
    40 to 69  -> MEDIUM
    70 to 89  -> HIGH
    90 to 100 -> CRITICAL

    Returns:
        RiskLevel or None if score is None.
    """
    if score is None:
        return None

    if score <= low_threshold:
        return RiskLevel.LOW
    elif score <= medium_threshold:
        return RiskLevel.MEDIUM
    elif score <= high_threshold:
        return RiskLevel.HIGH
    else:
        return RiskLevel.CRITICAL


def calculate_weighted_score(
    successful_results: Sequence[RuleResult],
    rule_weights: Dict[str, Decimal],
) -> Tuple[Optional[int], Decimal, Decimal]:
    """
    Calculate normalized weighted score using only successful rule signals.
    Failed/unavailable rules are excluded from both numerator and denominator,
    preventing a failed rule from being treated as clean (score 0).

    Formula:
        normalized_score = (sum(score_i * weight_i)) / sum(weight_i)

    Returns:
        Tuple of (normalized_integer_score, raw_weighted_sum, available_weight).
        If available_weight == 0, returns (None, Decimal("0.00"), Decimal("0.00")).
    """
    if not successful_results:
        return (None, Decimal("0.00"), Decimal("0.00"))

    available_weight = sum(rule_weights[r.rule_id] for r in successful_results)
    if available_weight <= Decimal("0.00"):
        return (None, Decimal("0.00"), Decimal("0.00"))

    raw_weighted_sum = sum(
        Decimal(str(r.score)) * rule_weights[r.rule_id]
        for r in successful_results
    )

    normalized = raw_weighted_sum / available_weight
    clamped = min(Decimal("100.00"), max(Decimal("0.00"), normalized))
    final_score = int(clamped.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    return (final_score, raw_weighted_sum, available_weight)

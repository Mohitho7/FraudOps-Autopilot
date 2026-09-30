"""
Deterministic Merchant Context Rule.
Evaluates transaction amounts against merchant historical statistical profiles (p95, p99, p50, average)
and operating hours to provide business-contextual risk signals without hardcoding category stereotypes.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from app.rules.base import FraudRule
from app.rules.helpers import is_within_operating_hours, score_to_severity
from app.schemas.context import FraudEvaluationContext
from app.schemas.merchant import Merchant, MerchantStatistics
from app.schemas.rule import RuleExecutionStatus, RuleResult, Severity
from app.schemas.transaction import Transaction


class MerchantContextRule(FraudRule):
    """
    Evaluates transactions using merchant-specific statistical baselines.
    Hierarchy:
    1. p95 (primary)
    2. p99 (stronger anomaly signal if amount > p99)
    3. p50 with fallback multiplier
    4. average_transaction_amount with fallback multiplier
    """

    def __init__(
        self,
        fallback_multiplier: float = 3.0,
        rule_id: str = "merchant_context",
        rule_name: str = "Merchant Context Rule",
        description: Optional[str] = None,
        is_enabled: bool = True,
    ):
        if fallback_multiplier <= 1.0:
            raise ValueError("fallback_multiplier must be greater than 1.0")

        desc = description or (
            "Evaluates transaction amounts against merchant statistical distributions "
            f"(p95/p99 baseline or p50/avg with {fallback_multiplier}x fallback multiplier)."
        )
        super().__init__(
            rule_id=rule_id,
            rule_name=rule_name,
            description=desc,
            is_enabled=is_enabled,
        )
        self.fallback_multiplier = Decimal(str(fallback_multiplier))

    async def evaluate(
        self,
        transaction: Transaction,
        context: FraudEvaluationContext,
    ) -> RuleResult:
        merchant: Optional[Merchant] = context.merchant_context
        stats: Optional[MerchantStatistics] = (
            context.merchant_statistics
            or (merchant.statistics if merchant else None)
        )

        merchant_id = merchant.merchant_id if merchant else transaction.merchant_id
        merchant_category = merchant.category if merchant else None

        # Check operating hours context
        within_hours: Optional[bool] = None
        op_status = "UNKNOWN"
        if merchant and merchant.operating_hours:
            within_hours = is_within_operating_hours(
                transaction.timestamp, merchant.operating_hours
            )
            if within_hours is True:
                op_status = "WITHIN_HOURS"
            elif within_hours is False:
                op_status = "OUTSIDE_HOURS"

        evidence: Dict[str, Any] = {
            "merchant_id": merchant_id,
            "merchant_category": merchant_category,
            "current_transaction_amount": str(transaction.amount),
            "baseline_type": None,
            "baseline_value": None,
            "p95": str(stats.p95) if (stats and stats.p95 is not None) else None,
            "p99": str(stats.p99) if (stats and stats.p99 is not None) else None,
            "p50": str(stats.p50) if (stats and stats.p50 is not None) else None,
            "average": (
                str(stats.average_transaction_amount)
                if (stats and stats.average_transaction_amount > Decimal("0.00"))
                else None
            ),
            "typical_daily_volume": (
                str(stats.typical_daily_volume)
                if (stats and stats.typical_daily_volume is not None)
                else None
            ),
            "operating_hours_status": op_status,
            "within_operating_hours": within_hours,
            "ratio": None,
            "fallback_multiplier": float(self.fallback_multiplier),
            "insufficient_merchant_statistics": False,
        }

        # Determine statistical baseline according to preference hierarchy
        baseline_type: Optional[str] = None
        baseline_value: Optional[Decimal] = None

        if stats and stats.p95 is not None and stats.p95 > Decimal("0.00"):
            baseline_type = "p95"
            baseline_value = stats.p95
        elif stats and stats.p99 is not None and stats.p99 > Decimal("0.00"):
            baseline_type = "p99"
            baseline_value = stats.p99
        elif stats and stats.p50 is not None and stats.p50 > Decimal("0.00"):
            baseline_type = "p50"
            baseline_value = stats.p50
        elif stats and stats.average_transaction_amount > Decimal("0.00"):
            baseline_type = "average"
            baseline_value = stats.average_transaction_amount

        # If no usable baseline exists, return clean with explicit evidence
        if baseline_type is None or baseline_value is None:
            reason = "Insufficient merchant statistics to establish baseline."
            evidence.update(
                {
                    "insufficient_merchant_statistics": True,
                    "score": 0,
                    "severity": Severity.NONE.value,
                    "reason": reason,
                }
            )
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                triggered=False,
                score=0,
                severity=Severity.NONE,
                reason=reason,
                evidence=evidence,
                status=RuleExecutionStatus.SUCCESS,
            )

        evidence["baseline_type"] = baseline_type
        evidence["baseline_value"] = str(baseline_value)

        # Evaluation based on baseline type
        if baseline_type == "p95":
            if transaction.amount <= baseline_value:
                triggered = False
                score = 0
                severity = Severity.NONE
                reason = (
                    f"Transaction amount {transaction.amount} is within merchant p95 "
                    f"threshold ({baseline_value})."
                )
            else:
                triggered = True
                # Check if p99 exists for higher severity anomaly
                if stats and stats.p99 is not None and stats.p99 > Decimal("0.00"):
                    if transaction.amount > stats.p99:
                        ratio_p99 = (transaction.amount - stats.p99) / stats.p99
                        score = min(100, 85 + int(ratio_p99 * Decimal("15")))
                        severity = score_to_severity(score)
                        reason = (
                            f"Transaction amount {transaction.amount} exceeds merchant p99 "
                            f"threshold ({stats.p99}) [p95: {baseline_value}]."
                        )
                    else:
                        spread = stats.p99 - baseline_value
                        if spread > Decimal("0.00"):
                            pos = (transaction.amount - baseline_value) / spread
                            score = min(84, 65 + int(pos * Decimal("19")))
                        else:
                            score = 65
                        severity = score_to_severity(score)
                        reason = (
                            f"Transaction amount {transaction.amount} exceeds merchant p95 "
                            f"threshold ({baseline_value}) but is below p99 ({stats.p99})."
                        )
                else:
                    excess = (transaction.amount - baseline_value) / baseline_value
                    score = min(100, 65 + int(excess * Decimal("20")))
                    severity = score_to_severity(score)
                    reason = (
                        f"Transaction amount {transaction.amount} exceeds merchant p95 "
                        f"threshold ({baseline_value})."
                    )

        elif baseline_type == "p99":
            if transaction.amount <= baseline_value:
                triggered = False
                score = 0
                severity = Severity.NONE
                reason = (
                    f"Transaction amount {transaction.amount} is within merchant p99 "
                    f"threshold ({baseline_value})."
                )
            else:
                triggered = True
                excess = (transaction.amount - baseline_value) / baseline_value
                score = min(100, 85 + int(excess * Decimal("15")))
                severity = score_to_severity(score)
                reason = (
                    f"Transaction amount {transaction.amount} exceeds merchant p99 "
                    f"threshold ({baseline_value})."
                )

        else:
            # Fallback handling (p50 or average) requiring fallback_multiplier
            ratio = transaction.amount / baseline_value
            evidence["ratio"] = float(round(ratio, 4))

            if ratio <= self.fallback_multiplier:
                triggered = False
                score = 0
                severity = Severity.NONE
                reason = (
                    f"Transaction amount {transaction.amount} is within fallback {baseline_type} "
                    f"multiplier ({float(round(ratio, 2))}x <= {float(self.fallback_multiplier)}x "
                    f"of {baseline_value})."
                )
            else:
                triggered = True
                deviation = ratio - self.fallback_multiplier
                score = min(100, 65 + int(deviation * Decimal("15")))
                severity = score_to_severity(score)
                reason = (
                    f"Transaction amount {transaction.amount} exceeds fallback {baseline_type} "
                    f"multiplier ({float(round(ratio, 2))}x > {float(self.fallback_multiplier)}x "
                    f"of {baseline_value})."
                )

        evidence["score"] = score
        evidence["severity"] = severity.value
        evidence["reason"] = reason

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            triggered=triggered,
            score=score,
            severity=severity,
            reason=reason,
            evidence=evidence,
            status=RuleExecutionStatus.SUCCESS,
        )

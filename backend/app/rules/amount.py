"""
Deterministic Unusual Amount Rule.
Detects transactions that are unusually large relative to a customer's historical median.
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.rules.base import FraudRule
from app.rules.helpers import calculate_median, score_to_severity
from app.schemas.context import FraudEvaluationContext
from app.schemas.rule import RuleExecutionStatus, RuleResult, Severity
from app.schemas.transaction import PreviousTransaction, Transaction


class UnusualAmountRule(FraudRule):
    """
    Evaluates whether the current transaction amount deviates significantly
    from the customer's historical median transaction baseline.
    Requires at least `minimum_history` historical transactions to establish a baseline.
    """

    def __init__(
        self,
        minimum_history: int = 3,
        amount_multiplier_threshold: float = 3.0,
        rule_id: str = "unusual_amount",
        rule_name: str = "Unusual Amount Rule",
        description: Optional[str] = None,
        is_enabled: bool = True,
    ):
        if minimum_history <= 0:
            raise ValueError("minimum_history must be positive")
        if amount_multiplier_threshold <= 1.0:
            raise ValueError("amount_multiplier_threshold must be greater than 1.0")

        desc = description or (
            f"Detects transactions where amount exceeds {amount_multiplier_threshold}x "
            f"the customer's historical median baseline (min {minimum_history} transactions)."
        )
        super().__init__(
            rule_id=rule_id,
            rule_name=rule_name,
            description=desc,
            is_enabled=is_enabled,
        )
        self.minimum_history = minimum_history
        self.amount_multiplier_threshold = Decimal(str(amount_multiplier_threshold))

    async def evaluate(
        self,
        transaction: Transaction,
        context: FraudEvaluationContext,
    ) -> RuleResult:
        # Collect distinct previous transactions from context
        previous_map: Dict[str, PreviousTransaction] = {}
        if context.recent_transactions:
            for pt in context.recent_transactions:
                previous_map[pt.transaction_id] = pt
        if context.previous_transaction:
            previous_map.setdefault(
                context.previous_transaction.transaction_id,
                context.previous_transaction,
            )

        # Exclude current transaction, non-null amounts, and future-dated transactions relative to current tx (Finding F-01)
        valid_history = [
            pt
            for pt in previous_map.values()
            if pt.transaction_id != transaction.transaction_id
            and pt.amount is not None
            and pt.timestamp <= transaction.timestamp
        ]

        historical_amounts: List[Decimal] = [pt.amount for pt in valid_history]

        evidence: Dict[str, Any] = {
            "current_amount": str(transaction.amount),
            "historical_transaction_count": len(historical_amounts),
            "historical_amounts": [str(a) for a in historical_amounts],
            "configured_threshold": float(self.amount_multiplier_threshold),
            "minimum_history_required": self.minimum_history,
            "insufficient_historical_data": False,
        }

        # Check minimum history requirement
        if len(historical_amounts) < self.minimum_history:
            reason = (
                f"Insufficient historical data: {len(historical_amounts)} transactions "
                f"available, but {self.minimum_history} required to establish baseline."
            )
            evidence.update(
                {
                    "median_baseline": None,
                    "multiplier_ratio": None,
                    "insufficient_historical_data": True,
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

        median_baseline = calculate_median(historical_amounts)
        evidence["median_baseline"] = str(median_baseline)

        # Zero baseline handling
        if median_baseline == Decimal("0.00"):
            if transaction.amount == Decimal("0.00"):
                triggered = False
                score = 0
                severity = Severity.NONE
                reason = "Both historical median baseline and current amount are zero."
                evidence["multiplier_ratio"] = 1.0
            else:
                triggered = True
                score = 70
                severity = Severity.HIGH
                reason = (
                    "Zero baseline anomaly: Historical median baseline is zero, "
                    f"but current transaction amount is {transaction.amount}."
                )
                evidence["multiplier_ratio"] = None
        else:
            ratio = transaction.amount / median_baseline
            evidence["multiplier_ratio"] = float(round(ratio, 4))

            if ratio < self.amount_multiplier_threshold:
                triggered = False
                score = 0
                severity = Severity.NONE
                reason = (
                    f"Transaction amount {transaction.amount} is within normal bounds "
                    f"({float(round(ratio, 2))}x median baseline of {median_baseline}, "
                    f"threshold: {float(self.amount_multiplier_threshold)}x)."
                )
            else:
                triggered = True
                # Score starts at 60 at threshold, increasing with ratio, capped at 100
                deviation = ratio - self.amount_multiplier_threshold
                score_increment = int(deviation * Decimal("20"))
                score = min(100, 60 + max(0, score_increment))
                severity = score_to_severity(score)
                reason = (
                    f"Unusually large transaction: amount {transaction.amount} is "
                    f"{float(round(ratio, 2))}x historical median baseline of {median_baseline} "
                    f"(threshold: {float(self.amount_multiplier_threshold)}x)."
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

"""
Deterministic Transaction Velocity Rule.
Detects unusually high transaction frequency within a configurable rolling time window.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.rules.base import FraudRule
from app.rules.helpers import score_to_severity
from app.schemas.context import FraudEvaluationContext
from app.schemas.rule import RuleExecutionStatus, RuleResult, Severity
from app.schemas.transaction import PreviousTransaction, Transaction


class TransactionVelocityRule(FraudRule):
    """
    Evaluates the frequency of transactions for a customer within a sliding window.
    Triggers if total count (including the current transaction) >= transaction_threshold.
    """

    def __init__(
        self,
        window_minutes: int = 10,
        transaction_threshold: int = 5,
        rule_id: str = "transaction_velocity",
        rule_name: str = "Transaction Velocity Rule",
        description: Optional[str] = None,
        is_enabled: bool = True,
    ):
        if window_minutes <= 0:
            raise ValueError("window_minutes must be positive")
        if transaction_threshold <= 0:
            raise ValueError("transaction_threshold must be positive")

        desc = description or (
            f"Detects if transaction velocity exceeds {transaction_threshold} "
            f"transactions within a {window_minutes}-minute sliding window."
        )
        super().__init__(
            rule_id=rule_id,
            rule_name=rule_name,
            description=desc,
            is_enabled=is_enabled,
        )
        self.window_minutes = window_minutes
        self.transaction_threshold = transaction_threshold

    async def evaluate(
        self,
        transaction: Transaction,
        context: FraudEvaluationContext,
    ) -> RuleResult:
        current_time: datetime = transaction.timestamp
        window_start: datetime = current_time - timedelta(minutes=self.window_minutes)

        # Gather previous transactions from context
        all_previous: Dict[str, PreviousTransaction] = {}

        if context.recent_transactions:
            for pt in context.recent_transactions:
                all_previous[pt.transaction_id] = pt

        if context.previous_transaction:
            all_previous.setdefault(
                context.previous_transaction.transaction_id,
                context.previous_transaction,
            )

        # Filter strictly within [current_time - window, current_time]
        # Exclude transactions that match the current transaction_id if present in history
        qualifying_previous: List[PreviousTransaction] = []
        for pt in all_previous.values():
            if pt.transaction_id == transaction.transaction_id:
                continue
            # Must fall inside [window_start, current_time]
            if window_start <= pt.timestamp <= current_time:
                qualifying_previous.append(pt)

        # Sort deterministically by timestamp, then transaction_id
        qualifying_previous.sort(key=lambda x: (x.timestamp, x.transaction_id))

        # Total count includes the current transaction
        count = len(qualifying_previous) + 1

        qualifying_ids = [pt.transaction_id for pt in qualifying_previous] + [
            transaction.transaction_id
        ]

        if count < self.transaction_threshold:
            triggered = False
            score = 0
            severity = Severity.NONE
            reason = (
                f"Transaction count ({count}) within {self.window_minutes}m window "
                f"is below threshold ({self.transaction_threshold})."
            )
        else:
            triggered = True
            # Base score 60 at threshold, increasing by 10 for each additional tx, capped at 100
            score = min(100, 60 + ((count - self.transaction_threshold) * 10))
            severity = score_to_severity(score)
            reason = (
                f"High transaction velocity detected: {count} transactions within "
                f"{self.window_minutes}m window (threshold: {self.transaction_threshold})."
            )

        evidence = {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "window_minutes": self.window_minutes,
            "transaction_threshold": self.transaction_threshold,
            "current_transaction_id": transaction.transaction_id,
            "current_transaction_timestamp": current_time.isoformat(),
            "window_start": window_start.isoformat(),
            "window_end": current_time.isoformat(),
            "transaction_count": count,
            "qualifying_transaction_ids": qualifying_ids,
            "score": score,
            "severity": severity.value,
            "reason": reason,
        }

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

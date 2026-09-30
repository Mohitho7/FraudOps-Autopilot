"""
Deterministic Impossible Location Rule.
Detects geographically impossible or implausible travel speeds between consecutive transactions
using the Haversine distance formula.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.rules.base import FraudRule
from app.rules.helpers import haversine_distance_km, score_to_severity
from app.schemas.context import FraudEvaluationContext
from app.schemas.rule import RuleExecutionStatus, RuleResult, Severity
from app.schemas.transaction import PreviousTransaction, Transaction


class ImpossibleLocationRule(FraudRule):
    """
    Evaluates geographical distance and elapsed time between the current transaction
    and the most recent valid historical transaction.
    Triggers if implied travel speed strictly exceeds `max_implied_speed_kmh`.
    """

    def __init__(
        self,
        max_implied_speed_kmh: float = 900.0,
        rule_id: str = "impossible_location",
        rule_name: str = "Impossible Location Rule",
        description: Optional[str] = None,
        is_enabled: bool = True,
    ):
        if max_implied_speed_kmh <= 0.0:
            raise ValueError("max_implied_speed_kmh must be positive")

        desc = description or (
            f"Detects impossible physical travel exceeding {max_implied_speed_kmh} km/h "
            "between consecutive transactions based on local Haversine calculations."
        )
        super().__init__(
            rule_id=rule_id,
            rule_name=rule_name,
            description=desc,
            is_enabled=is_enabled,
        )
        self.max_implied_speed_kmh = max_implied_speed_kmh

    async def evaluate(
        self,
        transaction: Transaction,
        context: FraudEvaluationContext,
    ) -> RuleResult:
        evidence: Dict[str, Any] = {
            "current_transaction_id": transaction.transaction_id,
            "current_latitude": transaction.latitude,
            "current_longitude": transaction.longitude,
            "previous_transaction_id": None,
            "previous_latitude": None,
            "previous_longitude": None,
            "distance_km": None,
            "elapsed_seconds": None,
            "elapsed_hours": None,
            "implied_speed_kmh": None,
            "speed_threshold_kmh": self.max_implied_speed_kmh,
            "missing_location_data": False,
        }

        # Check if current transaction has coordinates
        if transaction.latitude is None or transaction.longitude is None:
            reason = "Current transaction lacks GPS coordinates; location evaluation skipped."
            evidence.update(
                {
                    "missing_location_data": True,
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

        # Gather historical candidates from context
        all_previous: Dict[str, PreviousTransaction] = {}
        if context.recent_transactions:
            for pt in context.recent_transactions:
                all_previous[pt.transaction_id] = pt
        if context.previous_transaction:
            all_previous.setdefault(
                context.previous_transaction.transaction_id,
                context.previous_transaction,
            )

        # Filter:
        # 1. Ignore transactions with same ID as current
        # 2. Ignore transactions missing latitude or longitude
        # 3. Ignore transactions occurring after current transaction
        valid_candidates: List[PreviousTransaction] = []
        for pt in all_previous.values():
            if pt.transaction_id == transaction.transaction_id:
                continue
            if pt.latitude is None or pt.longitude is None:
                continue
            if pt.timestamp > transaction.timestamp:
                continue
            valid_candidates.append(pt)

        if not valid_candidates:
            reason = "No valid prior location history available for comparison."
            evidence.update(
                {
                    "missing_location_data": True,
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

        # Pick the most recent valid candidate before the current transaction
        valid_candidates.sort(key=lambda x: (x.timestamp, x.transaction_id), reverse=True)
        prior_tx = valid_candidates[0]

        evidence.update(
            {
                "previous_transaction_id": prior_tx.transaction_id,
                "previous_latitude": prior_tx.latitude,
                "previous_longitude": prior_tx.longitude,
            }
        )

        # Calculate elapsed time
        elapsed_seconds = (transaction.timestamp - prior_tx.timestamp).total_seconds()
        evidence["elapsed_seconds"] = round(elapsed_seconds, 2)

        if elapsed_seconds <= 0:
            reason = (
                f"Non-positive elapsed time ({elapsed_seconds}s) between transactions "
                f"'{prior_tx.transaction_id}' and '{transaction.transaction_id}'."
            )
            evidence.update(
                {
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

        elapsed_hours = elapsed_seconds / 3600.0
        evidence["elapsed_hours"] = round(elapsed_hours, 4)

        # Calculate distance
        distance_km = haversine_distance_km(
            lat1=prior_tx.latitude,
            lon1=prior_tx.longitude,
            lat2=transaction.latitude,
            lon2=transaction.longitude,
        )
        evidence["distance_km"] = distance_km

        # Same location check
        if distance_km <= 0.001:
            evidence["implied_speed_kmh"] = 0.0
            reason = "Transactions occurred at the same physical location."
            evidence.update(
                {
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

        implied_speed = distance_km / elapsed_hours
        evidence["implied_speed_kmh"] = round(implied_speed, 2)

        # Strict greater-than threshold comparison
        if implied_speed > self.max_implied_speed_kmh:
            triggered = True
            excess_ratio = (implied_speed - self.max_implied_speed_kmh) / self.max_implied_speed_kmh
            score = min(100, 70 + int(excess_ratio * 30))
            severity = score_to_severity(score)
            reason = (
                f"Impossible travel detected: implied speed of {round(implied_speed, 1)} km/h "
                f"({round(distance_km, 1)} km in {round(elapsed_hours, 2)}h) exceeds "
                f"maximum threshold of {self.max_implied_speed_kmh} km/h."
            )
        else:
            triggered = False
            score = 0
            severity = Severity.NONE
            reason = (
                f"Implied speed of {round(implied_speed, 1)} km/h is within plausible "
                f"threshold ({self.max_implied_speed_kmh} km/h)."
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

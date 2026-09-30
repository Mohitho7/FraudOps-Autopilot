"""
Deterministic Risk Scoring & Aggregation Engine.
Consumes structured RuleResult signals and synthesizes a case-level risk evaluation.
"""

from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Sequence, Set

from app.risk.config import RiskConfiguration
from app.risk.exceptions import (
    DuplicateRuleResultError,
    EmptyRuleResultsError,
    InvalidScoreError,
    UnknownRuleResultError,
)
from app.risk.helpers import (
    calculate_coverage,
    calculate_weighted_score,
    map_score_to_risk_level,
)
from app.schemas.evaluation import FraudEvaluation, RiskEvaluationStatus, RiskLevel
from app.schemas.rule import RuleExecutionStatus, RuleResult

logger = logging.getLogger(__name__)


class RiskEngine:
    """
    Synthesizes rule evaluation outcomes into an aggregate, normalized case-level risk score.

    Design Principles:
    - Decoupled: Does not execute or recalculate rules; consumes only structured RuleResults.
    - Deterministic: Pure mathematical weighted aggregation; zero machine-learning or LLM calls.
    - Resilient: Failed rules (ERROR) are normalized out of available weight rather than assumed clean.
    - Transparent: Distinguishes COMPLETE, PARTIAL, and NO_VALID_SIGNALS evaluations.
    """

    def __init__(self, config: Optional[RiskConfiguration] = None) -> None:
        """
        Initialize the RiskEngine.

        Args:
            config: Optional RiskConfiguration defining rule weights and thresholds.
                    Defaults to standard heuristic configuration.
        """
        self.config = config if config is not None else RiskConfiguration()

    def evaluate(
        self,
        rule_results: Sequence[RuleResult],
        transaction_id: Optional[str] = None,
    ) -> FraudEvaluation:
        """
        Aggregate a sequence of RuleResult objects into a unified FraudEvaluation.

        Args:
            rule_results: Collection of evaluated rule outcomes.
            transaction_id: Optional transaction identifier.

        Returns:
            FraudEvaluation: Standardized output with case-level score, level, and metadata.

        Raises:
            EmptyRuleResultsError: If rule_results is empty.
            DuplicateRuleResultError: If multiple results have the same rule_id.
            UnknownRuleResultError: If a result has an unconfigured rule_id.
            InvalidScoreError: If any result score is outside [0, 100].
        """
        if not rule_results:
            raise EmptyRuleResultsError("Cannot aggregate risk on an empty sequence of rule_results")

        tx_id = transaction_id or "unspecified_tx"

        # 1. Validation: check for duplicates, unknown rules, and valid scores
        seen_rule_ids: Set[str] = set()
        for r in rule_results:
            if not isinstance(r, RuleResult):
                raise TypeError(f"Expected RuleResult instance, got {type(r).__name__}")

            if r.rule_id in seen_rule_ids:
                raise DuplicateRuleResultError(
                    f"Duplicate RuleResult detected for rule_id '{r.rule_id}' in transaction '{tx_id}'"
                )
            seen_rule_ids.add(r.rule_id)

            if r.rule_id not in self.config.rule_weights:
                raise UnknownRuleResultError(
                    f"RuleResult '{r.rule_id}' has no configured weight in RiskConfiguration"
                )

            if not isinstance(r.score, (int, float)) or r.score < 0 or r.score > 100:
                raise InvalidScoreError(
                    f"RuleResult '{r.rule_id}' contains invalid score {r.score}. "
                    "Score must be a number between 0 and 100."
                )

        # 2. Partition results into successful, failed, triggered, and clean sets
        successful_results: List[RuleResult] = []
        failed_results: List[RuleResult] = []
        triggered_results: List[RuleResult] = []
        clean_results: List[RuleResult] = []

        for r in rule_results:
            if r.status == RuleExecutionStatus.SUCCESS:
                successful_results.append(r)
                if r.triggered:
                    triggered_results.append(r)
                else:
                    clean_results.append(r)
            else:
                failed_results.append(r)

        total_configured_weight = sum(self.config.rule_weights.values())

        # 3. Handle all-rules-failed state explicitly
        if not successful_results:
            evaluation_status = RiskEvaluationStatus.NO_VALID_SIGNALS
            risk_score = None
            risk_level = None
            coverage_ratio = 0.0
            available_weight = Decimal("0.00")
            raw_weighted_sum = None
        else:
            # 4. Compute normalized weighted score over available successful weights
            risk_score, raw_weighted_sum, available_weight = calculate_weighted_score(
                successful_results=successful_results,
                rule_weights=self.config.rule_weights,
            )

            coverage_ratio = calculate_coverage(
                available_weight=available_weight,
                total_weight=total_configured_weight,
            )

            # Determine completeness status
            if len(failed_results) == 0 and coverage_ratio >= 1.0:
                evaluation_status = RiskEvaluationStatus.COMPLETE
            else:
                evaluation_status = RiskEvaluationStatus.PARTIAL

            risk_level = map_score_to_risk_level(
                score=risk_score,
                low_threshold=self.config.low_threshold,
                medium_threshold=self.config.medium_threshold,
                high_threshold=self.config.high_threshold,
            )

        # 5. Build structured diagnostic metadata
        metadata: Dict[str, Any] = {
            "evaluation_status": evaluation_status.value,
            "risk_score": risk_score,
            "risk_level": risk_level.value if risk_level else None,
            "coverage_ratio": coverage_ratio,
            "available_weight": float(available_weight),
            "total_configured_weight": float(total_configured_weight),
            "raw_weighted_sum": float(raw_weighted_sum) if raw_weighted_sum is not None else None,
            "successful_rule_count": len(successful_results),
            "failed_rule_count": len(failed_results),
            "triggered_rule_count": len(triggered_results),
            "clean_rule_count": len(clean_results),
            "successful_rules": [r.rule_id for r in successful_results],
            "failed_rules": [r.rule_id for r in failed_results],
            "triggered_rules": [r.rule_id for r in triggered_results],
            "clean_rules": [r.rule_id for r in clean_results],
        }

        return FraudEvaluation(
            transaction_id=tx_id,
            rule_results=list(rule_results),  # Preserve original unmutated rule results
            risk_score=risk_score,
            risk_level=risk_level.value if risk_level else None,
            evaluation_status=evaluation_status.value,
            coverage_ratio=coverage_ratio,
            triggered_rules=[r.rule_id for r in triggered_results],
            clean_rules=[r.rule_id for r in clean_results],
            failed_rules=[r.rule_id for r in failed_results],
            metadata=metadata,
        )

    def evaluate_evaluation(self, evaluation: FraudEvaluation) -> FraudEvaluation:
        """
        Convenience method to process an existing un-scored FraudEvaluation
        produced by RuleEngine and enrich it with aggregated risk signals.

        Args:
            evaluation: FraudEvaluation containing transaction_id and rule_results.

        Returns:
            FraudEvaluation: Enriched FraudEvaluation with risk_score, risk_level, and metadata.
        """
        enriched = self.evaluate(
            rule_results=evaluation.rule_results,
            transaction_id=evaluation.transaction_id,
        )
        # Merge pre-existing metadata if any
        if evaluation.metadata:
            merged_meta = dict(evaluation.metadata)
            merged_meta.update(enriched.metadata)
            enriched = enriched.model_copy(update={"metadata": merged_meta})

        return enriched

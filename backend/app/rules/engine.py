"""
Deterministic Rule Engine for orchestrating fraud rule evaluations.
"""

import logging
import time
from typing import List, Optional

from app.rules.base import FraudRule
from app.rules.exceptions import RuleExecutionError
from app.rules.registry import RuleRegistry
from app.schemas.context import FraudEvaluationContext
from app.schemas.evaluation import FraudEvaluation
from app.schemas.rule import RuleExecutionStatus, RuleResult, Severity
from app.schemas.transaction import Transaction

logger = logging.getLogger(__name__)


class RuleEngine:
    """
    Executes all registered, enabled deterministic fraud rules against a Transaction and Context.

    Design Principles:
    - Decoupled: The engine depends only on the FraudRule interface and knows no concrete rule implementations.
    - Extensible: New rules can be plugged into the registry without modifying this engine.
    - Deterministic: Performs no risk aggregation, AI orchestration, or scoring calculation.
    """

    def __init__(
        self,
        registry: Optional[RuleRegistry] = None,
        fail_fast: bool = False,
    ) -> None:
        """
        Initialize the RuleEngine.

        Args:
            registry: Optional RuleRegistry instance holding registered rules.
                      If None, creates a fresh isolated RuleRegistry instance.
            fail_fast: If True, raises RuleExecutionError immediately upon rule failure.
                       If False (default), logs the failure and produces an explicit error RuleResult
                       with status=RuleExecutionStatus.ERROR so evaluation completes without silently hiding errors.
        """
        self.registry = registry if registry is not None else RuleRegistry()
        self.fail_fast = fail_fast

    async def evaluate_all(
        self,
        transaction: Transaction,
        context: FraudEvaluationContext,
    ) -> List[RuleResult]:
        """
        Execute all enabled rules in the registry against the transaction and context.

        Args:
            transaction: The transaction undergoing evaluation.
            context: Pre-fetched evaluation context.

        Returns:
            List[RuleResult]: Outcomes from all evaluated rules in registration order.
        """
        enabled_rules: List[FraudRule] = self.registry.get_enabled()
        results: List[RuleResult] = []

        for rule in enabled_rules:
            start_time = time.perf_counter()
            try:
                result = await rule.evaluate(transaction, context)
                elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)

                # Ensure execution duration is recorded if not provided by rule
                if result.execution_time_ms is None:
                    result = result.model_copy(update={"execution_time_ms": elapsed_ms})

                results.append(result)
            except Exception as e:
                elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)
                logger.error(
                    "Rule execution failed for '%s' (%s): %s",
                    rule.rule_id,
                    rule.rule_name,
                    str(e),
                    exc_info=True,
                )

                if self.fail_fast:
                    raise RuleExecutionError(
                        rule_id=rule.rule_id,
                        message=str(e),
                        original_exception=e,
                    ) from e

                # Create transparent error result so downstream consumers detect the failure
                error_result = RuleResult(
                    rule_id=rule.rule_id,
                    rule_name=rule.rule_name,
                    triggered=False,
                    score=0,
                    severity=Severity.NONE,
                    reason=f"Rule evaluation failed with error: {type(e).__name__}: {str(e)}",
                    evidence={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "execution_failed": True,
                    },
                    execution_time_ms=elapsed_ms,
                    status=RuleExecutionStatus.ERROR,
                )
                results.append(error_result)

        return results

    async def evaluate_transaction(
        self,
        transaction: Transaction,
        context: FraudEvaluationContext,
    ) -> FraudEvaluation:
        """
        Evaluate a transaction and package results into a FraudEvaluation structure.
        Note: Risk scoring is intentionally deferred to later batches.

        Args:
            transaction: The transaction undergoing evaluation.
            context: Pre-fetched evaluation context.

        Returns:
            FraudEvaluation: Aggregate container with transaction_id and rule_results.
        """
        results = await self.evaluate_all(transaction, context)
        return FraudEvaluation(
            transaction_id=transaction.transaction_id,
            rule_results=results,
            risk_score=None,
            risk_level=None,
        )

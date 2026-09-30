"""
Fraud Evaluation Application Service.
Coordinates the end-to-end deterministic evaluation pipeline:
Transaction -> ContextService -> RuleEngine -> RiskEngine -> EvaluationStore -> FraudEvaluation.
"""

import logging
from typing import Optional

from app.repositories.evaluation_store import EvaluationStoreInterface, InMemoryEvaluationStore
from app.risk.engine import RiskEngine
from app.rules.engine import RuleEngine
from app.rules.registry import create_default_rule_registry
from app.schemas.evaluation import FraudEvaluation
from app.schemas.transaction import Transaction
from app.services.context_service import ContextServiceInterface

logger = logging.getLogger(__name__)


class FraudEvaluationService:
    """
    Core application orchestration service for deterministic fraud evaluations.

    Design Principles:
    - Pure Orchestration: Coordinates ContextService, RuleEngine, and RiskEngine without
      re-implementing any fraud rules or mathematical risk aggregation.
    - Decoupled Persistence: Evaluation persistence delegates to EvaluationStoreInterface.
    - Observability: Logs lifecycle events (started, completed, errors) without logging
      sensitive personal payload data.
    - Determinism: Identical inputs yield identical FraudEvaluation outputs.
    """

    def __init__(
        self,
        context_service: ContextServiceInterface,
        rule_engine: Optional[RuleEngine] = None,
        risk_engine: Optional[RiskEngine] = None,
        evaluation_store: Optional[EvaluationStoreInterface] = None,
    ) -> None:
        """
        Initialize the FraudEvaluationService.

        Args:
            context_service: Service responsible for assembling FraudEvaluationContext.
            rule_engine: Deterministic rule execution engine (defaults to pre-configured 4 Batch 3 rules).
            risk_engine: Deterministic risk scoring engine (defaults to standard RiskConfiguration).
            evaluation_store: Storage adapter for persisting evaluation results (defaults to in-memory store).
        """
        if context_service is None:
            raise ValueError("context_service cannot be None")

        self.context_service = context_service
        self.rule_engine = rule_engine if rule_engine is not None else RuleEngine(registry=create_default_rule_registry())
        self.risk_engine = risk_engine if risk_engine is not None else RiskEngine()
        self.evaluation_store = evaluation_store if evaluation_store is not None else InMemoryEvaluationStore()

    async def evaluate(self, transaction: Transaction) -> FraudEvaluation:
        """
        Execute the full deterministic fraud evaluation workflow for a transaction.

        Pipeline Sequence:
        1. Context Enrichment: ContextService builds FraudEvaluationContext
        2. Rule Execution: RuleEngine evaluates registered FraudRules against context
        3. Risk Aggregation: RiskEngine synthesizes normalized risk score & status
        4. Persistence: Evaluation is saved to EvaluationStore
        5. Return FraudEvaluation

        Args:
            transaction: Validated incoming financial transaction.

        Returns:
            FraudEvaluation: Standardized case evaluation container.

        Raises:
            ContextRetrievalError: If the underlying context provider failed.
        """
        tx_id = transaction.transaction_id
        logger.info("Starting fraud evaluation for transaction '%s' (customer '%s')", tx_id, transaction.customer_id)

        # 1. Retrieve & Enrich Context
        context = await self.context_service.build_context(transaction)

        # 2. Execute Deterministic Fraud Rules
        rule_results = await self.rule_engine.evaluate_all(transaction, context)

        # 3. Aggregate Deterministic Risk Scores
        evaluation = self.risk_engine.evaluate(rule_results=rule_results, transaction_id=tx_id)

        # 4. Persist to Evaluation Store (if configured)
        if self.evaluation_store is not None:
            await self.evaluation_store.save(evaluation)

        logger.info(
            "Completed fraud evaluation for transaction '%s': score=%s, level=%s, status=%s, triggered=%s",
            tx_id,
            evaluation.risk_score,
            evaluation.risk_level,
            evaluation.evaluation_status,
            evaluation.triggered_rules,
        )

        return evaluation

    async def get_evaluation(self, transaction_id: str) -> Optional[FraudEvaluation]:
        """
        Retrieve a previously computed evaluation by transaction_id.

        Args:
            transaction_id: Transaction reference ID.

        Returns:
            FraudEvaluation or None if not found in store.
        """
        if self.evaluation_store is None:
            return None
        return await self.evaluation_store.get(transaction_id)

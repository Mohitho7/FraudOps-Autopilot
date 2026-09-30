"""
Context Service foundation and implementation.
Assembles the deterministic FraudEvaluationContext for an incoming transaction
by delegating to pluggable ContextProviderInterface implementations.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional

from app.repositories.context_provider import ContextProviderInterface
from app.schemas.context import FraudEvaluationContext
from app.schemas.customer import CustomerContext
from app.schemas.merchant import Merchant, MerchantStatistics
from app.schemas.transaction import PreviousTransaction, Transaction
from app.services.exceptions import ContextRetrievalError

logger = logging.getLogger(__name__)


class ContextServiceInterface(ABC):
    """
    Interface definition for context enrichment services.
    Concrete implementations fetch customer baselines, merchant operational data,
    and recent transactions, then assemble the FraudEvaluationContext required by RuleEngine.
    """

    @abstractmethod
    async def build_context(self, transaction: Transaction) -> FraudEvaluationContext:
        """
        Assemble the FraudEvaluationContext for a given transaction.

        Args:
            transaction: The incoming transaction to contextualize.

        Returns:
            FraudEvaluationContext: Populated contextual data for rule execution.

        Raises:
            ContextRetrievalError: If underlying provider encounters an operational/infrastructure failure.
        """
        pass


class ContextService(ContextServiceInterface):
    """
    Production deterministic context service.
    Orchestrates contextual data retrieval from a ContextProviderInterface without
    performing any fraud or risk calculations.

    Key Guarantees:
    - Timezone-safe comparison: All timestamp comparisons preserve timezone awareness.
    - Defense-in-depth: Excludes future-dated transactions (timestamp > current_timestamp).
    - Current transaction exclusion: Current transaction ID never leaks into historical context.
    - Deterministic ordering: History is ordered descending by timestamp, then transaction_id.
    - Bounded history: Recent history is capped at max_recent_transactions.
    - Resilient error semantics: Distinguishes expected missing data (returns None) from
      provider failures (raises ContextRetrievalError).
    """

    def __init__(
        self,
        provider: ContextProviderInterface,
        max_recent_transactions: int = 10,
    ) -> None:
        """
        Initialize ContextService.

        Args:
            provider: Pluggable context provider implementation.
            max_recent_transactions: Maximum number of recent transactions to assemble in history.
        """
        if provider is None:
            raise ValueError("ContextProvider cannot be None")
        if max_recent_transactions < 1:
            raise ValueError("max_recent_transactions must be at least 1")

        self.provider = provider
        self.max_recent_transactions = max_recent_transactions

    async def build_context(self, transaction: Transaction) -> FraudEvaluationContext:
        """
        Assemble the FraudEvaluationContext for an incoming transaction.

        Args:
            transaction: Incoming transaction to contextualize.

        Returns:
            FraudEvaluationContext: Context bundle for rule engine execution.

        Raises:
            ContextRetrievalError: When the provider fails unexpectedly.
        """
        current_time = transaction.timestamp
        tx_id = transaction.transaction_id

        # 1. Customer Context Retrieval
        try:
            customer_context = await self.provider.get_customer_context(transaction.customer_id)
        except Exception as e:
            logger.error("Provider failure retrieving customer '%s': %s", transaction.customer_id, e, exc_info=True)
            raise ContextRetrievalError(
                f"Failed to retrieve customer context for customer '{transaction.customer_id}': {e}",
                original_exception=e,
            ) from e

        # 2. Merchant Profile Retrieval
        try:
            merchant = await self.provider.get_merchant(transaction.merchant_id)
        except Exception as e:
            logger.error("Provider failure retrieving merchant '%s': %s", transaction.merchant_id, e, exc_info=True)
            raise ContextRetrievalError(
                f"Failed to retrieve merchant context for merchant '{transaction.merchant_id}': {e}",
                original_exception=e,
            ) from e

        # 3. Merchant Statistics Retrieval
        try:
            merchant_statistics = await self.provider.get_merchant_statistics(transaction.merchant_id)
        except Exception as e:
            logger.error("Provider failure retrieving statistics for merchant '%s': %s", transaction.merchant_id, e, exc_info=True)
            raise ContextRetrievalError(
                f"Failed to retrieve merchant statistics for merchant '{transaction.merchant_id}': {e}",
                original_exception=e,
            ) from e

        # If statistics not retrieved separately, fallback to embedded statistics on Merchant
        if merchant_statistics is None and merchant is not None and merchant.statistics is not None:
            merchant_statistics = merchant.statistics

        # 4. Historical Transaction Candidates Retrieval
        try:
            raw_recent = await self.provider.get_recent_transactions(
                customer_id=transaction.customer_id,
                current_timestamp=current_time,
                limit=self.max_recent_transactions,
            )
        except Exception as e:
            logger.error("Provider failure retrieving recent transactions for customer '%s': %s", transaction.customer_id, e, exc_info=True)
            raise ContextRetrievalError(
                f"Failed to retrieve recent transactions for customer '{transaction.customer_id}': {e}",
                original_exception=e,
            ) from e

        try:
            raw_prev = await self.provider.get_previous_transaction(
                customer_id=transaction.customer_id,
                current_timestamp=current_time,
            )
        except Exception as e:
            logger.error("Provider failure retrieving previous transaction for customer '%s': %s", transaction.customer_id, e, exc_info=True)
            raise ContextRetrievalError(
                f"Failed to retrieve previous transaction for customer '{transaction.customer_id}': {e}",
                original_exception=e,
            ) from e

        # 5. Defense-in-Depth Filtering & Deduplication
        # Collect candidate historical transactions, deduplicate by transaction_id
        dedup_map: Dict[str, PreviousTransaction] = {}

        candidate_list: List[PreviousTransaction] = list(raw_recent) if raw_recent else []
        if raw_prev is not None:
            candidate_list.append(raw_prev)

        for pt in candidate_list:
            if not isinstance(pt, PreviousTransaction):
                continue
            # Rule 1: Exclude the current transaction if present in historical source
            if pt.transaction_id == tx_id:
                continue
            # Rule 2: Defense-in-depth: Exclude future-dated transactions strictly
            if pt.timestamp > current_time:
                continue
            dedup_map[pt.transaction_id] = pt

        # 6. Deterministic Ordering
        # Order descending by timestamp (most recent first), then descending by transaction_id for deterministic ties
        sorted_history = sorted(
            dedup_map.values(),
            key=lambda pt: (pt.timestamp, pt.transaction_id),
            reverse=True,
        )

        # 7. Bounded Recent History
        recent_transactions = sorted_history[: self.max_recent_transactions]

        # 8. Previous Transaction Selection
        previous_transaction: Optional[PreviousTransaction] = None
        if (
            raw_prev is not None
            and raw_prev.transaction_id != tx_id
            and raw_prev.timestamp <= current_time
        ):
            previous_transaction = raw_prev
        elif sorted_history:
            # Fallback to the most recent historical item
            previous_transaction = sorted_history[0]

        # 9. Assemble Context Bundle
        metadata = {
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "max_recent_transactions_configured": self.max_recent_transactions,
            "recent_transaction_count": len(recent_transactions),
            "has_previous_transaction": previous_transaction is not None,
            "has_customer_context": customer_context is not None,
            "has_merchant_context": merchant is not None,
            "has_merchant_statistics": merchant_statistics is not None,
        }

        return FraudEvaluationContext(
            customer_context=customer_context,
            merchant_context=merchant,
            merchant_statistics=merchant_statistics,
            previous_transaction=previous_transaction,
            recent_transactions=recent_transactions,
            metadata=metadata,
        )

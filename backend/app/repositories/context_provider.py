"""
Context provider interfaces and in-memory reference implementations.
Provides the abstraction boundary so persistence (PostgreSQL/SQLAlchemy by Member 4)
can be plugged in without modifying ContextService, RuleEngine, or FraudRules.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional

from app.schemas.customer import CustomerContext
from app.schemas.merchant import Merchant, MerchantStatistics
from app.schemas.transaction import PreviousTransaction


class ContextProviderInterface(ABC):
    """
    Abstract contract for fetching contextual entities required for fraud evaluation.
    Concrete implementations may connect to PostgreSQL, Redis, or mock in-memory stores.
    """

    @abstractmethod
    async def get_customer_context(self, customer_id: str) -> Optional[CustomerContext]:
        """
        Retrieve customer contextual profile.
        Returns None if customer has no prior recorded history.
        """
        pass

    @abstractmethod
    async def get_merchant(self, merchant_id: str) -> Optional[Merchant]:
        """
        Retrieve merchant profile information.
        Returns None if merchant profile is not registered.
        """
        pass

    @abstractmethod
    async def get_merchant_statistics(self, merchant_id: str) -> Optional[MerchantStatistics]:
        """
        Retrieve statistical distribution metrics for a merchant.
        Returns None if statistical profile is not yet computed.
        """
        pass

    @abstractmethod
    async def get_recent_transactions(
        self,
        customer_id: str,
        current_timestamp: datetime,
        limit: int = 10,
    ) -> List[PreviousTransaction]:
        """
        Retrieve recent transactions for a customer prior to or at current_timestamp.
        """
        pass

    @abstractmethod
    async def get_previous_transaction(
        self,
        customer_id: str,
        current_timestamp: datetime,
    ) -> Optional[PreviousTransaction]:
        """
        Retrieve the most recent transaction prior to or at current_timestamp.
        """
        pass


class InMemoryContextProvider(ContextProviderInterface):
    """
    Lightweight, deterministic in-memory context provider for tests and local development.
    Does NOT connect to any database.
    """

    def __init__(self) -> None:
        self.customers: Dict[str, CustomerContext] = {}
        self.merchants: Dict[str, Merchant] = {}
        self.merchant_statistics: Dict[str, MerchantStatistics] = {}
        # Mapping: customer_id -> List[PreviousTransaction]
        self.transaction_history: Dict[str, List[PreviousTransaction]] = {}

    def add_customer(self, customer: CustomerContext) -> None:
        self.customers[customer.customer_id] = customer

    def add_merchant(self, merchant: Merchant) -> None:
        self.merchants[merchant.merchant_id] = merchant
        if merchant.statistics:
            self.merchant_statistics[merchant.merchant_id] = merchant.statistics

    def add_merchant_statistics(self, merchant_id: str, statistics: MerchantStatistics) -> None:
        self.merchant_statistics[merchant_id] = statistics

    def add_previous_transaction(self, customer_id: str, transaction: PreviousTransaction) -> None:
        if customer_id not in self.transaction_history:
            self.transaction_history[customer_id] = []
        self.transaction_history[customer_id].append(transaction)

    def set_transaction_history(self, customer_id: str, transactions: List[PreviousTransaction]) -> None:
        self.transaction_history[customer_id] = list(transactions)

    def clear(self) -> None:
        self.customers.clear()
        self.merchants.clear()
        self.merchant_statistics.clear()
        self.transaction_history.clear()

    async def get_customer_context(self, customer_id: str) -> Optional[CustomerContext]:
        return self.customers.get(customer_id)

    async def get_merchant(self, merchant_id: str) -> Optional[Merchant]:
        return self.merchants.get(merchant_id)

    async def get_merchant_statistics(self, merchant_id: str) -> Optional[MerchantStatistics]:
        if merchant_id in self.merchant_statistics:
            return self.merchant_statistics[merchant_id]
        merchant = self.merchants.get(merchant_id)
        if merchant and merchant.statistics:
            return merchant.statistics
        return None

    async def get_recent_transactions(
        self,
        customer_id: str,
        current_timestamp: datetime,
        limit: int = 10,
    ) -> List[PreviousTransaction]:
        history = self.transaction_history.get(customer_id, [])
        # Return all candidate transactions (ContextService will enforce defense-in-depth filtering)
        return list(history)

    async def get_previous_transaction(
        self,
        customer_id: str,
        current_timestamp: datetime,
    ) -> Optional[PreviousTransaction]:
        history = self.transaction_history.get(customer_id, [])
        eligible = [pt for pt in history if pt.timestamp <= current_timestamp]
        if not eligible:
            return None
        # Sort descending by timestamp, then transaction_id
        eligible.sort(key=lambda pt: (pt.timestamp, pt.transaction_id), reverse=True)
        return eligible[0]

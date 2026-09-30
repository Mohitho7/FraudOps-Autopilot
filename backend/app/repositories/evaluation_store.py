"""
Evaluation store interfaces and in-memory reference implementation.
Provides the persistence abstraction boundary for FraudEvaluation objects
so Member 4 can attach a PostgreSQL/database adapter later without altering service or API layers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional

from app.schemas.evaluation import FraudEvaluation


class EvaluationStoreInterface(ABC):
    """
    Abstract storage interface for persisting and retrieving FraudEvaluation outcomes.
    """

    @abstractmethod
    async def save(self, evaluation: FraudEvaluation) -> None:
        """
        Persist a FraudEvaluation record.
        """
        pass

    @abstractmethod
    async def get(self, transaction_id: str) -> Optional[FraudEvaluation]:
        """
        Retrieve a FraudEvaluation record by transaction_id.
        Returns None if not found.
        """
        pass


class InMemoryEvaluationStore(EvaluationStoreInterface):
    """
    Lightweight, deterministic in-memory storage adapter for testing and local development.
    Does NOT provide durable storage. A PostgreSQL adapter will be supplied by Member 4.
    """

    def __init__(self) -> None:
        self._evaluations: Dict[str, FraudEvaluation] = {}

    async def save(self, evaluation: FraudEvaluation) -> None:
        """
        Save or overwrite an evaluation in memory.
        """
        self._evaluations[evaluation.transaction_id] = evaluation

    async def get(self, transaction_id: str) -> Optional[FraudEvaluation]:
        """
        Retrieve an evaluation by transaction_id from in-memory dictionary.
        """
        return self._evaluations.get(transaction_id)

    def clear(self) -> None:
        """
        Clear in-memory storage. Useful for test isolation.
        """
        self._evaluations.clear()

    def __len__(self) -> int:
        return len(self._evaluations)

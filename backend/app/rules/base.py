"""
Abstract base interface for deterministic fraud detection rules.
"""

from abc import ABC, abstractmethod
from typing import Optional

from app.schemas.context import FraudEvaluationContext
from app.schemas.rule import RuleResult
from app.schemas.transaction import Transaction


class FraudRule(ABC):
    """
    Abstract base class for all deterministic fraud rules.
    Every rule must implement the asynchronous `evaluate` method and declare
    unique `rule_id` and `rule_name` properties.

    Architectural Principle:
    - Rules are deterministic and compute only against the provided Transaction and Context.
    - Rules do NOT perform external I/O, database fetching, or LLM reasoning.
    """
    rule_id: str
    rule_name: str
    description: str = ""
    is_enabled: bool = True

    def __init__(
        self,
        rule_id: Optional[str] = None,
        rule_name: Optional[str] = None,
        description: Optional[str] = None,
        is_enabled: bool = True,
    ):
        if rule_id is not None:
            self.rule_id = rule_id
        if rule_name is not None:
            self.rule_name = rule_name
        if description is not None:
            self.description = description
        self.is_enabled = is_enabled

    @abstractmethod
    async def evaluate(
        self,
        transaction: Transaction,
        context: FraudEvaluationContext,
    ) -> RuleResult:
        """
        Evaluate the transaction and contextual information.

        Args:
            transaction: The incoming transaction to evaluate.
            context: Pre-fetched contextual data (customer history, merchant profile, etc.).

        Returns:
            RuleResult: Structured outcome containing triggered status, score, severity, reason, and evidence.
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id='{getattr(self, 'rule_id', 'unassigned')}', enabled={self.is_enabled})>"

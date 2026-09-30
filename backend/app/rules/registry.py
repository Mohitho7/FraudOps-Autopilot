"""
Rule registry for managing and looking up fraud evaluation rules.
"""

import logging
from typing import Dict, List, Optional

from app.rules.base import FraudRule
from app.rules.exceptions import DuplicateRuleError, InvalidRuleError, RuleNotFoundError

logger = logging.getLogger(__name__)


class RuleRegistry:
    """
    Central registry for storing and retrieving configured FraudRule instances.
    Enforces interface conformance and unique rule identifiers.
    """

    def __init__(self) -> None:
        self._rules: Dict[str, FraudRule] = {}

    def register(self, rule: FraudRule) -> None:
        """
        Register a new FraudRule instance.

        Args:
            rule: An instance conforming to FraudRule.

        Raises:
            InvalidRuleError: If the object is not a FraudRule or lacks a valid rule_id.
            DuplicateRuleError: If a rule with the same rule_id is already registered.
        """
        if not isinstance(rule, FraudRule):
            raise InvalidRuleError(f"Expected instance of FraudRule, got {type(rule).__name__}")

        rule_id = getattr(rule, "rule_id", None)
        if not rule_id or not isinstance(rule_id, str) or not rule_id.strip():
            raise InvalidRuleError("Rule must have a valid non-empty string 'rule_id'")

        rule_id = rule_id.strip()

        if rule_id in self._rules:
            raise DuplicateRuleError(f"Rule with id '{rule_id}' is already registered")

        self._rules[rule_id] = rule
        logger.info("Registered fraud rule: %s ('%s')", rule_id, getattr(rule, "rule_name", "unnamed"))

    def unregister(self, rule_id: str) -> FraudRule:
        """
        Unregister and return a rule by ID.

        Args:
            rule_id: The ID of the rule to remove.

        Returns:
            The unregistered FraudRule.

        Raises:
            RuleNotFoundError: If the rule_id is not registered.
        """
        if rule_id not in self._rules:
            raise RuleNotFoundError(f"Rule with id '{rule_id}' is not registered")
        removed = self._rules.pop(rule_id)
        logger.info("Unregistered fraud rule: %s", rule_id)
        return removed

    def remove(self, rule_id: str) -> FraudRule:
        """Alias for unregister."""
        return self.unregister(rule_id)

    def get(self, rule_id: str) -> Optional[FraudRule]:
        """
        Retrieve a registered rule by its ID, or None if not found.
        """
        return self._rules.get(rule_id)

    def get_or_raise(self, rule_id: str) -> FraudRule:
        """
        Retrieve a registered rule by its ID, or raise RuleNotFoundError.
        """
        if rule_id not in self._rules:
            raise RuleNotFoundError(f"Rule with id '{rule_id}' is not registered")
        return self._rules[rule_id]

    def get_all(self) -> List[FraudRule]:
        """
        Return a list of all registered rules.
        """
        return list(self._rules.values())

    def get_enabled(self) -> List[FraudRule]:
        """
        Return a list of all registered rules that have is_enabled=True.
        """
        return [rule for rule in self._rules.values() if rule.is_enabled]

    def clear(self) -> None:
        """
        Remove all rules from the registry. Useful for test isolation.
        """
        self._rules.clear()

    def __len__(self) -> int:
        return len(self._rules)

    def __contains__(self, rule_id: str) -> bool:
        return rule_id in self._rules

    def __repr__(self) -> str:
        return f"<RuleRegistry(total_rules={len(self._rules)}, enabled={len(self.get_enabled())})>"


# Default global registry instance
default_rule_registry = RuleRegistry()


def create_default_rule_registry() -> RuleRegistry:
    """
    Create a fresh, isolated RuleRegistry pre-populated with all four
    production deterministic fraud rules:
    - TransactionVelocityRule ('transaction_velocity')
    - UnusualAmountRule ('unusual_amount')
    - ImpossibleLocationRule ('impossible_location')
    - MerchantContextRule ('merchant_context')
    """
    from app.rules.amount import UnusualAmountRule
    from app.rules.location import ImpossibleLocationRule
    from app.rules.merchant_context import MerchantContextRule
    from app.rules.velocity import TransactionVelocityRule

    registry = RuleRegistry()
    registry.register(TransactionVelocityRule())
    registry.register(UnusualAmountRule())
    registry.register(ImpossibleLocationRule())
    registry.register(MerchantContextRule())
    return registry

"""
Deterministic fraud rule engine and rule definitions.
"""

from app.rules.amount import UnusualAmountRule
from app.rules.base import FraudRule
from app.rules.engine import RuleEngine
from app.rules.exceptions import (
    DuplicateRuleError,
    InvalidRuleError,
    RuleEngineError,
    RuleExecutionError,
    RuleNotFoundError,
)
from app.rules.location import ImpossibleLocationRule
from app.rules.merchant_context import MerchantContextRule
from app.rules.registry import (
    RuleRegistry,
    create_default_rule_registry,
    default_rule_registry,
)
from app.rules.velocity import TransactionVelocityRule
from app.schemas.rule import RuleExecutionStatus, RuleResult, Severity

__all__ = [
    "DuplicateRuleError",
    "FraudRule",
    "ImpossibleLocationRule",
    "InvalidRuleError",
    "MerchantContextRule",
    "RuleEngine",
    "RuleEngineError",
    "RuleExecutionError",
    "RuleExecutionStatus",
    "RuleNotFoundError",
    "RuleRegistry",
    "RuleResult",
    "Severity",
    "TransactionVelocityRule",
    "UnusualAmountRule",
    "create_default_rule_registry",
    "default_rule_registry",
]

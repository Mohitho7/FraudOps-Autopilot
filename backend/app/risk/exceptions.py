"""
Domain exceptions for the Risk Scoring & Aggregation Engine.
"""


class RiskEngineError(Exception):
    """Base exception for all Risk Engine errors."""
    pass


class RiskConfigurationError(RiskEngineError):
    """Raised when risk configuration or rule weights are invalid."""
    pass


class DuplicateRuleResultError(RiskEngineError):
    """Raised when duplicate RuleResult instances for the same rule_id are detected in evaluation input."""
    pass


class UnknownRuleResultError(RiskEngineError):
    """Raised when a RuleResult with an unconfigured rule_id is evaluated."""
    pass


class InvalidScoreError(RiskEngineError):
    """Raised when a RuleResult score violates boundary constraints [0, 100]."""
    pass


class EmptyRuleResultsError(RiskEngineError):
    """Raised when attempting to evaluate an empty sequence of RuleResults."""
    pass

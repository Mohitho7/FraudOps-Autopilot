"""
Exceptions raised during rule registry management and rule engine execution.
"""


class RuleEngineError(Exception):
    """Base exception for all Rule Engine errors."""
    pass


class DuplicateRuleError(RuleEngineError):
    """Raised when attempting to register a rule with an ID that already exists."""
    pass


class RuleNotFoundError(RuleEngineError):
    """Raised when attempting to access or unregister a non-existent rule ID."""
    pass


class InvalidRuleError(RuleEngineError):
    """Raised when an object does not conform to the FraudRule interface."""
    pass


class RuleExecutionError(RuleEngineError):
    """Raised when a rule encounters an unhandled exception during evaluation."""
    def __init__(self, rule_id: str, message: str, original_exception: Exception | None = None):
        super().__init__(f"Rule '{rule_id}' failed during evaluation: {message}")
        self.rule_id = rule_id
        self.original_exception = original_exception

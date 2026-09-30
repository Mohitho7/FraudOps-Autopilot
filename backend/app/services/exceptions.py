"""
Exceptions for application and context retrieval services.
"""

from typing import Optional


class ContextRetrievalError(Exception):
    """
    Raised when an underlying context provider encounters an operational,
    network, or database failure during context retrieval.
    Downstream consumers and API layers translate this to HTTP 503 Service Unavailable,
    ensuring infrastructure failures never masquerade as clean/safe evaluations.
    """

    def __init__(self, message: str, original_exception: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.message = message
        self.original_exception = original_exception


class FraudEvaluationServiceError(Exception):
    """
    Raised when the high-level FraudEvaluationService encounters an unrecoverable orchestration error.
    """

    def __init__(self, message: str, original_exception: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.message = message
        self.original_exception = original_exception

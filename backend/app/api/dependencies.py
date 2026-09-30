"""
FastAPI dependency injection providers for services and repositories.
"""

from fastapi import Depends

from app.repositories.context_provider import ContextProviderInterface, InMemoryContextProvider
from app.repositories.evaluation_store import EvaluationStoreInterface, InMemoryEvaluationStore
from app.services.context_service import ContextService
from app.services.fraud_evaluation_service import FraudEvaluationService

# Default in-memory reference adapters for local execution and development
default_context_provider = InMemoryContextProvider()
default_evaluation_store = InMemoryEvaluationStore()


def get_context_provider() -> ContextProviderInterface:
    """
    Provide the active context provider instance.
    Can be overridden via app.dependency_overrides in tests or when Member 4 connects PostgreSQL.
    """
    return default_context_provider


def get_evaluation_store() -> EvaluationStoreInterface:
    """
    Provide the active evaluation store instance.
    Can be overridden via app.dependency_overrides in tests or when Member 4 connects PostgreSQL.
    """
    return default_evaluation_store


def get_fraud_evaluation_service(
    provider: ContextProviderInterface = Depends(get_context_provider),
    store: EvaluationStoreInterface = Depends(get_evaluation_store),
) -> FraudEvaluationService:
    """
    Provide an initialized FraudEvaluationService instance with configured dependencies.
    """
    context_service = ContextService(provider=provider)
    return FraudEvaluationService(context_service=context_service, evaluation_store=store)

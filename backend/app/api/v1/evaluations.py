"""
Fraud Evaluation API endpoints.
Exposes synchronous evaluation and retrieval endpoints without implementing any fraud rules.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_fraud_evaluation_service
from app.schemas.evaluation import FraudEvaluation
from app.schemas.transaction import Transaction
from app.services.exceptions import ContextRetrievalError
from app.services.fraud_evaluation_service import FraudEvaluationService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/fraud/evaluations",
    tags=["evaluations"],
)


@router.post(
    "",
    response_model=FraudEvaluation,
    status_code=status.HTTP_200_OK,
    summary="Evaluate transaction fraud risk",
    description="Asynchronously evaluates a financial transaction through deterministic fraud rules and risk aggregation.",
)
async def evaluate_transaction(
    transaction: Transaction,
    service: FraudEvaluationService = Depends(get_fraud_evaluation_service),
) -> FraudEvaluation:
    """
    Execute deterministic fraud evaluation for a transaction payload.
    """
    try:
        return await service.evaluate(transaction)
    except ContextRetrievalError as e:
        logger.error("Context retrieval unavailable during evaluation of tx '%s': %s", transaction.transaction_id, e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Context retrieval unavailable: {e.message}",
        ) from e
    except Exception as e:
        logger.error("Unexpected error during evaluation of tx '%s': %s", transaction.transaction_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal fraud evaluation failure",
        ) from e


@router.get(
    "/{transaction_id}",
    response_model=FraudEvaluation,
    status_code=status.HTTP_200_OK,
    summary="Get fraud evaluation by transaction ID",
    description="Retrieve a previously calculated fraud evaluation outcome.",
)
async def get_evaluation(
    transaction_id: str,
    service: FraudEvaluationService = Depends(get_fraud_evaluation_service),
) -> FraudEvaluation:
    """
    Retrieve stored fraud evaluation by transaction reference identifier.
    """
    evaluation = await service.get_evaluation(transaction_id)
    if evaluation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation for transaction '{transaction_id}' not found",
        )
    return evaluation

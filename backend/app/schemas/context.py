"""
Central context schema passed to fraud evaluation rules.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.customer import CustomerContext
from app.schemas.merchant import Merchant, MerchantStatistics
from app.schemas.transaction import PreviousTransaction


class FraudEvaluationContext(BaseModel):
    """
    Central evaluation context encapsulating customer baseline, merchant profile,
    and historical transactions. Rules receive this context and evaluate in-memory
    without making individual database queries.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    customer_context: Optional[CustomerContext] = Field(default=None, description="Customer behavioral baseline")
    merchant_context: Optional[Merchant] = Field(default=None, description="Merchant profile and operating details")
    merchant_statistics: Optional[MerchantStatistics] = Field(default=None, description="Merchant statistical distribution")
    previous_transaction: Optional[PreviousTransaction] = Field(default=None, description="Most recent prior transaction")
    recent_transactions: List[PreviousTransaction] = Field(default_factory=list, description="Recent transaction window for velocity checks")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary extensible metadata for evaluation context")

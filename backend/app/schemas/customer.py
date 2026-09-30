"""
Customer domain and contextual profile schemas.
"""

from decimal import Decimal
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class CustomerContext(BaseModel):
    """
    Contextual profile of a customer used by behavioral and amount anomaly rules.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    customer_id: str = Field(..., min_length=1, description="Unique customer reference ID")
    average_transaction_amount: Optional[Decimal] = Field(default=None, ge=Decimal("0.00"), description="Historical average transaction amount")
    transaction_count: int = Field(default=0, ge=0, description="Total historical transaction count")
    recent_transaction_count: int = Field(default=0, ge=0, description="Recent transaction count within observation window")
    historical_activity_summary: Dict[str, Any] = Field(default_factory=dict, description="Structured historical activity indicators")

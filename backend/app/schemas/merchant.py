"""
Merchant domain and business-context schemas.
"""

from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class OperatingHours(BaseModel):
    """
    Standard operating hours for a merchant location or business.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    start_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):[0-5]\d$", description="Opening time in HH:MM format (00:00 to 23:59)")
    end_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):[0-5]\d$", description="Closing time in HH:MM format (00:00 to 23:59)")
    timezone: str = Field(default="UTC", description="Operating timezone (e.g. Asia/Kolkata, UTC)")


class MerchantStatistics(BaseModel):
    """
    Historical statistical baseline for a merchant used by business context rules.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    transaction_count: int = Field(default=0, ge=0, description="Total historical transaction count")
    average_transaction_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"), description="Average transaction amount")
    p50: Optional[Decimal] = Field(default=None, ge=Decimal("0.00"), description="50th percentile transaction amount")
    p95: Optional[Decimal] = Field(default=None, ge=Decimal("0.00"), description="95th percentile transaction amount")
    p99: Optional[Decimal] = Field(default=None, ge=Decimal("0.00"), description="99th percentile transaction amount")
    typical_daily_volume: Optional[Decimal] = Field(default=None, ge=Decimal("0.00"), description="Typical daily financial volume")


class Merchant(BaseModel):
    """
    Merchant profile data structure supporting business-context risk evaluation.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    merchant_id: str = Field(..., min_length=1, description="Unique merchant reference ID")
    merchant_name: str = Field(..., min_length=1, description="Registered merchant or legal name")
    category: str = Field(..., min_length=1, description="Merchant category (e.g. JEWELRY, ELECTRONICS, FUEL, GROCERY)")
    business_type: Optional[str] = Field(default=None, description="Legal business classification (e.g. RETAIL, ONLINE)")
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0, description="Merchant physical latitude")
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0, description="Merchant physical longitude")
    operating_hours: Optional[OperatingHours] = Field(default=None, description="Merchant regular operating hours")
    statistics: Optional[MerchantStatistics] = Field(default=None, description="Merchant statistical profile")

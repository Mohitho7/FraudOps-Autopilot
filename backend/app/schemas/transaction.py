"""
Transaction domain and contract schemas.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Transaction(BaseModel):
    """
    Core transaction model representing a financial transaction event.
    Uses Decimal for safe monetary values and enforces timezone-aware timestamps.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    transaction_id: str = Field(..., min_length=1, description="Unique transaction reference ID")
    customer_id: str = Field(..., min_length=1, description="Unique identifier of customer")
    merchant_id: str = Field(..., min_length=1, description="Unique identifier of merchant")
    amount: Decimal = Field(..., gt=Decimal("0.00"), description="Monetary transaction amount (safe Decimal)")
    currency: str = Field(default="INR", min_length=3, max_length=3, description="ISO-4217 3-letter currency code")
    timestamp: datetime = Field(..., description="Timezone-aware transaction timestamp")
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0, description="Latitude (-90 to 90)")
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0, description="Longitude (-180 to 180)")
    transaction_type: Optional[str] = Field(default="PURCHASE", description="Type of transaction (e.g. PURCHASE, TRANSFER)")
    device_id: Optional[str] = Field(default=None, description="Client device identifier")
    ip_address: Optional[str] = Field(default=None, description="Client IP address")
    country: Optional[str] = Field(default=None, description="Transaction country code or name")
    merchant_label: Optional[str] = Field(default=None, description="Display merchant label")

    @field_validator("timestamp")
    @classmethod
    def ensure_timezone_aware(cls, v: datetime) -> datetime:
        """
        Enforce that transaction timestamps are timezone-aware (defaults naive to UTC).
        """
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        """
        Normalize currency code to uppercase.
        """
        return v.upper()


class PreviousTransaction(BaseModel):
    """
    Historical transaction snapshot used for context evaluation (e.g. velocity, impossible travel).
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    transaction_id: str = Field(..., min_length=1, description="Unique identifier of previous transaction")
    timestamp: datetime = Field(..., description="Timestamp of previous transaction")
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0, description="Latitude of previous transaction")
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0, description="Longitude of previous transaction")
    amount: Decimal = Field(..., gt=Decimal("0.00"), description="Amount of previous transaction")
    merchant_id: str = Field(..., min_length=1, description="Merchant ID of previous transaction")
    device_id: Optional[str] = Field(default=None, description="Client device identifier of previous transaction")
    ip_address: Optional[str] = Field(default=None, description="Client IP address of previous transaction")

    @field_validator("timestamp")
    @classmethod
    def ensure_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

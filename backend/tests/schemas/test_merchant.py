"""
Tests for Merchant, OperatingHours, and MerchantStatistics schemas.
"""

from decimal import Decimal
import pytest
from pydantic import ValidationError

from app.schemas.merchant import Merchant, MerchantStatistics, OperatingHours


def test_valid_merchant_with_operating_hours_and_statistics():
    hours = OperatingHours(start_time="09:00", end_time="21:00", timezone="Asia/Kolkata")
    stats = MerchantStatistics(
        transaction_count=1200,
        average_transaction_amount=Decimal("540.25"),
        p50=Decimal("350.00"),
        p95=Decimal("1500.00"),
        p99=Decimal("4500.00"),
        typical_daily_volume=Decimal("50000.00"),
    )
    merchant = Merchant(
        merchant_id="merch_100",
        merchant_name="City Gold Palace",
        category="JEWELRY",
        business_type="RETAIL",
        latitude=19.0760,
        longitude=72.8777,
        operating_hours=hours,
        statistics=stats,
    )
    assert merchant.merchant_id == "merch_100"
    assert merchant.category == "JEWELRY"
    assert merchant.operating_hours.start_time == "09:00"
    assert merchant.statistics.average_transaction_amount == Decimal("540.25")


def test_invalid_operating_hours_pattern():
    with pytest.raises(ValidationError):
        OperatingHours(start_time="9am", end_time="9pm")

    with pytest.raises(ValidationError):
        OperatingHours(start_time="25:00", end_time="12:00")


def test_merchant_minimal_defaults():
    merchant = Merchant(
        merchant_id="merch_200",
        merchant_name="Corner Store",
        category="GROCERY",
    )
    assert merchant.business_type is None
    assert merchant.latitude is None
    assert merchant.operating_hours is None
    assert merchant.statistics is None

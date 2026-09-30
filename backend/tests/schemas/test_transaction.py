"""
Tests for Transaction and PreviousTransaction domain models.
"""

from datetime import datetime, timezone
from decimal import Decimal
import pytest
from pydantic import ValidationError

from app.schemas.transaction import PreviousTransaction, Transaction


def test_valid_transaction_creation():
    tx = Transaction(
        transaction_id="tx_12345",
        customer_id="cust_999",
        merchant_id="merch_888",
        amount=Decimal("1500.50"),
        currency="inr",
        timestamp=datetime(2026, 9, 30, 10, 0, 0, tzinfo=timezone.utc),
        latitude=19.0760,
        longitude=72.8777,
        transaction_type="PURCHASE",
        device_id="dev_abc",
        ip_address="192.168.1.1",
        country="India",
        merchant_label="ABC Jewelers",
    )
    assert tx.transaction_id == "tx_12345"
    assert tx.amount == Decimal("1500.50")
    assert tx.currency == "INR"  # Auto-uppercased
    assert tx.latitude == 19.0760
    assert tx.longitude == 72.8777


def test_naive_timestamp_auto_converts_to_timezone_aware():
    naive_dt = datetime(2026, 9, 30, 10, 0, 0)
    tx = Transaction(
        transaction_id="tx_naive",
        customer_id="cust_1",
        merchant_id="merch_1",
        amount=Decimal("100.00"),
        timestamp=naive_dt,
    )
    assert tx.timestamp.tzinfo is not None
    assert tx.timestamp.tzinfo == timezone.utc


def test_invalid_amount_rejections():
    with pytest.raises(ValidationError):
        Transaction(
            transaction_id="tx_neg",
            customer_id="cust_1",
            merchant_id="merch_1",
            amount=Decimal("-10.00"),  # Negative amount rejected
            timestamp=datetime.now(timezone.utc),
        )

    with pytest.raises(ValidationError):
        Transaction(
            transaction_id="tx_zero",
            customer_id="cust_1",
            merchant_id="merch_1",
            amount=Decimal("0.00"),  # Zero amount rejected
            timestamp=datetime.now(timezone.utc),
        )


def test_latitude_longitude_bounds_validation():
    # Valid bounds
    tx = Transaction(
        transaction_id="tx_loc",
        customer_id="cust_1",
        merchant_id="merch_1",
        amount=Decimal("50.00"),
        timestamp=datetime.now(timezone.utc),
        latitude=90.0,
        longitude=-180.0,
    )
    assert tx.latitude == 90.0

    # Invalid latitude
    with pytest.raises(ValidationError):
        Transaction(
            transaction_id="tx_invalid_lat",
            customer_id="cust_1",
            merchant_id="merch_1",
            amount=Decimal("50.00"),
            timestamp=datetime.now(timezone.utc),
            latitude=95.0,
        )

    # Invalid longitude
    with pytest.raises(ValidationError):
        Transaction(
            transaction_id="tx_invalid_lon",
            customer_id="cust_1",
            merchant_id="merch_1",
            amount=Decimal("50.00"),
            timestamp=datetime.now(timezone.utc),
            longitude=185.0,
        )


def test_optional_fields_can_be_none():
    tx = Transaction(
        transaction_id="tx_min",
        customer_id="cust_1",
        merchant_id="merch_1",
        amount=Decimal("25.00"),
        timestamp=datetime.now(timezone.utc),
    )
    assert tx.latitude is None
    assert tx.longitude is None
    assert tx.device_id is None
    assert tx.ip_address is None
    assert tx.country is None


def test_previous_transaction_model_minimal_defaults():
    prev = PreviousTransaction(
        transaction_id="tx_prev_1",
        timestamp=datetime(2026, 9, 30, 9, 30, 0, tzinfo=timezone.utc),
        latitude=12.9716,
        longitude=77.5946,
        amount=Decimal("250.00"),
        merchant_id="merch_prev",
    )
    assert prev.transaction_id == "tx_prev_1"
    assert prev.amount == Decimal("250.00")
    assert prev.latitude == 12.9716
    assert prev.device_id is None
    assert prev.ip_address is None


def test_previous_transaction_with_device_and_ip():
    prev = PreviousTransaction(
        transaction_id="tx_prev_2",
        timestamp=datetime(2026, 9, 30, 9, 35, 0, tzinfo=timezone.utc),
        latitude=19.0760,
        longitude=72.8777,
        amount=Decimal("1200.00"),
        merchant_id="merch_prev_2",
        device_id="device_iphone_15",
        ip_address="203.0.113.42",
    )
    assert prev.device_id == "device_iphone_15"
    assert prev.ip_address == "203.0.113.42"

    # Verify serialization retains fields
    dump = prev.model_dump()
    assert dump["device_id"] == "device_iphone_15"
    assert dump["ip_address"] == "203.0.113.42"
    assert dump["amount"] == Decimal("1200.00")

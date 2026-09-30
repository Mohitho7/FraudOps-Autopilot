"""
Tests for FraudEvaluationContext schema.
"""

from datetime import datetime, timezone
from decimal import Decimal

from app.schemas.context import FraudEvaluationContext
from app.schemas.customer import CustomerContext
from app.schemas.merchant import Merchant, MerchantStatistics
from app.schemas.transaction import PreviousTransaction


def test_empty_context_creation():
    context = FraudEvaluationContext()
    assert context.customer_context is None
    assert context.merchant_context is None
    assert context.merchant_statistics is None
    assert context.previous_transaction is None
    assert context.recent_transactions == []
    assert context.metadata == {}


def test_fully_populated_context():
    customer = CustomerContext(
        customer_id="cust_500",
        average_transaction_amount=Decimal("1200.00"),
        transaction_count=45,
        recent_transaction_count=2,
        historical_activity_summary={"account_age_days": 180, "chargebacks": 0},
    )
    merchant = Merchant(
        merchant_id="merch_500",
        merchant_name="Prime Tech",
        category="ELECTRONICS",
    )
    stats = MerchantStatistics(
        transaction_count=5000,
        average_transaction_amount=Decimal("4500.00"),
    )
    prev_tx = PreviousTransaction(
        transaction_id="tx_p1",
        timestamp=datetime.now(timezone.utc),
        latitude=12.9716,
        longitude=77.5946,
        amount=Decimal("1100.00"),
        merchant_id="merch_500",
    )

    context = FraudEvaluationContext(
        customer_context=customer,
        merchant_context=merchant,
        merchant_statistics=stats,
        previous_transaction=prev_tx,
        recent_transactions=[prev_tx],
        metadata={"channel": "web_browser", "session_id": "sess_xyz"},
    )

    assert context.customer_context.customer_id == "cust_500"
    assert context.merchant_context.category == "ELECTRONICS"
    assert len(context.recent_transactions) == 1
    assert context.metadata["channel"] == "web_browser"

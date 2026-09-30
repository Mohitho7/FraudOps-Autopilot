"""Shared pytest fixtures for the backend test suite.

The Batch 1 suite covers contracts only: schema validation, state creation,
tool interfaces and the service boundary. No test asserts that AI
investigation works -- that arrives with the Batch 2 implementation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from app.schemas.investigation import (
    InvestigationRequest,
    RuleResultRecord,
    Severity,
    TransactionContext,
)

TRANSACTION_ID = UUID("0f3d1c1e-6b6a-4f4b-9f2a-1d2c3b4a5e6f")
CUSTOMER_ID = UUID("6c1f0d2a-7b3c-4d5e-8f90-1a2b3c4d5e6f")
MERCHANT_ID = UUID("9a8b7c6d-5e4f-4a3b-8c9d-0e1f2a3b4c5d")
CASE_ID = UUID("1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d")
EVENT_TIME = datetime(2026, 9, 30, 10, 30, tzinfo=timezone.utc)


def make_rule_result(
    rule_id: str = "unusual_amount",
    *,
    triggered: bool = True,
    score: int = 35,
    severity: Severity = Severity.HIGH,
) -> RuleResultRecord:
    """Build a Member 1 rule result for tests."""

    return RuleResultRecord(
        rule_id=rule_id,
        rule_name="Unusual Transaction Amount",
        triggered=triggered,
        score=score,
        severity=severity,
        reason="Amount is 434.8x customer baseline",
        evidence={
            "amount": "1000000.00",
            "customer_average": "2300.00",
            "merchant_p95": "6500.00",
        },
    )


def make_transaction_context() -> TransactionContext:
    """Build the transaction snapshot for the documented fuel-station scenario."""

    return TransactionContext(
        transaction_id=TRANSACTION_ID,
        customer_id=CUSTOMER_ID,
        merchant_id=MERCHANT_ID,
        amount=Decimal("1000000.00"),
        currency="INR",
        timestamp=EVENT_TIME,
        latitude=17.385,
        longitude=78.4867,
        country="IN",
        merchant_label="M-FUEL-019",
        ip_address="203.0.113.10",
        device_id="device-abc-123",
    )


def make_request(**overrides: object) -> InvestigationRequest:
    """Build a valid Member 1 -> Member 2 request, with optional overrides."""

    payload: dict[str, object] = {
        "transaction_id": TRANSACTION_ID,
        "customer_id": CUSTOMER_ID,
        "merchant_id": MERCHANT_ID,
        "case_id": CASE_ID,
        "risk_score": 94,
        "severity": Severity.CRITICAL,
        "triggered_rules": [make_rule_result()],
        "transaction_context": make_transaction_context(),
    }
    payload.update(overrides)
    return InvestigationRequest(**payload)


@pytest.fixture
def investigation_request() -> InvestigationRequest:
    """A valid investigation request for the documented demo scenario."""

    return make_request()

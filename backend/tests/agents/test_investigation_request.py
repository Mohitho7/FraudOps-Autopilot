"""Validation tests for the Member 1 -> Member 2 contract."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.investigation import (
    ContextSignal,
    InvestigationRequest,
    InvestigationTrigger,
    Severity,
    TransactionContext,
)
from tests.conftest import (
    CUSTOMER_ID,
    MERCHANT_ID,
    TRANSACTION_ID,
    make_request,
    make_rule_result,
)


def test_valid_request_is_accepted() -> None:
    request = make_request()

    assert request.transaction_id == TRANSACTION_ID
    assert request.risk_score == 94
    assert request.severity is Severity.CRITICAL
    assert request.triggered_rule_ids == ("unusual_amount",)
    assert request.trigger is InvestigationTrigger.RISK_THRESHOLD


def test_request_accepts_the_documented_minimum_payload() -> None:
    request = InvestigationRequest(
        transaction_id=TRANSACTION_ID,
        risk_score=94,
        severity="CRITICAL",
        triggered_rules=[
            {
                "rule_id": "unusual_amount",
                "rule_name": "Unusual Transaction Amount",
                "triggered": True,
                "score": 35,
                "severity": "HIGH",
                "reason": "Amount is 434.8x customer baseline",
            }
        ],
    )

    assert request.customer_id is None
    assert request.transaction_context is None
    assert request.context_signals == []
    assert request.triggered_rules[0].evidence == {}


def test_risk_score_must_be_within_range() -> None:
    with pytest.raises(ValidationError) as invalid_low:
        make_request(risk_score=-1)
    with pytest.raises(ValidationError) as invalid_high:
        make_request(risk_score=101)

    assert "risk_score" in str(invalid_low.value)
    assert "risk_score" in str(invalid_high.value)


def test_unknown_severity_is_rejected() -> None:
    with pytest.raises(ValidationError) as error:
        make_request(severity="EXTREME")

    assert "severity" in str(error.value)


def test_transaction_id_is_required() -> None:
    with pytest.raises(ValidationError) as error:
        InvestigationRequest(
            risk_score=80,
            severity=Severity.HIGH,
            triggered_rules=[make_rule_result()],
        )

    assert "transaction_id" in str(error.value)


def test_at_least_one_triggered_rule_is_required() -> None:
    with pytest.raises(ValidationError) as error:
        make_request(triggered_rules=[])

    assert "triggered_rules" in str(error.value)


def test_rule_result_requires_a_reason() -> None:
    payload = make_rule_result().model_dump()
    payload.pop("reason")

    with pytest.raises(ValidationError) as error:
        InvestigationRequest(
            transaction_id=TRANSACTION_ID,
            risk_score=80,
            severity=Severity.HIGH,
            triggered_rules=[payload],
        )

    assert "reason" in str(error.value)


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError) as error:
        make_request(frontend_layout="danger")

    assert "frontend_layout" in str(error.value)


def test_transaction_context_must_match_the_request() -> None:
    other_transaction = "11111111-2222-3333-4444-555555555555"
    context = TransactionContext(
        transaction_id=other_transaction,
        customer_id=CUSTOMER_ID,
        merchant_id=MERCHANT_ID,
        amount=Decimal("10.00"),
        currency="INR",
        timestamp="2026-09-30T10:30:00Z",  # type: ignore[arg-type]
    )

    with pytest.raises(ValidationError) as error:
        make_request(transaction_context=context)

    assert "transaction_context.transaction_id" in str(error.value)


def test_currency_must_be_a_three_letter_code() -> None:
    with pytest.raises(ValidationError) as error:
        make_request(
            transaction_context={
                "transaction_id": TRANSACTION_ID,
                "customer_id": CUSTOMER_ID,
                "merchant_id": MERCHANT_ID,
                "amount": "100.00",
                "currency": "inr",
                "timestamp": "2026-09-30T10:30:00Z",
            }
        )

    assert "currency" in str(error.value)


def test_naive_timestamps_are_rejected() -> None:
    with pytest.raises(ValidationError) as error:
        make_request(
            transaction_context={
                "transaction_id": TRANSACTION_ID,
                "customer_id": CUSTOMER_ID,
                "merchant_id": MERCHANT_ID,
                "amount": "100.00",
                "currency": "INR",
                "timestamp": "2026-09-30T10:30:00",
            }
        )

    assert "timezone aware" in str(error.value)


def test_coordinates_must_be_supplied_in_pairs() -> None:
    with pytest.raises(ValidationError) as error:
        make_request(
            transaction_context={
                "transaction_id": TRANSACTION_ID,
                "customer_id": CUSTOMER_ID,
                "merchant_id": MERCHANT_ID,
                "amount": "100.00",
                "currency": "INR",
                "timestamp": "2026-09-30T10:30:00Z",
                "latitude": 17.385,
            }
        )

    assert "latitude and longitude" in str(error.value)


def test_out_of_range_coordinates_are_rejected() -> None:
    with pytest.raises(ValidationError) as error:
        make_request(
            transaction_context={
                "transaction_id": TRANSACTION_ID,
                "customer_id": CUSTOMER_ID,
                "merchant_id": MERCHANT_ID,
                "amount": "100.00",
                "currency": "INR",
                "timestamp": "2026-09-30T10:30:00Z",
                "latitude": 191.0,
                "longitude": 78.4867,
            }
        )

    assert "latitude" in str(error.value)


def test_context_signals_carry_a_source() -> None:
    signal = ContextSignal(
        signal_type="customer_amount_ratio",
        description="Amount is 434.8x the customer baseline",
        value=434.8,
        severity=Severity.HIGH,
        source="context_enricher:customer_history",
    )

    assert signal.source.startswith("context_enricher")
    assert signal.observed_at is None


def test_rule_evidence_reference_is_stable() -> None:
    assert make_rule_result().evidence_reference == "rule_result:unusual_amount"


def test_request_does_not_recompute_risk() -> None:
    """Member 1's score is echoed verbatim; the contract never derives it."""

    request = make_request(risk_score=37, severity=Severity.MEDIUM)

    assert request.risk_score == 37
    assert request.severity is Severity.MEDIUM

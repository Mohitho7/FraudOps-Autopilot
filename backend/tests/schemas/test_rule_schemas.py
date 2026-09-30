"""
Tests for RuleResult, Severity, and RuleExecutionStatus schemas.
"""

import pytest
from pydantic import ValidationError

from app.schemas.rule import RuleExecutionStatus, RuleResult, Severity


def test_valid_rule_result_creation():
    result = RuleResult(
        rule_id="unusual_amount_check",
        rule_name="Unusual Amount Rule",
        triggered=True,
        score=35,
        severity=Severity.HIGH,
        reason="Amount is 8.5x customer baseline average",
        evidence={
            "amount": "8500.00",
            "customer_average": "1000.00",
            "ratio": 8.5,
        },
        execution_time_ms=1.25,
    )
    assert result.rule_id == "unusual_amount_check"
    assert result.triggered is True
    assert result.score == 35
    assert result.severity == Severity.HIGH
    assert result.evidence["ratio"] == 8.5
    assert result.execution_time_ms == 1.25
    assert result.status == RuleExecutionStatus.SUCCESS


def test_rule_result_status_defaults_to_success():
    result = RuleResult(
        rule_id="r_success",
        rule_name="Success Rule",
        triggered=False,
    )
    assert result.status == RuleExecutionStatus.SUCCESS


def test_rule_result_status_error_explicit():
    result = RuleResult(
        rule_id="r_err",
        rule_name="Error Rule",
        triggered=False,
        score=0,
        severity=Severity.NONE,
        reason="Evaluation failed",
        evidence={"execution_failed": True, "error": "Crash"},
        status=RuleExecutionStatus.ERROR,
    )
    assert result.status == RuleExecutionStatus.ERROR
    # Verify failed rule cannot be confused with success
    assert result.status != RuleExecutionStatus.SUCCESS


def test_invalid_status_raises_error():
    with pytest.raises(ValidationError):
        RuleResult(
            rule_id="r1",
            rule_name="Rule 1",
            triggered=False,
            status="UNKNOWN_STATUS",  # type: ignore
        )


def test_invalid_severity_raises_error():
    with pytest.raises(ValidationError):
        RuleResult(
            rule_id="r1",
            rule_name="Rule 1",
            triggered=True,
            severity="EXTREME",  # Invalid enum value
        )


def test_score_bounds_validation():
    with pytest.raises(ValidationError):
        RuleResult(
            rule_id="r1",
            rule_name="Rule 1",
            triggered=True,
            score=105,  # Exceeds maximum 100
        )

    with pytest.raises(ValidationError):
        RuleResult(
            rule_id="r1",
            rule_name="Rule 1",
            triggered=True,
            score=-5,  # Sub-zero rejected
        )


def test_empty_rule_id_or_name_rejected():
    with pytest.raises(ValidationError):
        RuleResult(
            rule_id="",
            rule_name="Rule 1",
            triggered=False,
        )

    with pytest.raises(ValidationError):
        RuleResult(
            rule_id="   ",
            rule_name="Rule 1",
            triggered=False,
        )

    with pytest.raises(ValidationError):
        RuleResult(
            rule_id="r1",
            rule_name="",
            triggered=False,
        )


def test_evidence_must_be_mapping():
    with pytest.raises(ValidationError):
        RuleResult(
            rule_id="r1",
            rule_name="Rule 1",
            triggered=True,
            evidence="natural language string instead of dict",  # Must be dict
        )

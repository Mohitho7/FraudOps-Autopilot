"""Validation tests for the Member 2 -> Member 3 contract."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.agents.graph.state import InvestigationState
from app.schemas.investigation import (
    ClaimKind,
    EntityType,
    InvestigationStatus,
    RelationType,
    Severity,
)
from app.schemas.investigation_result import (
    EvidenceItem,
    EvidenceSourceType,
    HumanDecision,
    HumanDecisionAction,
    InvestigationActivity,
    InvestigationFinding,
    InvestigationResponse,
    RelatedEntity,
    Recommendation,
    RecommendationAction,
)
from tests.conftest import TRANSACTION_ID, make_request

NOW = datetime(2026, 9, 30, 11, 20, 4, tzinfo=timezone.utc)


def _response_payload() -> dict[str, object]:
    return {
        "investigation_id": uuid4(),
        "transaction_id": TRANSACTION_ID,
        "case_id": uuid4(),
        "status": InvestigationStatus.WAITING_HUMAN,
        "risk_score": 96,
        "severity": Severity.CRITICAL,
        "findings": [],
        "evidence": [],
        "related_entities": [],
        "recommendation": None,
        "confidence": 0.94,
        "activity_timeline": [],
        "started_at": NOW,
        "updated_at": NOW,
    }


def test_minimal_response_is_accepted() -> None:
    response = InvestigationResponse(**_response_payload())  # type: ignore[arg-type]

    assert response.risk_score == 96
    assert response.status is InvestigationStatus.WAITING_HUMAN
    assert response.human_decision is None
    assert response.completed_at is None


def test_unknown_fields_are_rejected() -> None:
    payload = _response_payload()
    payload["risk_breakdown"] = {"velocity": 25}

    with pytest.raises(ValidationError) as error:
        InvestigationResponse(**payload)  # type: ignore[arg-type]

    assert "risk_breakdown" in str(error.value)


def test_confidence_must_be_within_range() -> None:
    payload = _response_payload()
    payload["confidence"] = 1.4

    with pytest.raises(ValidationError) as error:
        InvestigationResponse(**payload)  # type: ignore[arg-type]

    assert "confidence" in str(error.value)


def test_risk_score_must_be_within_range() -> None:
    payload = _response_payload()
    payload["risk_score"] = -5

    with pytest.raises(ValidationError) as error:
        InvestigationResponse(**payload)  # type: ignore[arg-type]

    assert "risk_score" in str(error.value)


def test_evidence_items_expose_a_reference() -> None:
    evidence = EvidenceItem(
        evidence_id=uuid4(),
        source_type=EvidenceSourceType.MERCHANT,
        source_ref="merchant:9a8b7c6d-5e4f-4a3b-8c9d-0e1f2a3b4c5d",
        claim_kind=ClaimKind.CALCULATED_METRIC,
        title="Amount is above merchant P99",
        details={"expected_p99": "12000", "amount": "1000000"},
    )

    assert evidence.reference == f"evidence:{evidence.evidence_id}"
    assert evidence.source_ref.startswith("merchant:")


def test_evidence_requires_a_source_reference() -> None:
    with pytest.raises(ValidationError) as error:
        EvidenceItem(
            evidence_id=uuid4(),
            source_type=EvidenceSourceType.CUSTOMER,
            source_ref="",
            claim_kind=ClaimKind.OBSERVED_FACT,
            title="Customer baseline loaded",
        )

    assert "source_ref" in str(error.value)


def test_findings_reference_evidence_references() -> None:
    finding = InvestigationFinding(
        finding_id=uuid4(),
        category="BEHAVIORAL",
        title="Amount is 434.8x customer average",
        summary="Far above the customer's 90-day baseline.",
        confidence=0.9,
        metrics={"amount_multiple_of_customer_average": 434.8},
        evidence_refs=["evidence:abc"],
    )

    assert finding.evidence_refs == ["evidence:abc"]
    assert finding.severity_impact is None


def test_related_entities_use_the_documented_case_entity_vocabulary() -> None:
    entity = RelatedEntity(
        entity_type=EntityType.DEVICE,
        entity_ref="device:abc-123",
        relation_type=RelationType.SHARED_DEVICE,
        label="Shared device",
        risk_note="Device is also used by a previously flagged customer.",
    )

    assert entity.entity_type is EntityType.DEVICE
    assert entity.relation_type is RelationType.SHARED_DEVICE
    assert entity.related_case_id is None


def test_recommendation_actions_match_the_documented_vocabulary() -> None:
    assert {action.value for action in RecommendationAction} == {
        "ALLOW",
        "MONITOR",
        "HOLD_FOR_REVIEW",
        "ESCALATE",
    }


def test_human_decision_actions_match_the_reviewer_actions() -> None:
    assert {action.value for action in HumanDecisionAction} == {
        "CLEAR",
        "CONFIRM_FRAUD",
        "ESCALATE",
        "MARK_REVIEWED",
    }


def test_timeline_entries_are_structured_events() -> None:
    event = InvestigationActivity(
        sequence=0,
        step="CALL_TOOL",
        status="COMPLETED",
        summary="Found 6 related transactions",
        tool_name="get_related_entities",
        occurred_at=NOW,
    )

    assert event.sequence == 0
    assert event.error is None
    assert event.tool_name == "get_related_entities"


def test_requires_human_review_is_derived_for_the_console() -> None:
    response = InvestigationResponse(**_response_payload())  # type: ignore[arg-type]

    assert response.requires_human_review is True

    response.human_decision = HumanDecision(
        action=HumanDecisionAction.CONFIRM_FRAUD,
        reviewer_id="reviewer-1",
        note="Confirmed by analyst",
        decided_at=NOW,
    )

    assert response.requires_human_review is False


def test_failed_investigation_requires_human_review() -> None:
    payload = _response_payload()
    payload["status"] = InvestigationStatus.FAILED
    payload["error"] = {
        "step": "EVIDENCE_BUILD",
        "error_type": "PersistenceError",
        "message": "Evidence write failed",
        "retryable": True,
    }

    response = InvestigationResponse(**payload)  # type: ignore[arg-type]

    assert response.requires_human_review is True
    assert response.error is not None
    assert response.error.retryable is True


def test_response_serialises_to_json() -> None:
    state = InvestigationState.from_request(make_request())
    response = state.to_response()
    response.recommendation = Recommendation(
        action=RecommendationAction.ESCALATE,
        confidence=0.8,
        rationale="Linked suspicious entities.",
        requires_human_review=True,
    )

    payload = response.model_dump(mode="json")

    assert payload["recommendation"]["action"] == "ESCALATE"
    assert payload["severity"] == "CRITICAL"
    assert payload["requires_human_review"] is True

"""Investigation state tests (Member 2).

Covers state creation from a Member 1 request, the audit helpers, the
checkpoint round-trip and the projection into the Member 2 -> Member 3 payload.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.agents.graph.nodes import INVESTIGATION_NODE_SEQUENCE, NODE_DESCRIPTIONS
from app.agents.graph.state import STATE_SCHEMA_VERSION, InvestigationState
from app.agents.graph.workflow import build_investigation_graph
from app.schemas.investigation import (
    AnalysisCategory,
    ClaimKind,
    EntityType,
    InvestigationStatus,
    InvestigationStep,
    InvestigationTrigger,
    RelationType,
    Severity,
)
from app.schemas.investigation_result import (
    EvidenceItem,
    EvidenceSourceType,
    InvestigationFinding,
    Recommendation,
    RecommendationAction,
    RelatedEntity,
)
from tests.conftest import (
    CASE_ID,
    CUSTOMER_ID,
    MERCHANT_ID,
    TRANSACTION_ID,
    make_request,
)


def test_state_is_created_from_a_member1_request() -> None:
    state = InvestigationState.from_request(make_request())

    assert state.schema_version == STATE_SCHEMA_VERSION
    assert state.transaction_id == TRANSACTION_ID
    assert state.customer_id == CUSTOMER_ID
    assert state.merchant_id == MERCHANT_ID
    assert state.case_id == CASE_ID
    assert state.risk_score == 94
    assert state.severity is Severity.CRITICAL
    assert state.status is InvestigationStatus.RUNNING
    assert state.trigger is InvestigationTrigger.RISK_THRESHOLD
    assert state.current_step is InvestigationStep.LOAD_STATE
    assert state.completed_steps == []
    assert state.evidence == []
    assert state.all_findings() == []


def test_state_uses_a_supplied_investigation_id() -> None:
    investigation_id = uuid4()
    state = InvestigationState.from_request(
        make_request(), investigation_id=investigation_id
    )

    assert state.investigation_id == investigation_id


def test_customer_and_merchant_are_derived_from_the_context() -> None:
    state = InvestigationState.from_request(
        make_request(customer_id=None, merchant_id=None)
    )

    assert state.customer_id == CUSTOMER_ID
    assert state.merchant_id == MERCHANT_ID


def test_state_works_without_a_transaction_context() -> None:
    state = InvestigationState.from_request(
        make_request(
            customer_id=None,
            merchant_id=None,
            transaction_context=None,
        )
    )

    assert state.customer_id is None
    assert state.merchant_id is None
    assert state.transaction_context is None


def test_state_rejects_a_missing_risk_score() -> None:
    with pytest.raises(ValidationError) as error:
        InvestigationState(transaction_id=TRANSACTION_ID)  # type: ignore[call-arg]

    assert "risk_score" in str(error.value)


def test_state_rejects_a_naive_timestamp() -> None:
    with pytest.raises(ValidationError) as error:
        InvestigationState(
            transaction_id=TRANSACTION_ID,
            risk_score=90,
            severity=Severity.HIGH,
            started_at=datetime(2026, 9, 30, 10, 30),
        )

    assert "timezone aware" in str(error.value)


def test_completed_steps_are_deduplicated() -> None:
    state = InvestigationState.from_request(make_request())

    state.mark_step_completed(InvestigationStep.LOAD_STATE)
    state.mark_step_completed(InvestigationStep.LOAD_STATE)

    assert state.completed_steps == [InvestigationStep.LOAD_STATE]


def test_activity_events_are_sequenced_and_ordered() -> None:
    state = InvestigationState.from_request(make_request())

    first = state.record_activity(
        step=InvestigationStep.CALL_TOOL,
        status="COMPLETED",
        summary="Loaded 90-day customer history",
        tool_name="get_customer_history",
    )
    second = state.record_activity(
        step=InvestigationStep.CALL_TOOL,
        status="FAILED",
        summary="Merchant profile lookup failed",
        tool_name="get_merchant_profile",
        error="connection refused",
    )

    assert (first.sequence, second.sequence) == (0, 1)
    assert [event.tool_name for event in state.activity] == [
        "get_customer_history",
        "get_merchant_profile",
    ]
    assert second.error == "connection refused"
    assert state.updated_at == second.occurred_at


def test_state_round_trips_through_a_checkpoint_dict() -> None:
    state = InvestigationState.from_request(make_request())
    state.mark_step_completed(InvestigationStep.LOAD_STATE)
    state.record_activity(
        step=InvestigationStep.LOAD_STATE,
        status="COMPLETED",
        summary="Investigation started",
    )

    restored = InvestigationState.from_dict(state.to_dict())

    assert restored == state
    assert isinstance(restored.to_dict()["transaction_id"], str)


def test_state_round_trips_after_evidence_has_been_collected() -> None:
    """Checkpoint restore must work once the evidence builder has run.

    Regression test: computed fields are emitted by ``model_dump`` but rejected
    by validation, so a state carrying evidence could not be restored from its
    own checkpoint dict (Agent System Design section 13).
    """

    state = InvestigationState.from_request(make_request())
    state.evidence = [
        EvidenceItem(
            evidence_id=uuid4(),
            source_type=EvidenceSourceType.RULE_RESULT,
            source_ref="rule_result:unusual_amount",
            claim_kind=ClaimKind.RULE_RESULT,
            title="Unusual amount rule triggered",
            details={"amount": "1000000.00", "customer_average": "2300.00"},
        )
    ]
    state.related_entities = [
        RelatedEntity(
            entity_type=EntityType.DEVICE,
            entity_ref="device-abc-123",
            relation_type=RelationType.SHARED_DEVICE,
        )
    ]

    restored = InvestigationState.from_dict(state.to_dict())

    assert restored == state
    assert restored.evidence[0].reference == state.evidence[0].reference


def test_state_projects_the_member3_response() -> None:
    state = InvestigationState.from_request(make_request())
    evidence = EvidenceItem(
        evidence_id=uuid4(),
        source_type=EvidenceSourceType.RULE_RESULT,
        source_ref="rule_result:unusual_amount",
        claim_kind=ClaimKind.RULE_RESULT,
        title="Unusual amount rule triggered",
        details={"amount": "1000000.00", "customer_average": "2300.00"},
    )
    finding = InvestigationFinding(
        finding_id=uuid4(),
        category=AnalysisCategory.BEHAVIORAL,
        title="Amount is 434.8x customer average",
        summary="Far above the customer's 90-day baseline.",
        confidence=0.9,
        metrics={"amount_multiple_of_customer_average": 434.8},
        evidence_refs=[evidence.reference],
    )
    state.evidence.append(evidence)
    state.behavioral_findings.append(finding)
    state.confidence = 0.88
    state.recommendation = Recommendation(
        action=RecommendationAction.HOLD_FOR_REVIEW,
        confidence=0.91,
        rationale="Strong amount and merchant anomalies.",
        evidence_refs=[evidence.reference],
        requires_human_review=True,
    )
    state.status = InvestigationStatus.WAITING_HUMAN

    response = state.to_response()

    assert response.investigation_id == state.investigation_id
    assert response.transaction_id == TRANSACTION_ID
    assert response.risk_score == 94
    assert response.severity is Severity.CRITICAL
    assert response.findings == [finding]
    assert response.evidence == [evidence]
    assert response.confidence == 0.88
    assert response.recommendation is not None
    assert response.requires_human_review is True
    assert len(response.triggered_rules) == 1


def test_all_findings_are_returned_in_a_stable_order() -> None:
    state = InvestigationState.from_request(make_request())
    finding_lists = {
        AnalysisCategory.BEHAVIORAL: state.behavioral_findings,
        AnalysisCategory.BUSINESS: state.business_findings,
        AnalysisCategory.RELATIONSHIP: state.relationship_findings,
    }
    for category, findings in finding_lists.items():
        findings.append(
            InvestigationFinding(
                finding_id=uuid4(),
                category=category,
                title=f"{category.value} finding",
                summary="summary",
                confidence=0.5,
            )
        )

    assert [finding.category for finding in state.all_findings()] == [
        AnalysisCategory.BEHAVIORAL,
        AnalysisCategory.BUSINESS,
        AnalysisCategory.RELATIONSHIP,
    ]


def test_node_vocabulary_matches_the_documented_workflow() -> None:
    assert InvestigationStep.LOAD_STATE in INVESTIGATION_NODE_SEQUENCE
    assert InvestigationStep.EVIDENCE_BUILD in INVESTIGATION_NODE_SEQUENCE
    assert InvestigationStep.RECOMMENDATION in INVESTIGATION_NODE_SEQUENCE
    assert InvestigationStep.HUMAN_HANDOFF in INVESTIGATION_NODE_SEQUENCE
    assert set(NODE_DESCRIPTIONS) >= set(INVESTIGATION_NODE_SEQUENCE)


def test_graph_compilation_is_not_implemented_in_batch1() -> None:
    with pytest.raises(NotImplementedError):
        build_investigation_graph(toolset=None, settings=None)  # type: ignore[arg-type]


def test_default_timestamps_are_timezone_aware() -> None:
    state = InvestigationState.from_request(make_request())

    assert state.started_at.tzinfo is not None
    assert state.started_at == state.updated_at
    assert state.last_checkpoint_at is None
    assert datetime.now(timezone.utc) >= state.started_at

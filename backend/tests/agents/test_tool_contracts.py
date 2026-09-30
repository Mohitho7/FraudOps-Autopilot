"""Contract tests for the approved investigation tools (Member 2).

These tests assert the *shape* of the tool contracts and that the Batch 1 stubs
refuse to fabricate data. They do not test any database behaviour, because
there is no database behaviour yet.
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, time, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

import app.agents.tools as tools_package
from app.agents.behavioral.analyzer import BehavioralAnalyzerStub
from app.agents.business.analyzer import BusinessContextAnalyzerStub
from app.agents.evidence.builder import EvidenceBuilderStub
from app.agents.recommendation.agent import RecommendationAgentStub
from app.agents.relationship.analyzer import RelatedEntitiesAnalyzerStub
from app.agents.tools import (
    CustomerHistoryTool,
    CustomerHistoryToolStub,
    MerchantProfileTool,
    MerchantProfileToolStub,
    PriorCasesTool,
    PriorCasesToolStub,
    RecentTransactionsTool,
    RecentTransactionsToolStub,
    RelatedEntitiesTool,
    RelatedEntitiesToolStub,
    RuleResultsTool,
    RuleResultsToolStub,
    ToolCallRecord,
    ToolNotImplementedError,
    ToolStatus,
    tool_reference,
)
from app.agents.tools.types import (
    AmountStatistics,
    CustomerHistory,
    MerchantContext,
    OperatingHours,
    PriorCasesResult,
    RecentTransactionSet,
    RelatedEntitiesResult,
    RuleResultsResult,
    TimeWindow,
)
from app.schemas.investigation import RelationType, Severity
from app.schemas.investigation_result import RelatedEntity
from tests.conftest import CUSTOMER_ID, MERCHANT_ID, TRANSACTION_ID, make_rule_result

WINDOW = TimeWindow(
    start=datetime(2026, 7, 1, tzinfo=timezone.utc),
    end=datetime(2026, 9, 30, tzinfo=timezone.utc),
)


def test_documented_read_tools_are_exposed() -> None:
    for protocol, method in (
        (CustomerHistoryTool, "get_customer_history"),
        (RecentTransactionsTool, "get_recent_transactions"),
        (MerchantProfileTool, "get_merchant_profile"),
        (RelatedEntitiesTool, "get_related_entities"),
        (RuleResultsTool, "get_rule_results"),
        (PriorCasesTool, "get_prior_cases"),
    ):
        assert hasattr(protocol, method), f"{protocol.__name__}.{method} is missing"


def test_tool_methods_are_asynchronous() -> None:
    for protocol, method in (
        (CustomerHistoryTool, "get_customer_history"),
        (MerchantProfileTool, "get_merchant_profile"),
        (RelatedEntitiesTool, "get_related_entities"),
    ):
        assert inspect.iscoroutinefunction(getattr(protocol, method))


def test_customer_history_stub_refuses_to_fabricate_data() -> None:
    with pytest.raises(ToolNotImplementedError):
        asyncio.run(CustomerHistoryToolStub().get_customer_history(CUSTOMER_ID))


@pytest.mark.parametrize(
    "call",
    [
        lambda: RecentTransactionsToolStub().get_recent_transactions(),
        lambda: RuleResultsToolStub().get_rule_results(TRANSACTION_ID),
        lambda: MerchantProfileToolStub().get_merchant_profile(MERCHANT_ID),
        lambda: RelatedEntitiesToolStub().get_related_entities(TRANSACTION_ID),
        lambda: PriorCasesToolStub().get_prior_cases(),
    ],
)
def test_every_tool_stub_raises_not_implemented(call) -> None:
    with pytest.raises(ToolNotImplementedError):
        asyncio.run(call())


@pytest.mark.parametrize(
    "call",
    [
        lambda: BehavioralAnalyzerStub().analyze(None, None),  # type: ignore[arg-type]
        lambda: BusinessContextAnalyzerStub().analyze(None, None),  # type: ignore[arg-type]
        lambda: RelatedEntitiesAnalyzerStub().analyze(None, None),  # type: ignore[arg-type]
        lambda: EvidenceBuilderStub().build(None),  # type: ignore[arg-type]
        lambda: RecommendationAgentStub().recommend(None, None),  # type: ignore[arg-type]
    ],
)
def test_every_capability_stub_raises_not_implemented(call) -> None:
    with pytest.raises(NotImplementedError):
        asyncio.run(call())


def test_time_window_must_be_a_valid_range() -> None:
    with pytest.raises(ValidationError) as error:
        TimeWindow(
            start=datetime(2026, 9, 30, tzinfo=timezone.utc),
            end=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )

    assert "start must be earlier than end" in str(error.value)


def test_time_window_rejects_naive_datetimes() -> None:
    with pytest.raises(ValidationError) as error:
        TimeWindow(
            start=datetime(2026, 7, 1),
            end=datetime(2026, 9, 30, tzinfo=timezone.utc),
        )

    assert "timezone aware" in str(error.value)


def test_customer_history_carries_deterministic_baselines() -> None:
    history = CustomerHistory(
        customer_id=CUSTOMER_ID,
        window=WINDOW,
        context={
            "customer_id": CUSTOMER_ID,
            "amount_statistics": {
                "sample_size": 42,
                "median": "2300.00",
                "p95": "6500.00",
            },
            "transaction_count": 42,
        },
        transactions=[],
        reference=f"customer:{CUSTOMER_ID}:history",
    )

    assert history.context.amount_statistics is not None
    assert history.context.amount_statistics.has_baseline is True
    assert history.context.amount_statistics.median == Decimal("2300.00")


def test_amount_statistics_report_a_missing_baseline() -> None:
    assert AmountStatistics(sample_size=0).has_baseline is False


def test_operating_hours_cover_overnight_windows() -> None:
    night_shift = OperatingHours(opens_at=time(22, 0), closes_at=time(2, 0))

    assert night_shift.contains(time(23, 30)) is True
    assert night_shift.contains(time(1, 0)) is True
    assert night_shift.contains(time(12, 0)) is False


def test_merchant_context_uses_the_documented_bands() -> None:
    merchant = MerchantContext(
        merchant_id=MERCHANT_ID,
        category="fuel_station",
        expected_p50="1800",
        expected_p95="6500",
        expected_p99="12000",
        daily_volume_baseline="1200",
        reference=f"merchant:{MERCHANT_ID}:profile",
    )

    assert merchant.observed is None
    assert merchant.operating_hours is None
    assert merchant.expected_p99 == Decimal("12000")


def test_recent_transaction_set_requires_exactly_one_scope() -> None:
    with pytest.raises(ValidationError) as no_scope:
        RecentTransactionSet(
            window=WINDOW, amount_statistics=AmountStatistics(sample_size=0)
        )
    with pytest.raises(ValidationError) as both_scopes:
        RecentTransactionSet(
            customer_id=CUSTOMER_ID,
            merchant_id=MERCHANT_ID,
            window=WINDOW,
            amount_statistics=AmountStatistics(sample_size=0),
        )

    assert "exactly one of customer_id or merchant_id" in str(no_scope.value)
    assert "exactly one of customer_id or merchant_id" in str(both_scopes.value)


def test_prior_cases_result_requires_exactly_one_scope() -> None:
    with pytest.raises(ValidationError) as no_scope:
        PriorCasesResult(reference=f"prior_cases:transaction:{TRANSACTION_ID}")
    with pytest.raises(ValidationError) as both_scopes:
        PriorCasesResult(
            customer_id=CUSTOMER_ID,
            entity_ref="device:abc-123",
            reference=f"prior_cases:customer:{CUSTOMER_ID}",
        )

    assert "exactly one of customer_id or entity_ref" in str(no_scope.value)
    assert "exactly one of customer_id or entity_ref" in str(both_scopes.value)


def test_relationship_tool_output_is_linked_entities() -> None:
    result = RelatedEntitiesResult(
        transaction_id=TRANSACTION_ID,
        entities=[
            RelatedEntity(
                entity_type="DEVICE",
                entity_ref="device:abc-123",
                relation_type=RelationType.SHARED_DEVICE,
            )
        ],
        generated_at=datetime(2026, 9, 30, 11, 20, 2, tzinfo=timezone.utc),
        reference=f"transaction:{TRANSACTION_ID}:entities",
    )

    assert result.entity_count == 1
    assert result.entities[0].entity_type.value == "DEVICE"


def test_rule_results_expose_member1_outputs_without_recomputing() -> None:
    result = RuleResultsResult(
        transaction_id=TRANSACTION_ID,
        results=[
            make_rule_result(),
            make_rule_result(
                "velocity", triggered=False, score=0, severity=Severity.LOW
            ),
        ],
        reference=f"transaction:{TRANSACTION_ID}:rule_results",
    )

    assert [rule.rule_id for rule in result.triggered] == ["unusual_amount"]
    assert result.highest_severity is Severity.HIGH
    assert result.results[0].score == 35


def test_tool_reference_format_is_stable() -> None:
    assert tool_reference("transaction", TRANSACTION_ID) == (
        f"transaction:{TRANSACTION_ID}"
    )
    assert tool_reference("device", "abc-123") == "device:abc-123"


def test_tool_call_record_starts_unresolved() -> None:
    record = ToolCallRecord.started(
        tool_name="get_customer_history",
        step="CALL_TOOL",  # type: ignore[arg-type]
        input_refs=(f"customer:{CUSTOMER_ID}",),
    )

    assert record.status == ToolStatus.STARTED
    assert record.output_refs == ()
    assert record.started_at == record.completed_at
    assert record.error is None


def test_geographic_distance_is_not_a_member2_tool() -> None:
    """Impossible travel stays with Member 1; Member 2 must not duplicate it."""

    exported = dir(tools_package)

    assert not any("geo" in name.lower() for name in exported)
    assert not any("distance" in name.lower() for name in exported)


def test_notification_delivery_is_not_a_member2_tool() -> None:
    """SES/SNS delivery belongs to Member 4, so no notification tool is declared."""

    assert not any("notification" in name.lower() for name in dir(tools_package))


def test_entity_references_survive_a_round_trip() -> None:
    entity = RelatedEntity(
        entity_type="IP_ADDRESS",
        entity_ref="ip:203.0.113.10",
        relation_type=RelationType.SHARED_IP_ADDRESS,
    )

    assert RelatedEntity.model_validate(entity.model_dump()) == entity

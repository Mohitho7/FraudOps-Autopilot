"""Fake toolset tests (Member 2, Batch 2).

Covers the gate, determinism, the refusal to invent data, and the arithmetic
the fakes compute. These tools back every other Batch 2 test, so their own
behaviour is asserted directly rather than taken on trust.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.agents.tools.base import InvestigationToolError, InvestigationToolset
from app.agents.tools.fakes import (
    ALLOW_FAKE_TOOLS_ENV,
    FAKE_CUSTOMER_ID,
    FAKE_DATA_MARKER,
    FAKE_MERCHANT_ID,
    FAKE_TRANSACTION_ID,
    FakeInvestigationToolset,
    FakeToolsetError,
    build_fake_toolset,
    compute_amount_statistics,
    require_fake_tools_enabled,
)
from app.agents.tools.types import AmountStatistics


def test_fakes_are_gated() -> None:
    """The gate is the whole reason these tools are safe to ship in app code."""

    require_fake_tools_enabled()
    assert build_fake_toolset() is not None


def test_gate_refuses_when_disabled(fakes_disabled: None) -> None:
    with pytest.raises(FakeToolsetError, match=ALLOW_FAKE_TOOLS_ENV):
        require_fake_tools_enabled()


def test_gate_refuses_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ALLOW_FAKE_TOOLS_ENV, raising=False)

    with pytest.raises(FakeToolsetError):
        require_fake_tools_enabled()


def test_gate_refuses_a_malformed_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ALLOW_FAKE_TOOLS_ENV, "maybe")

    with pytest.raises(FakeToolsetError):
        require_fake_tools_enabled()


async def test_every_reference_is_marked_as_fake(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    """Fake output must never be mistakable for a database record."""

    rule_results = await fake_toolset.rule_results_tool.get_rule_results(
        FAKE_TRANSACTION_ID
    )
    history = await fake_toolset.customer_history_tool.get_customer_history(
        FAKE_CUSTOMER_ID
    )
    profile = await fake_toolset.merchant_profile_tool.get_merchant_profile(
        FAKE_MERCHANT_ID
    )
    prior_cases = await fake_toolset.case_history_tool.get_prior_cases(
        customer_id=FAKE_CUSTOMER_ID
    )

    references = [
        rule_results.reference,
        history.reference,
        profile.reference,
        prior_cases[0].reference,
    ]

    assert all(
        reference.startswith(f"{FAKE_DATA_MARKER}:") for reference in references
    )


async def test_every_tool_call_rechecks_the_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A toolset built while enabled must not stay usable after it is disabled."""

    monkeypatch.setenv(ALLOW_FAKE_TOOLS_ENV, "true")
    toolset = FakeInvestigationToolset()
    monkeypatch.setenv(ALLOW_FAKE_TOOLS_ENV, "false")

    with pytest.raises(FakeToolsetError):
        await toolset.rule_results_tool.get_rule_results(FAKE_TRANSACTION_ID)


def test_toolset_exposes_every_batch1_accessor() -> None:
    """A fake and a production toolset are interchangeable at the graph seam."""

    toolset = build_fake_toolset()

    for accessor in InvestigationToolset.__protocol_attrs__:
        assert getattr(toolset, accessor, None) is not None


def test_amount_statistics_of_a_single_value() -> None:
    stats = compute_amount_statistics([Decimal("100.00")])

    assert stats.sample_size == 1
    assert stats.mean == Decimal("100.00")
    assert stats.median == Decimal("100.00")
    assert stats.p95 == Decimal("100.00")
    assert stats.standard_deviation == Decimal("0.00")


def test_amount_statistics_of_an_empty_sample() -> None:
    stats = compute_amount_statistics([])

    assert stats.sample_size == 0
    assert not stats.has_baseline


def test_amount_statistics_median_of_an_even_sample() -> None:
    stats = compute_amount_statistics([Decimal("10"), Decimal("20")])

    assert stats.median == Decimal("15.00")


def test_amount_statistics_percentiles_interpolate() -> None:
    stats = compute_amount_statistics([Decimal(value) for value in "100 200 300 400".split()])

    assert stats.minimum == Decimal("100")
    assert stats.maximum == Decimal("400")
    assert stats.mean == Decimal("250.00")
    assert stats.p95 is not None
    assert Decimal("380") <= stats.p95 <= Decimal("400")


def test_amount_statistics_are_order_independent() -> None:
    values = [Decimal(value) for value in "500 100 300 200".split()]

    assert compute_amount_statistics(values) == compute_amount_statistics(
        list(reversed(values))
    )


def test_amount_statistics_round_trip_through_validation() -> None:
    stats = compute_amount_statistics([Decimal("100"), Decimal("250")])

    assert AmountStatistics.model_validate(stats.model_dump()) == stats


async def test_rule_results_are_fixed_literals(fake_toolset: FakeInvestigationToolset) -> None:
    result = await fake_toolset.rule_results_tool.get_rule_results(FAKE_TRANSACTION_ID)

    assert {item.rule_id for item in result.results} == {
        "unusual_amount",
        "velocity_24h",
        "new_device",
    }
    assert {item.rule_id for item in result.triggered} == {
        "unusual_amount",
        "velocity_24h",
    }


async def test_recent_transactions_requires_exactly_one_scope(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    tool = fake_toolset.transaction_history_tool

    with pytest.raises(InvestigationToolError, match="exactly one"):
        await tool.get_recent_transactions()
    with pytest.raises(InvestigationToolError, match="exactly one"):
        await tool.get_recent_transactions(
            customer_id=FAKE_CUSTOMER_ID, merchant_id=FAKE_MERCHANT_ID
        )


async def test_recent_transactions_honours_the_limit(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    result = await fake_toolset.transaction_history_tool.get_recent_transactions(
        customer_id=FAKE_CUSTOMER_ID, limit=3
    )

    assert len(result.transactions) == 3
    assert result.amount_statistics.sample_size == 3


@pytest.mark.parametrize("limit", [0, -1])
async def test_recent_transactions_rejects_a_non_positive_limit(
    fake_toolset: FakeInvestigationToolset, limit: int
) -> None:
    with pytest.raises(InvestigationToolError, match="positive integer"):
        await fake_toolset.transaction_history_tool.get_recent_transactions(
            customer_id=FAKE_CUSTOMER_ID, limit=limit
        )


async def test_recent_transactions_refuses_an_unknown_customer(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    with pytest.raises(FakeToolsetError, match="no customer"):
        await fake_toolset.transaction_history_tool.get_recent_transactions(
            customer_id=uuid4()
        )


async def test_related_entities_carry_the_fake_marker(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    entities = await fake_toolset.relationship_tool.get_related_entities(
        FAKE_TRANSACTION_ID
    )

    assert len(entities) == 3
    assert all(
        entity.risk_note and entity.risk_note.startswith("FAKE-DATA:") for entity in entities
    )


async def test_related_entities_refuse_an_unknown_transaction(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    with pytest.raises(FakeToolsetError, match="no transaction"):
        await fake_toolset.relationship_tool.get_related_entities(uuid4())


async def test_merchant_profile_reports_observed_statistics(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    profile = await fake_toolset.merchant_profile_tool.get_merchant_profile(FAKE_MERCHANT_ID)

    assert profile.observed is not None
    assert profile.observed.transaction_count == 7
    assert profile.observed.average_daily_volume is not None
    assert profile.reference.startswith("FAKE-DATA:")


async def test_customer_history_is_reproducible(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    first = await fake_toolset.customer_history_tool.get_customer_history(FAKE_CUSTOMER_ID)
    second = await fake_toolset.customer_history_tool.get_customer_history(FAKE_CUSTOMER_ID)

    assert first == second
    assert first.context.amount_statistics is not None
    assert first.context.amount_statistics.maximum == Decimal("2800.00")


async def test_prior_cases_requires_exactly_one_scope(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    tool = fake_toolset.case_history_tool

    with pytest.raises(InvestigationToolError, match="exactly one"):
        await tool.get_prior_cases()
    with pytest.raises(InvestigationToolError, match="exactly one"):
        await tool.get_prior_cases(
            customer_id=FAKE_CUSTOMER_ID, entity_ref="device-abc-123"
        )


async def test_prior_cases_return_the_fixed_case(
    fake_toolset: FakeInvestigationToolset,
) -> None:
    cases = await fake_toolset.case_history_tool.get_prior_cases(
        customer_id=FAKE_CUSTOMER_ID
    )

    assert len(cases) == 1
    assert cases[0].status == "CLEARED"
    assert cases[0].reference.startswith("FAKE-DATA:")


async def test_fakes_are_deterministic_across_instances() -> None:
    """Two independent toolsets must produce identical output."""

    first = build_fake_toolset()
    second = build_fake_toolset()

    assert await first.customer_history_tool.get_customer_history(
        FAKE_CUSTOMER_ID
    ) == await second.customer_history_tool.get_customer_history(FAKE_CUSTOMER_ID)
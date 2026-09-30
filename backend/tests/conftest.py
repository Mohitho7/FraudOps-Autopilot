"""Shared pytest fixtures for the backend test suite.

Batch 1 covered contracts only: schema validation, state creation, tool
interfaces and the service boundary. Batch 2 adds the orchestration layer --
graph compilation, node execution, checkpoint/resume and error handling -- so
these fixtures also provide the deterministic fake toolset and the environment
gate it requires.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from app.agents.tools.base import InvestigationToolError
from app.agents.tools.fakes import (
    ALLOW_FAKE_TOOLS_ENV,
    FakeInvestigationToolset,
    FakeMerchantProfileTool,
    build_fake_toolset,
)
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


@pytest.fixture(autouse=True)
def fake_tools_enabled(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Enable the deterministic fake read tools for every test.

    Autouse so a test can never silently depend on the gate being off. The fake
    tools themselves re-check the variable on every call, so the
    ``fakes_disabled`` tests can still exercise the refusal path.
    """

    monkeypatch.setenv(ALLOW_FAKE_TOOLS_ENV, "true")
    yield


@pytest.fixture
def fakes_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Turn the fake-tool gate off for tests that assert the refusal."""

    monkeypatch.setenv(ALLOW_FAKE_TOOLS_ENV, "false")


@pytest.fixture
def fake_toolset() -> FakeInvestigationToolset:
    """The deterministic fake toolset, matching the demo scenario ids."""

    return build_fake_toolset()


@pytest.fixture
def failing_toolset() -> Iterator[FakeInvestigationToolset]:
    """A fake toolset whose merchant lookup fails until the read layer recovers.

    Used to prove that a node failure is recorded, that the investigation is
    left in ``FAILED`` with a reviewer-safe error, and that resume reruns only
    the unfinished work.

    ``FakeInvestigationToolset`` is frozen, so the outage is installed on the
    merchant tool instance rather than by rebinding the field. Call
    :func:`restore_read_layer` to bring the tool back.

    Raises:
        InvestigationToolError: On every merchant-profile call until restored.
    """

    toolset = build_fake_toolset()
    simulate_read_layer_outage(toolset)
    try:
        yield toolset
    finally:
        restore_read_layer(toolset)


def restore_read_layer(toolset: FakeInvestigationToolset) -> None:
    """Undo a simulated read-layer outage on ``toolset``.

    The real deterministic merchant tool is copied onto the failing tool
    instance, so recovery needs no new object and no service rebuild.
    """

    toolset.merchant_profile_tool.get_merchant_profile = (
        FakeMerchantProfileTool().get_merchant_profile
    )


def simulate_read_layer_outage(toolset: FakeInvestigationToolset) -> None:
    """Make every merchant-profile call on ``toolset`` fail."""

    async def explode(*args: object, **kwargs: object) -> None:
        raise InvestigationToolError("simulated read-layer outage")

    toolset.merchant_profile_tool.get_merchant_profile = explode  # type: ignore[method-assign]

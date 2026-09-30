"""Tests for the investigation service boundary and the startup policy.

The service is a Batch 1 stub: it creates, stores and returns investigation
state. No test here claims that investigation analysis runs.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.agents.config import InvestigationSettings
from app.agents.graph.state import InvestigationState
from app.schemas.investigation import (
    InvestigationStatus,
    InvestigationStep,
    InvestigationTrigger,
    Severity,
)
from app.services.investigation_service import (
    InMemoryInvestigationService,
    InvestigationNotFoundError,
    InvestigationNotRequiredError,
    should_start_investigation,
)
from tests.conftest import TRANSACTION_ID, make_request


def _run(coro):
    return asyncio.run(coro)


def test_start_investigation_creates_the_initial_state() -> None:
    service = InMemoryInvestigationService()

    state = _run(service.start_investigation(make_request()))

    assert isinstance(state, InvestigationState)
    assert state.transaction_id == TRANSACTION_ID
    assert state.status is InvestigationStatus.RUNNING
    assert state.current_step is InvestigationStep.LOAD_STATE
    assert state.completed_steps == []
    assert len(state.activity) == 1
    assert state.activity[0].step is InvestigationStep.LOAD_STATE
    assert state.activity[0].status == "COMPLETED"
    assert "deterministic engine" in state.activity[0].summary


def test_get_investigation_returns_the_stored_state() -> None:
    service = InMemoryInvestigationService()
    started = _run(service.start_investigation(make_request()))

    fetched = _run(service.get_investigation(started.investigation_id))

    assert fetched is started


def test_get_investigation_rejects_an_unknown_id() -> None:
    service = InMemoryInvestigationService()

    with pytest.raises(InvestigationNotFoundError):
        _run(service.get_investigation(uuid4()))


def test_resume_returns_the_checkpointed_state() -> None:
    service = InMemoryInvestigationService()
    started = _run(service.start_investigation(make_request()))
    started.mark_step_completed(InvestigationStep.LOAD_STATE)
    started.current_step = InvestigationStep.CHECK_EVIDENCE

    resumed = _run(service.resume_investigation(started.investigation_id))

    assert resumed.current_step is InvestigationStep.CHECK_EVIDENCE
    assert resumed.completed_steps == [InvestigationStep.LOAD_STATE]
    assert resumed.status is InvestigationStatus.RUNNING


def test_resume_rejects_an_unknown_id() -> None:
    service = InMemoryInvestigationService()

    with pytest.raises(InvestigationNotFoundError):
        _run(service.resume_investigation(uuid4()))


def test_two_investigations_get_distinct_ids() -> None:
    service = InMemoryInvestigationService()

    first = _run(service.start_investigation(make_request()))
    second = _run(service.start_investigation(make_request()))

    assert first.investigation_id != second.investigation_id


@pytest.mark.parametrize("severity", [Severity.HIGH, Severity.CRITICAL])
def test_automatic_investigation_is_allowed_for_high_and_critical(severity) -> None:
    request = make_request(severity=severity)

    assert should_start_investigation(request) is True


@pytest.mark.parametrize("severity", [Severity.LOW, Severity.MEDIUM])
def test_automatic_investigation_is_blocked_for_low_and_medium(severity) -> None:
    request = make_request(severity=severity)

    assert should_start_investigation(request) is False


def test_reviewer_request_overrides_the_severity_threshold() -> None:
    request = make_request(
        severity=Severity.LOW,
        trigger=InvestigationTrigger.REVIEWER_REQUEST,
    )

    assert should_start_investigation(request) is True


def test_threshold_is_configurable() -> None:
    request = make_request(severity=Severity.MEDIUM)
    settings = InvestigationSettings(min_auto_investigation_severity=Severity.MEDIUM)

    assert should_start_investigation(request, settings) is True


def test_start_rejects_a_request_below_the_threshold() -> None:
    service = InMemoryInvestigationService()
    request = make_request(severity=Severity.MEDIUM)

    with pytest.raises(InvestigationNotRequiredError):
        _run(service.start_investigation(request))


def test_settings_never_expose_the_api_key() -> None:
    settings = InvestigationSettings(openai_api_key="sk-not-a-real-key")

    assert "sk-not-a-real-key" not in repr(settings)
    assert settings.llm_available is True
    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "sk-not-a-real-key"


def test_settings_report_no_llm_without_a_key() -> None:
    settings = InvestigationSettings(openai_api_key=None)

    assert settings.llm_available is False


def test_settings_can_disable_the_llm() -> None:
    settings = InvestigationSettings(
        openai_api_key="sk-not-a-real-key",
        llm_enabled=False,
    )

    assert settings.llm_available is False


def test_service_accepts_a_request_without_a_transaction_context() -> None:
    service = InMemoryInvestigationService()
    request = make_request(transaction_context=None)

    state = _run(service.start_investigation(request))

    assert state.transaction_context is None
    assert state.status is InvestigationStatus.RUNNING

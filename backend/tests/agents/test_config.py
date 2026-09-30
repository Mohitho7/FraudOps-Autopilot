"""Tests for the environment-driven investigation settings (Member 2)."""

from __future__ import annotations

import pytest

from app.agents.config import (
    DEFAULT_OPENAI_MODEL,
    InvestigationSettings,
    get_investigation_settings,
)
from app.schemas.investigation import Severity

_ENV_VARS = (
    "OPENAI_API_KEY",
    "FRAUDOPS_INVESTIGATION_OPENAI_API_KEY",
    "FRAUDOPS_INVESTIGATION_OPENAI_MODEL",
    "FRAUDOPS_INVESTIGATION_LLM_ENABLED",
    "FRAUDOPS_INVESTIGATION_MAX_TOOL_RETRIES",
    "FRAUDOPS_INVESTIGATION_MIN_AUTO_INVESTIGATION_SEVERITY",
    "FRAUDOPS_INVESTIGATION_CHECKPOINT_BACKEND",
)


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate settings tests from the developer's real environment."""

    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    get_investigation_settings.cache_clear()


def test_defaults_are_used_when_nothing_is_configured() -> None:
    settings = InvestigationSettings()

    assert settings.openai_api_key is None
    assert settings.openai_model == DEFAULT_OPENAI_MODEL
    assert settings.llm_enabled is True
    assert settings.min_auto_investigation_severity is Severity.HIGH
    assert settings.checkpoint_backend == "memory"
    assert settings.llm_available is False


def test_prefixed_severity_is_configurable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "FRAUDOPS_INVESTIGATION_MIN_AUTO_INVESTIGATION_SEVERITY", "MEDIUM"
    )

    assert InvestigationSettings().min_auto_investigation_severity is Severity.MEDIUM


def test_openai_key_is_read_from_either_variable_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-value")

    settings = InvestigationSettings()

    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "sk-test-value"
    assert settings.llm_available is True


def test_prefixed_openai_key_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRAUDOPS_INVESTIGATION_OPENAI_API_KEY", "sk-prefixed")

    settings = InvestigationSettings()

    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "sk-prefixed"


def test_blank_key_counts_as_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """``.env.example`` ships blank placeholders; they must not enable the LLM."""

    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("FRAUDOPS_INVESTIGATION_OPENAI_API_KEY", "   ")

    settings = InvestigationSettings()

    assert settings.openai_api_key is None
    assert settings.llm_available is False


def test_disabling_the_llm_wins_over_a_present_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-value")
    monkeypatch.setenv("FRAUDOPS_INVESTIGATION_LLM_ENABLED", "false")

    settings = InvestigationSettings()

    assert settings.openai_api_key is not None
    assert settings.llm_available is False


def test_blank_model_falls_back_to_the_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: an empty model variable used to abort startup."""

    monkeypatch.setenv("FRAUDOPS_INVESTIGATION_OPENAI_MODEL", "")

    assert InvestigationSettings().openai_model == DEFAULT_OPENAI_MODEL


def test_explicit_model_is_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRAUDOPS_INVESTIGATION_OPENAI_MODEL", "gpt-4o")

    assert InvestigationSettings().openai_model == "gpt-4o"


def test_settings_are_cached_and_clearable(monkeypatch: pytest.MonkeyPatch) -> None:
    first = get_investigation_settings()

    assert get_investigation_settings() is first

    get_investigation_settings.cache_clear()
    monkeypatch.setenv("FRAUDOPS_INVESTIGATION_CHECKPOINT_BACKEND", "postgres")

    assert get_investigation_settings().checkpoint_backend == "postgres"


def test_retry_budget_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRAUDOPS_INVESTIGATION_MAX_TOOL_RETRIES", "99")

    with pytest.raises(ValueError):
        InvestigationSettings()
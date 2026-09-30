"""Environment configuration for the agentic investigation layer (Member 2).

Configuration comes from the environment only. No secret, key or credential is
stored in the repository, and nothing here has a hardcoded default for a
credential.

Variable names use the ``FRAUDOPS_INVESTIGATION_`` prefix so that Member 2
settings cannot collide with Member 1 (``FRAUDOPS_*``) or Member 4
(``DATABASE_URL``, ``AWS_*``) settings.

``Agent System Design`` section 16 requires that "the system still works when
the LLM is unavailable by using deterministic evidence and a fallback case
summary", so ``openai_api_key`` is optional and ``llm_enabled`` can be turned
off. No field raises at import time; callers check
:meth:`InvestigationSettings.llm_available`.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas.investigation import Severity

__all__ = ["InvestigationSettings", "get_investigation_settings"]

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
"""Fallback model id. Confirm with the team; override via the env variable."""


class InvestigationSettings(BaseSettings):
    """Settings required by the investigation layer.

    Batch 1 defines the surface only; the values that matter for Batch 2 are
    the model name, the retry budget and the minimum severity that triggers an
    automatic investigation.
    """

    model_config = SettingsConfigDict(
        env_prefix="FRAUDOPS_INVESTIGATION_",
        env_file=None,
        extra="ignore",
        populate_by_name=True,
    )

    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "FRAUDOPS_INVESTIGATION_OPENAI_API_KEY",
            "OPENAI_API_KEY",
        ),
        description=(
            "LLM access for the investigation workflow. ``OPENAI_API_KEY`` is "
            "the name used by the Technology Stack document; the prefixed name "
            "is accepted too. The value is never logged or returned."
        ),
    )
    openai_model: str = Field(
        default=DEFAULT_OPENAI_MODEL,
        min_length=1,
        description=(
            "Model id used for narration, evidence synthesis and recommendation. "
            "Confirm with the team; override via FRAUDOPS_INVESTIGATION_OPENAI_MODEL."
        ),
    )
    llm_enabled: bool = Field(
        default=True,
        description=(
            "Set to false to force the deterministic fallback path when no LLM "
            "access is available."
        ),
    )
    max_tool_retries: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Bounded retry budget per tool call (Agent System Design 9/13).",
    )
    investigation_timeout_seconds: int = Field(
        default=120,
        gt=0,
        description="Wall-clock budget for a single investigation run.",
    )
    min_auto_investigation_severity: Severity = Field(
        default=Severity.HIGH,
        description=(
            "Lowest severity that may start an automatic investigation. "
            "LOW/MEDIUM stays in monitor/aggregate mode "
            "(Agent System Design sections 4 and 10)."
        ),
    )
    checkpoint_backend: str = Field(
        default="memory",
        description=(
            "LangGraph checkpointer backend for resume-after-failure. 'memory' "
            "until Member 4 provides the PostgreSQL checkpointer."
        ),
    )

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def _blank_key_is_absent(cls, value: object) -> object:
        """Treat an empty or whitespace-only key as no key at all.

        ``.env.example`` ships blank placeholders, and an unset shell variable
        exported as an empty string must not count as LLM access. Without this,
        ``llm_available`` would report True for a blank key and the
        deterministic fallback required by ``Agent System Design`` section 16
        would never engage.
        """

        if isinstance(value, SecretStr):
            value = value.get_secret_value()
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("openai_model", mode="before")
    @classmethod
    def _blank_model_falls_back_to_default(cls, value: object) -> object:
        """Treat a blank model id as unset so the default applies.

        ``.env.example`` leaves the variable empty; an empty string would fail
        the ``min_length=1`` constraint and abort startup.
        """

        if value is None or (isinstance(value, str) and not value.strip()):
            return DEFAULT_OPENAI_MODEL
        return value

    @property
    def llm_available(self) -> bool:
        """True when narration is possible in this environment."""

        return self.llm_enabled and self.openai_api_key is not None


@lru_cache(maxsize=1)
def get_investigation_settings() -> InvestigationSettings:
    """Return the process-wide settings instance (cached)."""

    return InvestigationSettings()

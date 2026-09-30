"""Investigation service boundary (Member 2).

This is the single entry point the rest of the backend uses to start, read and
resume an investigation:

* Member 1's pipeline calls :meth:`InvestigationService.start_investigation`
  after the risk engine classified a transaction.
* Member 1's case/transaction API calls
  :meth:`InvestigationService.get_investigation` to serve the console.
* Batch 2 wires :meth:`InvestigationService.resume_investigation` to the
  LangGraph checkpointer for resume-after-failure
  (``Agent System Design`` section 13).

Status
------
Batch 1 provides the boundary plus a non-persistent
:class:`InMemoryInvestigationService` used by tests. It stores and returns
state; it does **not** execute any analysis. Member 4's persistence layer
replaces the in-memory store in a later batch.

BOUNDARY
--------
The service does not compute risk, does not evaluate fraud rules and does not
notify reviewers. Those belong to Member 1 and Member 4.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Final
from uuid import UUID

from app.agents.config import InvestigationSettings, get_investigation_settings
from app.agents.graph.state import InvestigationState
from app.schemas.investigation import (
    InvestigationRequest,
    InvestigationStep,
    InvestigationTrigger,
    Severity,
)

__all__ = [
    "InMemoryInvestigationService",
    "InvestigationNotFoundError",
    "InvestigationNotRequiredError",
    "InvestigationService",
    "InvestigationServiceError",
    "should_start_investigation",
]

_SEVERITY_ORDER: Final[dict[Severity, int]] = {
    Severity.LOW: 0,
    Severity.MEDIUM: 1,
    Severity.HIGH: 2,
    Severity.CRITICAL: 3,
}


class InvestigationServiceError(RuntimeError):
    """Base error for the investigation service."""


class InvestigationNotFoundError(InvestigationServiceError, LookupError):
    """Raised when an investigation id is unknown."""


class InvestigationNotRequiredError(InvestigationServiceError):
    """Raised when a request does not meet the automatic investigation policy.

    LOW and MEDIUM risk stays in monitor/aggregate mode unless a reviewer
    explicitly requests an investigation (``Agent System Design`` sections 4
    and 10).
    """


def should_start_investigation(
    request: InvestigationRequest,
    settings: InvestigationSettings | None = None,
) -> bool:
    """Return whether ``request`` may start an investigation.

    Policy from ``Agent System Design`` sections 4 and 10: automatic
    investigation starts at HIGH or CRITICAL (configurable), while a reviewer
    request is always allowed.

    This is a policy check, not fraud logic: the severity itself was computed
    by Member 1's risk engine.
    """

    if request.trigger is InvestigationTrigger.REVIEWER_REQUEST:
        return True
    effective = settings or get_investigation_settings()
    return _SEVERITY_ORDER[request.severity] >= _SEVERITY_ORDER[
        effective.min_auto_investigation_severity
    ]


class InvestigationService(ABC):
    """Orchestration boundary for investigations."""

    @abstractmethod
    async def start_investigation(
        self,
        request: InvestigationRequest,
        *,
        settings: InvestigationSettings | None = None,
    ) -> InvestigationState:
        """Start a new investigation for a Member 1 fraud result.

        Args:
            request: Member 1's deterministic fraud result.
            settings: Optional settings override, mainly for tests.

        Returns:
            The initial investigation state, positioned at ``LOAD_STATE``.

        Raises:
            InvestigationNotRequiredError: When the request is below the
                automatic investigation threshold and was not explicitly
                requested by a reviewer.
        """

    @abstractmethod
    async def get_investigation(
        self,
        investigation_id: UUID,
    ) -> InvestigationState:
        """Return a stored investigation state.

        Raises:
            InvestigationNotFoundError: When the id is unknown.
        """

    @abstractmethod
    async def resume_investigation(
        self,
        investigation_id: UUID,
    ) -> InvestigationState:
        """Resume an interrupted investigation from its last checkpoint.

        Raises:
            InvestigationNotFoundError: When the id is unknown.
        """


class InMemoryInvestigationService(InvestigationService):
    """Batch 1 service stub backed by a process-local dictionary.

    Deliberately minimal: it creates, stores and returns investigation state
    so the boundary is testable, and it executes **no** analysis. A production
    implementation backed by Member 4's ``investigations`` table replaces it
    in a later batch.
    """

    def __init__(self) -> None:
        self._states: dict[UUID, InvestigationState] = {}

    async def start_investigation(
        self,
        request: InvestigationRequest,
        *,
        settings: InvestigationSettings | None = None,
    ) -> InvestigationState:
        """Create and store the initial state for ``request``."""

        if not should_start_investigation(request, settings):
            raise InvestigationNotRequiredError(
                f"severity {request.severity} is below the automatic "
                "investigation threshold; a reviewer must request it explicitly"
            )
        state = InvestigationState.from_request(request)
        state.record_activity(
            step=InvestigationStep.LOAD_STATE,
            status="COMPLETED",
            summary=(
                f"Investigation started for transaction {request.transaction_id} "
                f"with {len(request.triggered_rules)} triggered rule result(s) "
                f"from the deterministic engine"
            ),
        )
        self._states[state.investigation_id] = state
        return state

    async def get_investigation(self, investigation_id: UUID) -> InvestigationState:
        """Return the stored state for ``investigation_id``."""

        try:
            return self._states[investigation_id]
        except KeyError as error:
            raise InvestigationNotFoundError(
                f"unknown investigation_id: {investigation_id}"
            ) from error

    async def resume_investigation(self, investigation_id: UUID) -> InvestigationState:
        """Return the state to resume from.

        Batch 1 does not execute the workflow, so this returns the stored state
        unchanged, with its current step and completed steps intact. Batch 2
        routes this call to the LangGraph checkpointer and continues from
        ``state.current_step``.
        """

        return await self.get_investigation(investigation_id)

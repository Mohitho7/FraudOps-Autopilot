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
Batch 2 provides two implementations of this boundary:

* :class:`InMemoryInvestigationService` -- the original Batch 1 stub. It stores
  and returns state and executes no analysis. Kept unchanged for the contract
  tests.
* :class:`LangGraphInvestigationService` -- the Batch 2 engine. It delegates
  orchestration to the compiled LangGraph graph and owns the checkpoint store,
  the toolset and the idempotency key.

Member 4's persistence layer replaces the in-memory checkpoint store in a later
batch; nothing else has to change.

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
from app.agents.graph.checkpoint import (
    InvestigationCheckpointStore,
    build_checkpoint_store,
)
from app.agents.graph.errors import InvestigationWorkflowError
from app.agents.graph.state import InvestigationState
from app.agents.graph.workflow import build_investigation_graph
from app.agents.tools.base import InvestigationToolset
from app.schemas.investigation import (
    InvestigationRequest,
    InvestigationStatus,
    InvestigationStep,
    InvestigationTrigger,
    Severity,
)
from app.schemas.investigation_result import InvestigationError

__all__ = [
    "InMemoryInvestigationService",
    "InvestigationAlreadyCompletedError",
    "InvestigationAlreadyRunningError",
    "InvestigationNotFoundError",
    "InvestigationNotRequiredError",
    "InvestigationService",
    "InvestigationServiceError",
    "LangGraphInvestigationService",
    "investigation_identity_key",
    "should_start_investigation",
]

_SEVERITY_ORDER: Final[dict[Severity, int]] = {
    Severity.LOW: 0,
    Severity.MEDIUM: 1,
    Severity.HIGH: 2,
    Severity.CRITICAL: 3,
}

_RESUMABLE_STATUSES: Final[frozenset[InvestigationStatus]] = frozenset(
    {InvestigationStatus.RUNNING, InvestigationStatus.FAILED}
)
"""Statuses a caller may resume from."""


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


class InvestigationAlreadyRunningError(InvestigationServiceError):
    """Raised when starting an investigation that is already in flight.

    The correct recovery is :meth:`InvestigationService.resume_investigation` on
    the existing id, not a second run.
    """


class InvestigationAlreadyCompletedError(InvestigationServiceError):
    """Raised when starting an investigation that already reached a final state.

    Completed and ``WAITING_HUMAN`` investigations are not re-run: re-running
    them would duplicate the audit trail and could contradict a human decision
    that was already recorded.
    """


def investigation_identity_key(request: InvestigationRequest) -> tuple[str, str]:
    """Return the idempotency key for a Member 1 fraud result.

    Batch 2 decision, not a Batch 1 contract
    ----------------------------------------
    Batch 1 defines the investigation identity as the ``investigation_id`` UUID
    and does not define how a repeated request maps onto an existing
    investigation. Without a key, two deliveries of the same Member 1 fraud
    result would create two investigations and two diverging audit trails.

    The key is ``(transaction_id, case_id)``: the transaction being
    investigated plus the case it belongs to. Re-delivering the same result is
    then idempotent, while a genuinely different case for the same transaction
    still gets its own investigation.

    This is documented rather than silent because it is a cross-member
    behaviour: Member 1 owns when a fraud result is emitted, and Member 4 owns
    where the mapping is persisted. See ``docs/member2/agent-workflow.md``.
    """

    return (str(request.transaction_id), str(request.case_id))


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


class LangGraphInvestigationService(InvestigationService):
    """Batch 2 service that runs the compiled LangGraph graph.

    Responsibilities kept here, deliberately:

    * the automatic-investigation policy,
    * the idempotency key,
    * mapping an investigation id to a checkpoint thread,
    * translating a graph failure into ``InvestigationStatus.FAILED`` plus a
      stored :class:`~app.schemas.investigation_result.InvestigationError`.

    Everything else -- which nodes run, in what order, what they load -- lives
    in the graph, not here.

    Persistence
    -----------
    The checkpoint store is injected. With the Batch 2
    :class:`~app.agents.graph.checkpoint.InMemoryCheckpointStore` the engine is
    fully functional but **not durable across process restarts**. Member 4 owns
    the PostgreSQL checkpointer.
    """

    def __init__(
        self,
        toolset: InvestigationToolset,
        *,
        settings: InvestigationSettings | None = None,
        checkpoint_store: InvestigationCheckpointStore | None = None,
    ) -> None:
        self._settings = settings or get_investigation_settings()
        self._toolset = toolset
        self._store = checkpoint_store or build_checkpoint_store(
            self._settings.checkpoint_backend
        )
        self._graph = build_investigation_graph(
            toolset,
            self._settings,
            self._store,
        )
        self._by_identity: dict[tuple[str, str], UUID] = {}
        self._states: dict[UUID, InvestigationState] = {}

    @property
    def checkpoint_store(self) -> InvestigationCheckpointStore:
        """The checkpoint store this service was built with."""

        return self._store

    async def start_investigation(
        self,
        request: InvestigationRequest,
        *,
        settings: InvestigationSettings | None = None,
    ) -> InvestigationState:
        """Validate, create state and run the graph to completion.

        Args:
            request: Member 1's deterministic fraud result.
            settings: Optional settings override for the policy check only.

        Returns:
            The final investigation state.

        Raises:
            InvestigationNotRequiredError: Below the automatic severity
                threshold without a reviewer request.
            InvestigationAlreadyRunningError: An investigation for the same
                ``(transaction_id, case_id)`` is still running. Resume it
                instead.
            InvestigationAlreadyCompletedError: That investigation already
                reached a final status.
            InvestigationWorkflowError: The graph failed. The failure is
                persisted and the state is returned with ``status=FAILED``.
        """

        if not should_start_investigation(request, settings or self._settings):
            raise InvestigationNotRequiredError(
                f"severity {request.severity} is below the automatic "
                "investigation threshold; a reviewer must request it explicitly"
            )

        identity = investigation_identity_key(request)
        existing_id = self._by_identity.get(identity)
        if existing_id is not None:
            existing = self._states.get(existing_id)
            if existing is not None:
                if existing.status is InvestigationStatus.RUNNING:
                    raise InvestigationAlreadyRunningError(
                        "investigation "
                        f"{existing_id} for this fraud result is already "
                        "running; call resume_investigation instead"
                    )
                if existing.status in {
                    InvestigationStatus.COMPLETED,
                    InvestigationStatus.WAITING_HUMAN,
                }:
                    raise InvestigationAlreadyCompletedError(
                        f"investigation {existing_id} for this fraud result is "
                        f"already {existing.status.value}"
                    )

        state = InvestigationState.from_request(request)
        self._by_identity[identity] = state.investigation_id
        self._states[state.investigation_id] = state
        await self._store.save_state(state)
        return await self._run(state)

    async def get_investigation(
        self, investigation_id: UUID
    ) -> InvestigationState:
        """Return the stored state for ``investigation_id``.

        Raises:
            InvestigationNotFoundError: When the id is unknown.
        """

        stored = self._states.get(investigation_id)
        if stored is None:
            raise InvestigationNotFoundError(
                f"unknown investigation_id: {investigation_id}"
            )
        return stored.model_copy(deep=True)

    async def resume_investigation(
        self, investigation_id: UUID
    ) -> InvestigationState:
        """Continue an interrupted or failed investigation.

        Completed nodes are not re-executed: the graph routes on the activity
        timeline, so only the unfinished step runs again.

        Raises:
            InvestigationNotFoundError: When the id is unknown.
            InvestigationWorkflowError: The resumed run failed again.
        """

        state = self._states.get(investigation_id)
        if state is None:
            raise InvestigationNotFoundError(
                f"unknown investigation_id: {investigation_id}"
            )
        if state.status in {InvestigationStatus.COMPLETED, InvestigationStatus.WAITING_HUMAN}:
            # Nothing left to do. Returning the state keeps resume idempotent.
            return state.model_copy(deep=True)

        state.status = InvestigationStatus.RUNNING
        state.error = None
        await self._store.save_state(state)
        return await self._run(state)

    async def _run(self, state: InvestigationState) -> InvestigationState:
        """Invoke the graph and fold the outcome back into the service."""

        config = self._store.thread_config(state.investigation_id)
        try:
            # ``ainvoke(state, ...)`` starts the thread; ``ainvoke(None, ...)``
            # continues it. Passing the state on resume would restart the graph
            # from scratch, so the input is supplied only on the first run.
            checkpointed = await self._store.read_checkpoint(state.investigation_id)
            final = await self._graph.ainvoke(
                None if checkpointed is not None else state, config
            )
        except InvestigationWorkflowError as exc:
            failed = await self._restore(state)
            if failed.status is not InvestigationStatus.FAILED:
                failed.status = InvestigationStatus.FAILED
                failed.current_step = InvestigationStep.FAILURE
            if failed.error is None:
                # The node recorded the failure in its own audit entry; the
                # reviewer-facing error is still owed here.
                failed.error = _error_from(exc, failed.current_step)
            failed.retry_count += 1
            await self._store.save_state(failed)
            self._states[failed.investigation_id] = failed
            raise
        except Exception as exc:  # noqa: BLE001 - unexpected node failure
            failed = await self._restore(state)
            failed.status = InvestigationStatus.FAILED
            failed.current_step = InvestigationStep.FAILURE
            failed.error = _error_from(exc, state.current_step)
            failed.retry_count += 1
            failed.record_activity(
                step=InvestigationStep.FAILURE,
                status="FAILED",
                summary=f"Investigation failed with {type(exc).__name__}",
                error=str(exc),
            )
            await self._store.save_state(failed)
            self._states[failed.investigation_id] = failed
            raise InvestigationWorkflowError(
                f"investigation {failed.investigation_id} failed: {exc}",
                step=failed.current_step,
            ) from exc

        result = _state_from(final)
        self._states[result.investigation_id] = result
        await self._store.save_state(result)
        return result

    async def _restore(self, reference: InvestigationState) -> InvestigationState:
        """Return the most complete state available for a failed run.

        Order matters. LangGraph's checkpoint is authoritative because it holds
        every node that completed before the failure; the store's materialised
        snapshot is next; the service's own copy is the last resort.

        The result never silently loses completed work: even the pre-run copy
        carries the activity timeline and ``completed_steps``, so a caller can
        always see how far the investigation got.
        """

        investigation_id = reference.investigation_id
        for candidate in (
            await self._store.read_checkpoint(investigation_id),
            await self._store.load_state(investigation_id),
            self._states.get(investigation_id),
        ):
            if candidate is not None:
                return candidate.model_copy(deep=True)
        return reference.model_copy(deep=True)


def _error_from(exc: BaseException, step: InvestigationStep) -> InvestigationError:
    """Build a reviewer-safe error from an unexpected exception.

    The message is the exception text, never a traceback: it ends up in the
    Member 3 response (``Agent System Design`` sections 12 and 13).
    """

    return InvestigationError(
        step=step,
        error_type=type(exc).__name__,
        message=str(exc)[:2000] or type(exc).__name__,
        retryable=True,
    )


def _state_from(payload: object) -> InvestigationState:
    """Coerce a LangGraph result into an :class:`InvestigationState`."""

    if isinstance(payload, InvestigationState):
        return payload
    if isinstance(payload, dict):
        return InvestigationState.model_validate(payload)
    raise InvestigationWorkflowError(
        f"graph returned an unusable state payload: {type(payload).__name__}"
    )

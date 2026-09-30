"""Checkpoint abstraction for the investigation workflow (Member 2).

Purpose
-------
``Agent System Design`` section 13 requires that an interrupted or failed
investigation can be resumed from a checkpoint, with completed work preserved.
LangGraph performs that job through a *checkpointer*, keyed by a thread id.

This module is the seam between Member 2 and that mechanism:

* :class:`InvestigationCheckpointStore` is the interface Member 2 depends on.
* :class:`InMemoryCheckpointStore` is the deterministic implementation used by
  Batch 2. It is **not** production persistence.
* :meth:`InvestigationCheckpointStore.thread_config` maps an investigation id to
  the LangGraph thread config, so the thread identity is always the
  investigation id and never an ad-hoc string.

Why not call LangGraph's ``MemorySaver`` directly?
-------------------------------------------------
Because Member 4 owns production persistence. Depending on the small interface
below keeps the graph, the nodes and the service unchanged when the PostgreSQL
checkpointer arrives: a production store is added next to this module and
selected through
:attr:`~app.agents.config.InvestigationSettings.checkpoint_backend`.

Durability
----------
:class:`InMemoryCheckpointStore` lives in the process that created it. It
survives a failed node and a service restart *within the same process only*.
Anything that must outlive the process needs the Member 4 PostgreSQL
checkpointer. See ``docs/member2/data-contract.md``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from app.agents.graph.errors import (
    CheckpointError,
    UnsupportedCheckpointBackendError,
)
from app.agents.graph.state import InvestigationState

__all__ = [
    "CHECKPOINT_THREAD_PREFIX",
    "InMemoryCheckpointStore",
    "InvestigationCheckpointStore",
    "build_checkpoint_store",
]

CHECKPOINT_THREAD_PREFIX = "investigation"
"""Thread-id prefix, so a checkpoint thread is recognisable in traces."""


def _state_type_allowlist() -> tuple[tuple[str, str], ...]:
    """Return the msgpack allowlist for every type the state can hold.

    LangGraph's default checkpoint serializer permits arbitrary types and logs a
    warning per deserialization, then plans to block them. Naming the types
    explicitly is both quieter and stricter: the checkpointer only accepts
    ``InvestigationState`` and the schemas it transitively references, so a
    tampered checkpoint row cannot name an unrelated class.

    The list is derived from the state model rather than written out by hand, so
    a Batch 1 schema change cannot silently fall outside the allowlist.
    """

    from enum import Enum

    from pydantic import BaseModel

    found: set[tuple[str, str]] = set()
    pending = [InvestigationState]
    seen: set[type] = set()
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        found.add((current.__module__, current.__qualname__))
        for field in current.model_fields.values():
            for annotation in _unwrap_annotations(field.annotation):
                if not isinstance(annotation, type):
                    continue
                if issubclass(annotation, (BaseModel, Enum)):
                    pending.append(annotation)
    return tuple(sorted(found))


def _unwrap_annotations(annotation: Any) -> tuple[Any, ...]:
    """Flatten unions, lists and dicts into the concrete types they hold."""

    from typing import get_args

    found: list[Any] = [annotation]
    while found:
        current = found.pop()
        for argument in get_args(current):
            found.append(argument)
            origin = getattr(current, "__origin__", None)
            if origin is not None:
                found.append(origin)
    return tuple(found)


def investigation_thread_id(investigation_id: UUID) -> str:
    """Return the LangGraph thread id for an investigation.

    The investigation id is the thread identity, which is what makes resume
    deterministic: re-invoking with the same investigation id continues that
    investigation, and a different id is a different investigation.
    """

    return f"{CHECKPOINT_THREAD_PREFIX}:{investigation_id}"


class InvestigationCheckpointStore(ABC):
    """Interface for persisting and restoring investigation progress."""

    @abstractmethod
    def thread_config(self, investigation_id: UUID) -> dict[str, Any]:
        """Return the LangGraph runnable config for ``investigation_id``.

        The returned mapping contains a single ``configurable.thread_id`` entry.
        """

    @abstractmethod
    def saver(self) -> Any:
        """Return the LangGraph checkpointer object to compile the graph with."""

    @abstractmethod
    async def read_checkpoint(self, investigation_id: UUID) -> InvestigationState | None:
        """Return the state LangGraph last checkpointed for ``investigation_id``.

        This is the authoritative copy of a run: when a node raises, LangGraph
        keeps every node that completed before it. ``load_state`` is about a
        materialised snapshot, which is a different thing.
        """

    async def save_state(self, state: InvestigationState) -> None:
        """Persist the current state of an investigation.

        The default implementation only stamps ``last_checkpoint_at``; stores
        that keep their own copy override this.
        """

        if state.last_checkpoint_at is None:
            state.last_checkpoint_at = state.updated_at

    async def load_state(self, investigation_id: UUID) -> InvestigationState | None:
        """Return a previously stored state, or ``None`` when there is none.

        The default implementation returns ``None``: the LangGraph checkpointer
        owns the authoritative copy of a running graph, so this hook exists for
        stores that additionally keep a materialised state
        (Member 4's ``investigations.state_json`` column).
        """

        return None


class InMemoryCheckpointStore(InvestigationCheckpointStore):
    """Deterministic, process-local checkpoint store.

    Status
    ------
    This is the Batch 2 implementation used by tests and by a local run. It is
    **not** database persistence: the state is lost when the process exits. It
    exists so that resume is fully exercisable before Member 4 provides the
    PostgreSQL checkpointer (``Agent System Design`` section 13).
    """

    def __init__(self, saver: Any | None = None) -> None:
        self._saver = (
            saver
            if saver is not None
            else InMemorySaver(
                serde=JsonPlusSerializer(
                    allowed_msgpack_modules=_state_type_allowlist(),
                )
            )
        )
        self._states: dict[UUID, InvestigationState] = {}

    def thread_config(self, investigation_id: UUID) -> dict[str, Any]:
        return {"configurable": {"thread_id": investigation_thread_id(investigation_id)}}

    def saver(self) -> Any:
        return self._saver

    async def read_checkpoint(self, investigation_id: UUID) -> InvestigationState | None:
        config = self.thread_config(investigation_id)
        snapshot = await self._saver.aget(config)
        if snapshot is None:
            return None
        channel_values = (snapshot or {}).get("channel_values") or {}
        if "investigation_id" not in channel_values:
            # A checkpoint exists for the thread but holds no investigation yet,
            # which is what a run that failed in its very first superstep leaves.
            return None
        # A checkpoint holds one channel per state field *plus* LangGraph's own
        # routing channels ("branch:to:<node>"). The schema forbids extras, so
        # only the declared fields are handed back.
        fields = InvestigationState.model_fields
        state_values = {
            name: value for name, value in channel_values.items() if name in fields
        }
        return InvestigationState.model_validate(state_values)

    async def save_state(self, state: InvestigationState) -> None:
        state.last_checkpoint_at = datetime.now(timezone.utc)
        self._states[state.investigation_id] = state.model_copy(deep=True)

    async def load_state(self, investigation_id: UUID) -> InvestigationState | None:
        stored = self._states.get(investigation_id)
        if stored is None:
            return None
        return stored.model_copy(deep=True)

    async def clear(self, investigation_id: UUID | None = None) -> None:
        """Forget stored state.

        Test-only convenience: it makes assertions about a fresh start
        deterministic. Production stores keep the audit trail and do not
        provide this.
        """

        if investigation_id is None:
            self._states.clear()
            return
        self._states.pop(investigation_id, None)


def build_checkpoint_store(
    backend: str = "memory",
) -> InvestigationCheckpointStore:
    """Build the checkpoint store for ``backend``.

    Args:
        backend: Value of
            :attr:`~app.agents.config.InvestigationSettings.checkpoint_backend`.

    Returns:
        The store to compile the graph with.

    Raises:
        UnsupportedCheckpointBackendError: When ``backend`` is not ``memory``.
            ``postgres`` is reserved for Member 4's checkpointer; failing loudly
            is deliberate, because silently degrading to memory in production
            would make investigations look durable when they are not.
    """

    normalized = backend.strip().lower()
    if normalized == "memory":
        return InMemoryCheckpointStore()
    if normalized == "postgres":
        raise UnsupportedCheckpointBackendError(
            "checkpoint_backend='postgres' requires Member 4's LangGraph "
            "PostgreSQL checkpointer, which is not implemented yet. Use "
            "'memory' for local runs and tests; see docs/member2/data-contract.md.",
            step=None,
        )
    raise CheckpointError(
        f"unknown checkpoint backend: {backend!r}. "
        "Expected 'memory' (Member 4 provides 'postgres').",
        step=None,
    )
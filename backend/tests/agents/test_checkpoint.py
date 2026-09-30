"""Checkpoint store tests (Member 2, Batch 2).

Covers thread identity, the process-local store's contract, and the deliberate
failure modes of ``build_checkpoint_store``.
"""

from __future__ import annotations

from uuid import UUID, uuid4
from typing import Any

import pytest

from app.agents.graph.checkpoint import (
    CHECKPOINT_THREAD_PREFIX,
    InMemoryCheckpointStore,
    InvestigationCheckpointStore,
    build_checkpoint_store,
    investigation_thread_id,
)
from app.agents.graph.errors import (
    CheckpointError,
    UnsupportedCheckpointBackendError,
)
from app.agents.graph.state import InvestigationState
from app.schemas.investigation import InvestigationStatus
from tests.conftest import make_request


def test_thread_id_is_derived_from_the_investigation_id() -> None:
    state = InvestigationState.from_request(make_request())

    thread_id = investigation_thread_id(state.investigation_id)

    assert thread_id == f"{CHECKPOINT_THREAD_PREFIX}:{state.investigation_id}"
    assert str(state.investigation_id) in thread_id


def test_thread_config_carries_a_single_configurable_thread() -> None:
    state = InvestigationState.from_request(make_request())

    config = InMemoryCheckpointStore().thread_config(state.investigation_id)

    assert set(config) == {"configurable"}
    assert set(config["configurable"]) == {"thread_id"}


def test_memory_backend_builds_an_in_memory_store() -> None:
    store = build_checkpoint_store("memory")

    assert isinstance(store, InMemoryCheckpointStore)
    assert isinstance(store, InvestigationCheckpointStore)
    assert store.saver() is store.saver()


def test_backend_name_is_normalized() -> None:
    assert isinstance(build_checkpoint_store("  MEMORY "), InMemoryCheckpointStore)


def test_postgres_backend_is_refused_loudly() -> None:
    """Silently falling back to memory would look durable when it is not."""

    with pytest.raises(UnsupportedCheckpointBackendError, match="Member 4"):
        build_checkpoint_store("postgres")


def test_unknown_backend_is_refused() -> None:
    with pytest.raises(CheckpointError, match="unknown checkpoint backend"):
        build_checkpoint_store("sqlite")


async def test_saved_state_is_stamped_and_returned_as_a_copy() -> None:
    store = InMemoryCheckpointStore()
    state = InvestigationState.from_request(make_request())
    state.last_checkpoint_at = None

    await store.save_state(state)
    loaded = await store.load_state(state.investigation_id)

    assert state.last_checkpoint_at is not None
    assert loaded is not None
    assert loaded.investigation_id == state.investigation_id
    assert loaded is not state

    loaded.status = InvestigationStatus.FAILED
    assert (await store.load_state(state.investigation_id)).status is not (
        InvestigationStatus.FAILED
    )


async def test_load_returns_none_for_an_unknown_investigation() -> None:
    store = InMemoryCheckpointStore()

    assert await store.load_state(uuid4()) is None


async def test_clear_drops_one_or_all_investigations() -> None:
    store = InMemoryCheckpointStore()
    first = InvestigationState.from_request(make_request())
    second = InvestigationState.from_request(make_request(case_id=uuid4()))
    await store.save_state(first)
    await store.save_state(second)

    await store.clear(first.investigation_id)
    assert await store.load_state(first.investigation_id) is None
    assert await store.load_state(second.investigation_id) is not None

    await store.clear()
    assert await store.load_state(second.investigation_id) is None


async def test_the_base_store_declares_no_durable_copy() -> None:
    """The default hook is a no-op, which is exactly what Member 4 must implement."""

    class MinimalStore(InvestigationCheckpointStore):
        def thread_config(self, investigation_id: UUID) -> dict[str, Any]:
            return {"configurable": {"thread_id": str(investigation_id)}}

        def saver(self) -> Any:
            return object()

        async def read_checkpoint(self, investigation_id: UUID) -> InvestigationState | None:
            return None

    store = MinimalStore()

    assert await store.load_state(uuid4()) is None


def test_in_memory_store_is_usable_as_the_declared_interface() -> None:
    assert issubclass(InMemoryCheckpointStore, InvestigationCheckpointStore)
"""Errors raised by the investigation workflow engine (Member 2).

Batch 1 defined the errors of the *contracts*:
:mod:`app.agents.tools.base` (``InvestigationToolError``) and
:mod:`app.services.investigation_service`
(``InvestigationServiceError``). This module adds only what the workflow
itself needs on top of them: a node failed, or the checkpoint could not be
written or read.

BOUNDARY
--------
These errors carry reviewer-safe messages only. A stack trace is never put in
an :class:`~app.schemas.investigation_result.InvestigationError`, because that
model is serialised into the Member 3 response
(``Agent System Design`` sections 12 and 13).
"""

from __future__ import annotations

from app.agents.tools.base import InvestigationToolError
from app.schemas.investigation import InvestigationStep

__all__ = [
    "CheckpointError",
    "InvestigationWorkflowError",
    "ToolExecutionError",
    "UnsupportedCheckpointBackendError",
]


class InvestigationWorkflowError(RuntimeError):
    """Base error for a failed investigation workflow step.

    Attributes:
        step: Workflow step that failed, when known.
        tool_name: Approved tool involved in the failure, when applicable.
    """

    def __init__(
        self,
        message: str,
        *,
        step: InvestigationStep | None = None,
        tool_name: str | None = None,
    ) -> None:
        super().__init__(message)
        self.step = step
        self.tool_name = tool_name


class ToolExecutionError(InvestigationWorkflowError, InvestigationToolError):
    """An approved tool failed, timed out, or returned unusable output.

    Raised by the context-loading nodes. The node records the failure in the
    investigation activity timeline and sets
    :class:`~app.schemas.investigation_result.InvestigationError` on the state
    before re-raising, so the failure is never silently swallowed.
    """


class CheckpointError(InvestigationWorkflowError):
    """Checkpoint state could not be written or restored.

    Distinct from a tool failure: the investigation itself may be fine, but
    resumability is at risk, so the workflow must not report success.
    """


class UnsupportedCheckpointBackendError(CheckpointError):
    """The configured checkpoint backend is not implemented yet.

    ``InvestigationSettings.checkpoint_backend`` documents ``memory`` until
    Member 4 provides the PostgreSQL checkpointer required by
    ``Agent System Design`` section 13. Requesting ``postgres`` before then
    raises this error rather than silently falling back to memory, so a
    production deployment cannot believe it is durable when it is not.
    """
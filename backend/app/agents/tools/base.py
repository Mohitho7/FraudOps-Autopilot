"""Base types and errors for the approved investigation tools (Member 2).

Guardrails
----------
``System Design`` addendum, "Agent Tooling":

* Agents access data through narrow, approved tools -- never arbitrary
  database access.
* Every tool call is logged with input identifiers and output references.
* Tools return structured data that preserves the source record identifiers
  used as evidence.

Every tool in :mod:`app.agents.tools` is therefore:

1. a ``Protocol`` describing the least-privilege surface, and
2. a concrete implementation class whose methods raise
   :class:`ToolNotImplementedError` until the Batch 2+ implementation (and
   Member 4's database layer) exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from app.schemas.investigation import InvestigationStep

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.agents.tools.case_tools import PriorCasesTool
    from app.agents.tools.customer_tools import CustomerHistoryTool
    from app.agents.tools.merchant_tools import MerchantProfileTool
    from app.agents.tools.relationship_tools import RelatedEntitiesTool
    from app.agents.tools.transaction_tools import (
        RecentTransactionsTool,
        RuleResultsTool,
    )

__all__ = [
    "InvestigationToolError",
    "InvestigationToolset",
    "ToolCallRecord",
    "ToolNotImplementedError",
    "ToolStatus",
    "tool_reference",
]


class InvestigationToolError(RuntimeError):
    """Base error for tool failures raised inside the investigation workflow."""


class ToolNotImplementedError(InvestigationToolError, NotImplementedError):
    """Raised by the Batch 1 tool stubs.

    Raised instead of returning fabricated data so that no test or demo can
    accidentally present made-up fraud evidence as a real finding.
    """


class ToolStatus:
    """Lifecycle values for a recorded tool call."""

    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True, slots=True)
class ToolCallRecord:
    """Audit record of a single approved tool call.

    Persisted as part of the investigation audit trail
    (``Agent System Design`` section 12). Contains identifiers and references
    only -- never raw payloads containing personal data.
    """

    tool_name: str
    step: InvestigationStep
    input_refs: tuple[str, ...]
    output_refs: tuple[str, ...]
    status: str
    started_at: datetime
    completed_at: datetime
    error: str | None = None

    @classmethod
    def started(
        cls,
        *,
        tool_name: str,
        step: InvestigationStep,
        input_refs: tuple[str, ...],
        started_at: datetime | None = None,
    ) -> ToolCallRecord:
        """Create the initial ``STARTED`` record for a tool call."""

        moment = started_at or datetime.now(timezone.utc)
        return cls(
            tool_name=tool_name,
            step=step,
            input_refs=input_refs,
            output_refs=(),
            status=ToolStatus.STARTED,
            started_at=moment,
            completed_at=moment,
        )


class InvestigationToolset(Protocol):
    """The bundle of approved read tools handed to the investigation workflow.

    The workflow depends on this protocol, never on a database session, so the
    graph stays testable and the agent keeps least-privilege access. A
    production implementation is assembled in Batch 2 on top of Member 4's
    read layer.
    """

    @property
    def customer_history_tool(self) -> CustomerHistoryTool:
        """Tool exposing customer history and baseline metrics."""

    @property
    def transaction_history_tool(self) -> RecentTransactionsTool:
        """Tool exposing recent transactions for a customer or merchant."""

    @property
    def rule_results_tool(self) -> RuleResultsTool:
        """Tool exposing Member 1's stored rule results."""

    @property
    def merchant_profile_tool(self) -> MerchantProfileTool:
        """Tool exposing merchant/business profile and distribution."""

    @property
    def relationship_tool(self) -> RelatedEntitiesTool:
        """Tool exposing linked entities for a transaction."""

    @property
    def case_history_tool(self) -> PriorCasesTool:
        """Tool exposing previous cases for a customer or entity."""


def tool_reference(kind: str, identifier: UUID | str) -> str:
    """Build a stable ``<kind>:<identifier>`` reference for evidence citation.

    Example: ``transaction_reference(transaction_id)`` ->
    ``transaction:0f3d1c1e-...``. References are what findings and evidence
    items point at, so the reviewer can always trace a claim back to a stored
    record.
    """

    return f"{kind}:{identifier}"

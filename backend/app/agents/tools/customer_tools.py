"""Customer-facing investigation tools (Member 2).

Tool: ``get_customer_history`` (``Agent System Design`` section 7).

Purpose
-------
Supplies the historical customer behaviour the behavioral analysis capability
needs: the amount baseline, transaction frequency and previous review outcomes.

Guardrails
----------
* The tool is read-only and scoped to a single ``customer_id``.
* It returns stored facts only; it performs no interpretation and no scoring.
* Every call must be recorded in the investigation audit trail via
  :class:`~app.agents.tools.base.ToolCallRecord`.

Status: interface only. The database query is Member 4's persistence layer and
is implemented in a later batch.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.agents.tools.base import ToolNotImplementedError
from app.agents.tools.types import CustomerHistory, TimeWindow

__all__ = ["CustomerHistoryTool", "CustomerHistoryToolStub"]


class CustomerHistoryTool(Protocol):
    """Least-privilege read interface for customer history."""

    async def get_customer_history(
        self,
        customer_id: UUID,
        time_window: TimeWindow | None = None,
    ) -> CustomerHistory:
        """Return transactions and baseline metrics for ``customer_id``.

        Args:
            customer_id: Customer under investigation.
            time_window: Optional window. The implementation applies a
                documented default (90 days) when omitted.

        Returns:
            Customer history with deterministic baseline statistics.

        Raises:
            InvestigationToolError: When the lookup fails.
        """
        ...


class CustomerHistoryToolStub:
    """Batch 1 stub that refuses to fabricate customer history."""

    async def get_customer_history(
        self,
        customer_id: UUID,
        time_window: TimeWindow | None = None,
    ) -> CustomerHistory:
        """Not implemented until Member 4's persistence layer is available."""

        raise ToolNotImplementedError(
            "get_customer_history requires the PostgreSQL read layer "
            "(Member 4). Available from the Batch 2 implementation batch."
        )

"""Transaction-facing investigation tools (Member 2).

Tools: ``get_recent_transactions`` and ``get_rule_results``
(``Agent System Design`` section 7).

Purpose
-------
``get_recent_transactions``
    Recent activity for a customer or a merchant, used to spot bursts,
    clustering and merchant-side anomalies.
``get_rule_results``
    Member 1's stored rule results for the transaction, so the investigation
    can cite the deterministic outcome instead of recomputing it.

Guardrails
----------
* Read-only, scoped to a single subject, never a free-form query.
* ``get_rule_results`` returns Member 1's records verbatim; the investigation
  layer never re-evaluates a rule.
* ``calculate_geo_distance`` is intentionally **not** exposed here: distance and
  implied speed are Member 1's impossible-travel responsibility and must not be
  duplicated in the agent layer.

Status: interfaces only.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.agents.tools.base import ToolNotImplementedError
from app.agents.tools.types import RecentTransactionSet, RuleResultsResult, TimeWindow

__all__ = [
    "RecentTransactionsTool",
    "RecentTransactionsToolStub",
    "RuleResultsTool",
    "RuleResultsToolStub",
]


class RecentTransactionsTool(Protocol):
    """Least-privilege read interface for recent transaction activity."""

    async def get_recent_transactions(
        self,
        *,
        customer_id: UUID | None = None,
        merchant_id: UUID | None = None,
        time_window: TimeWindow | None = None,
        limit: int = 100,
    ) -> RecentTransactionSet:
        """Return recent transactions for exactly one subject.

        Args:
            customer_id: Customer scope. Mutually exclusive with ``merchant_id``.
            merchant_id: Merchant scope. Mutually exclusive with ``customer_id``.
            time_window: Optional window; a documented default is applied when
                omitted.
            limit: Maximum number of rows returned, bounded by the
                implementation to keep the agent's context small.

        Returns:
            Recent transactions plus their deterministic amount statistics.

        Raises:
            InvestigationToolError: When both or neither scope is supplied, or
                the lookup fails.
        """
        ...


class RecentTransactionsToolStub:
    """Batch 1 stub that refuses to fabricate transaction history."""

    async def get_recent_transactions(
        self,
        *,
        customer_id: UUID | None = None,
        merchant_id: UUID | None = None,
        time_window: TimeWindow | None = None,
        limit: int = 100,
    ) -> RecentTransactionSet:
        """Not implemented until Member 4's persistence layer is available."""

        raise ToolNotImplementedError(
            "get_recent_transactions requires the PostgreSQL read layer "
            "(Member 4). Available from the Batch 2 implementation batch."
        )


class RuleResultsTool(Protocol):
    """Least-privilege read interface for Member 1's stored rule results."""

    async def get_rule_results(self, transaction_id: UUID) -> RuleResultsResult:
        """Return the stored rule results for ``transaction_id``.

        Returns:
            All stored rule results, triggered or not, with Member 1's evidence
            values attached.

        Raises:
            InvestigationToolError: When the lookup fails.
        """
        ...


class RuleResultsToolStub:
    """Batch 1 stub that refuses to fabricate rule results."""

    async def get_rule_results(self, transaction_id: UUID) -> RuleResultsResult:
        """Not implemented until Member 4's persistence layer is available."""

        raise ToolNotImplementedError(
            "get_rule_results requires the PostgreSQL read layer (Member 4). "
            "Available from the Batch 2 implementation batch."
        )

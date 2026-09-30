"""Relationship-analysis investigation tools (Member 2).

Tool: ``get_related_entities`` (``Agent System Design`` section 7).

Purpose
-------
Finds entities linked to the transaction under investigation: shared device,
shared IP address, shared account, common merchant, location overlap and
temporal clusters. Results are written to ``case_entities`` by the case engine
so the reviewer console can draw the fraud network
(``Database Design`` section 2).

Guardrails
----------
* Read-only and scoped to a single ``transaction_id``.
* The tool reports links that exist in stored data. It does not assert that a
  link is fraudulent; that judgement belongs to the relationship analysis
  capability and is always advisory.
* No graph database, no arbitrary traversal: the implementation is a bounded
  lookup over the indexed ``transactions`` and ``case_entities`` tables
  (``Database Design`` section 8).

Status: interface only.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.agents.tools.base import ToolNotImplementedError
from app.schemas.investigation_result import RelatedEntity

__all__ = ["RelatedEntitiesTool", "RelatedEntitiesToolStub"]


class RelatedEntitiesTool(Protocol):
    """Least-privilege read interface for entity relationships."""

    async def get_related_entities(
        self,
        transaction_id: UUID,
        *,
        limit: int = 50,
    ) -> list[RelatedEntity]:
        """Return entities linked to ``transaction_id``.

        Args:
            transaction_id: Transaction the search starts from.
            limit: Maximum number of linked entities to return. The
                implementation must enforce a bound.

        Returns:
            Linked entities with their relation type and a source reference.

        Raises:
            InvestigationToolError: When the lookup fails.
        """
        ...


class RelatedEntitiesToolStub:
    """Batch 1 stub that refuses to fabricate relationship data."""

    async def get_related_entities(
        self,
        transaction_id: UUID,
        *,
        limit: int = 50,
    ) -> list[RelatedEntity]:
        """Not implemented until Member 4's persistence layer is available."""

        raise ToolNotImplementedError(
            "get_related_entities requires the PostgreSQL read layer (Member 4). "
            "Available from the Batch 2 implementation batch."
        )

"""Case-facing investigation tools (Member 2).

Tools: ``get_prior_cases`` (read) plus the approved write tools the workflow
needs to persist its output (``save_evidence``, ``create_or_update_case``)
(``Agent System Design`` section 7, ``System Design`` addendum "Agent Tooling").

Ownership split
---------------
Member 2 owns the *interface* it calls. The *implementations* are owned by other
members and must not be re-implemented here:

============================  ==========================================
Tool                          Implementation owner
============================  ==========================================
``get_prior_cases``           Member 4 (PostgreSQL read layer)
``save_evidence``             Member 1 (case/evidence service) on top of
                              Member 4's tables
``create_or_update_case``     Member 1 (case service)
============================  ==========================================

``send_notification`` is intentionally absent: notification delivery is
Member 4's responsibility and is triggered by the risk threshold, not by the
agent.

Status: interfaces only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from app.agents.tools.base import ToolNotImplementedError
from app.agents.tools.types import PriorCaseSummary
from app.schemas.investigation_result import EvidenceItem

__all__ = [
    "CaseWriteResult",
    "EvidenceWriter",
    "PriorCasesTool",
    "PriorCasesToolStub",
    "CaseUpdater",
]


class PriorCasesTool(Protocol):
    """Least-privilege read interface for previous fraud cases."""

    async def get_prior_cases(
        self,
        *,
        customer_id: UUID | None = None,
        entity_ref: str | None = None,
        limit: int = 20,
    ) -> list[PriorCaseSummary]:
        """Return previous cases for a customer or a linked entity.

        Args:
            customer_id: Customer scope. Mutually exclusive with ``entity_ref``.
            entity_ref: Linked entity scope (``customer:<id>``, ``device:<id>``,
                ``ip:<addr>`` or ``merchant:<id>``).
            limit: Maximum number of cases to return.

        Returns:
            Previous case summaries with their stored outcomes.

        Raises:
            InvestigationToolError: When both or neither scope is supplied, or
                the lookup fails.
        """
        ...


class PriorCasesToolStub:
    """Batch 1 stub that refuses to fabricate prior cases."""

    async def get_prior_cases(
        self,
        *,
        customer_id: UUID | None = None,
        entity_ref: str | None = None,
        limit: int = 20,
    ) -> list[PriorCaseSummary]:
        """Not implemented until Member 4's persistence layer is available."""

        raise ToolNotImplementedError(
            "get_prior_cases requires the PostgreSQL read layer (Member 4). "
            "Available from the Batch 2 implementation batch."
        )


class EvidenceWriter(Protocol):
    """Approved write tool for persisting investigation evidence."""

    async def save_evidence(
        self,
        *,
        case_id: UUID,
        evidence: list[EvidenceItem],
    ) -> list[UUID]:
        """Persist evidence items and return their stored identifiers.

        Raises:
            InvestigationToolError: When the write fails. Per
                ``Agent System Design`` section 13, a failed write must not be
                reported as a completed step.
        """
        ...


class CaseUpdater(Protocol):
    """Approved write tool for creating or updating the fraud case."""

    async def create_or_update_case(
        self,
        *,
        investigation_id: UUID,
        transaction_id: UUID,
        summary: str,
        recommendation: str,
        related_entity_refs: list[str],
    ) -> UUID:
        """Create or update the case and return its identifier.

        Raises:
            InvestigationToolError: When the write fails.
        """
        ...


@dataclass(frozen=True, slots=True)
class CaseWriteResult:
    """Identifiers returned by Member 1's case/evidence write services."""

    case_id: UUID
    stored_evidence_ids: list[UUID] = field(default_factory=list)
    updated_fields: list[str] = field(default_factory=list)

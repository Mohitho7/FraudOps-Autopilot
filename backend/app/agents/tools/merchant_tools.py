"""Merchant / business-context investigation tools (Member 2).

Tool: ``get_merchant_profile`` (``Agent System Design`` section 7).

Purpose
-------
Supplies the business context the business-context analysis capability needs:
merchant category, expected ticket-size percentile bands, operating hours and
observed distribution. These are what make "unusual amount" contextual instead
of a single global threshold (``System Design`` section 7).

Guardrails
----------
* Read-only and scoped to a single ``merchant_id``.
* Expected bands are stored configuration. The tool never adjusts them and the
  agent never invents a band.
* Business plausibility reasoning belongs to the analysis capability, not here.

Status: interface only.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.agents.tools.base import ToolNotImplementedError
from app.agents.tools.types import MerchantContext

__all__ = ["MerchantProfileTool", "MerchantProfileToolStub"]


class MerchantProfileTool(Protocol):
    """Least-privilege read interface for merchant/business profiles."""

    async def get_merchant_profile(self, merchant_id: UUID) -> MerchantContext:
        """Return the merchant profile for ``merchant_id``.

        Returns:
            Merchant profile with expected percentile bands, operating hours and,
            when available, the observed distribution for the analysed window.

        Raises:
            InvestigationToolError: When the merchant is unknown or the lookup
                fails.
        """
        ...


class MerchantProfileToolStub:
    """Batch 1 stub that refuses to fabricate merchant context."""

    async def get_merchant_profile(self, merchant_id: UUID) -> MerchantContext:
        """Not implemented until Member 4's persistence layer is available."""

        raise ToolNotImplementedError(
            "get_merchant_profile requires the PostgreSQL read layer (Member 4). "
            "Available from the Batch 2 implementation batch."
        )

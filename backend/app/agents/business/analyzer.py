"""Business / merchant context analysis capability (Member 2).

Purpose
-------
Determines whether the transaction is economically plausible **for the
merchant and its category**, instead of applying a global amount threshold
(``Agent System Design`` section 5.2, ``System Design`` section 7)::

    INR 10,00,000 -> gold/jewellery merchant -> potentially plausible
    INR 10,00,000 -> fuel station              -> strongly anomalous

Inputs are the merchant's stored profile (category, expected p50/p95/p99,
operating hours, daily volume baseline) and its observed distribution.

Status
------
Interface only in Batch 1.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.agents.analysis import AnalysisOutcome
from app.agents.graph.state import InvestigationState
from app.agents.tools.types import MerchantContext
from app.schemas.investigation import AnalysisCategory

__all__ = [
    "BUSINESS_ANALYSIS_CATEGORY",
    "BusinessContextAnalyzer",
    "BusinessContextAnalyzerStub",
    "BusinessContextAnalysisRequest",
]

BUSINESS_ANALYSIS_CATEGORY = AnalysisCategory.BUSINESS


class BusinessContextAnalysisRequest(BaseModel):
    """Inputs the business analyzer needs, all of them stored facts."""

    model_config = ConfigDict(extra="forbid")

    merchant: MerchantContext = Field(
        description="Merchant profile loaded through the approved tool."
    )
    transaction_amount: str = Field(
        min_length=1,
        max_length=64,
        description="Transaction amount as a decimal string, exactly as stored.",
    )
    transaction_currency: str = Field(
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
        description="Currency of the transaction under investigation.",
    )
    transaction_local_time: str = Field(
        min_length=1,
        max_length=8,
        description=(
            "Local time of the transaction as ``HH:MM`` in the merchant's "
            "timezone, used for the operating-hours check. The check itself is "
            "deterministic; the model only describes the result."
        ),
    )


class BusinessContextAnalyzer(Protocol):
    """Contract for the business/merchant context analysis capability."""

    async def analyze(
        self,
        state: InvestigationState,
        request: BusinessContextAnalysisRequest,
    ) -> AnalysisOutcome:
        """Compare the amount with the merchant's business expectations.

        Args:
            state: Current investigation state, used for evidence references
                and the audit trail.
            request: Deterministic merchant profile and transaction facts.

        Returns:
            Findings with computed metrics, capability confidence and any
            limitations (for example a missing merchant profile).

        Raises:
            InvestigationToolError: When the analysis cannot be completed.
        """
        ...


class BusinessContextAnalyzerStub:
    """Batch 1 stub: analysis logic lands in a later batch."""

    async def analyze(
        self,
        state: InvestigationState,
        request: BusinessContextAnalysisRequest,
    ) -> AnalysisOutcome:
        """Not implemented in Batch 1."""

        raise NotImplementedError(
            "Business context analysis is implemented in Batch 2. Batch 1 only "
            "defines the contract and the deterministic input types."
        )

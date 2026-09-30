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

import json
from datetime import time
from decimal import Decimal, InvalidOperation
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field

from app.agents.analysis import AnalysisOutcome
from app.agents.graph.state import InvestigationState
from app.agents.tools.types import MerchantContext
from app.schemas.investigation import AnalysisCategory
from app.schemas.investigation_result import InvestigationFinding

__all__ = [
    "BUSINESS_ANALYSIS_CATEGORY",
    "BusinessContextAnalyzer",
    "BusinessContextAnalyzerImpl",
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


class BusinessContextAnalyzerImpl:
    """Deterministic merchant/business context analysis."""

    async def analyze(
        self,
        state: InvestigationState,
        request: BusinessContextAnalysisRequest,
    ) -> AnalysisOutcome:
        merchant = request.merchant
        limitations: list[str] = []
        findings: list[InvestigationFinding] = []

        try:
            amount = Decimal(request.transaction_amount)
        except InvalidOperation:
            limitations.append("Transaction amount is not a valid decimal value.")
            return AnalysisOutcome(
                findings=[],
                confidence=0.0,
                sufficient_evidence=False,
                limitations=limitations,
            )

        if merchant is None:
            limitations.append("Merchant profile is missing; merchant comparison is unavailable.")
            return AnalysisOutcome(
                findings=[],
                confidence=0.0,
                sufficient_evidence=False,
                limitations=limitations,
            )

        def _finding(title: str, summary: str, metrics: dict[str, object]) -> InvestigationFinding:
            payload = json.dumps(
                {"title": title, "summary": summary, "metrics": metrics},
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            return InvestigationFinding(
                finding_id=uuid5(NAMESPACE_URL, payload),
                category=BUSINESS_ANALYSIS_CATEGORY,
                title=title,
                summary=summary,
                confidence=0.9,
                metrics=metrics,
                evidence_refs=[],
            )

        if merchant.expected_p95 is not None and amount > merchant.expected_p95:
            findings.append(
                _finding(
                    "Transaction amount exceeds merchant expected p95",
                    (
                        f"Transaction amount {amount} exceeds the merchant expected p95 "
                        f"of {merchant.expected_p95}."
                    ),
                    {
                        "transaction_amount": str(amount),
                        "merchant_expected_p95": str(merchant.expected_p95),
                    },
                )
            )

        if merchant.expected_p99 is not None and amount > merchant.expected_p99:
            findings.append(
                _finding(
                    "Transaction amount exceeds merchant expected p99",
                    (
                        f"Transaction amount {amount} exceeds the merchant expected p99 "
                        f"of {merchant.expected_p99}."
                    ),
                    {
                        "transaction_amount": str(amount),
                        "merchant_expected_p99": str(merchant.expected_p99),
                    },
                )
            )

        if merchant.observed is not None and merchant.observed.amount_statistics is not None:
            stats = merchant.observed.amount_statistics
            if stats.median is not None and amount > stats.median:
                findings.append(
                    _finding(
                        "Transaction amount exceeds merchant observed median",
                        (
                            f"Transaction amount {amount} is above the merchant observed median "
                            f"of {stats.median}."
                        ),
                        {
                            "transaction_amount": str(amount),
                            "merchant_observed_median": str(stats.median),
                        },
                    )
                )

            if stats.mean is not None and amount > stats.mean:
                findings.append(
                    _finding(
                        "Transaction amount exceeds merchant observed mean",
                        (
                            f"Transaction amount {amount} is above the merchant observed mean "
                            f"of {stats.mean}."
                        ),
                        {
                            "transaction_amount": str(amount),
                            "merchant_observed_mean": str(stats.mean),
                        },
                    )
                )

            if stats.p95 is not None and amount > stats.p95:
                findings.append(
                    _finding(
                        "Transaction amount exceeds merchant observed p95",
                        (
                            f"Transaction amount {amount} exceeds the merchant observed p95 "
                            f"of {stats.p95}."
                        ),
                        {
                            "transaction_amount": str(amount),
                            "merchant_observed_p95": str(stats.p95),
                        },
                    )
                )

            if stats.p99 is not None and amount > stats.p99:
                findings.append(
                    _finding(
                        "Transaction amount exceeds merchant observed p99",
                        (
                            f"Transaction amount {amount} exceeds the merchant observed p99 "
                            f"of {stats.p99}."
                        ),
                        {
                            "transaction_amount": str(amount),
                            "merchant_observed_p99": str(stats.p99),
                        },
                    )
                )

        if merchant.operating_hours is not None:
            try:
                local_time = time.fromisoformat(request.transaction_local_time)
            except ValueError:
                limitations.append(
                    "Transaction local time is not a valid HH:MM value; merchant operating-hours comparison is unavailable."
                )
            else:
                if not merchant.operating_hours.contains(local_time):
                    findings.append(
                        _finding(
                            "Transaction occurred outside merchant operating hours",
                            (
                                f"The transaction time {request.transaction_local_time} is outside the "
                                f"merchant operating window {merchant.operating_hours.opens_at} to "
                                f"{merchant.operating_hours.closes_at}."
                            ),
                            {
                                "transaction_local_time": request.transaction_local_time,
                                "merchant_opens_at": merchant.operating_hours.opens_at.isoformat(),
                                "merchant_closes_at": merchant.operating_hours.closes_at.isoformat(),
                            },
                        )
                    )

        if merchant.daily_volume_baseline is not None and merchant.observed is not None:
            observed_count = merchant.observed.transaction_count
            if observed_count > 0:
                baseline = Decimal(str(merchant.daily_volume_baseline))
                if Decimal(observed_count) > baseline:
                    findings.append(
                        _finding(
                            "Observed transaction volume exceeds merchant daily baseline",
                            (
                                f"The merchant has observed {observed_count} transactions in the analysed "
                                f"window, above the daily baseline of {merchant.daily_volume_baseline}."
                            ),
                            {
                                "merchant_observed_transaction_count": observed_count,
                                "merchant_daily_volume_baseline": str(merchant.daily_volume_baseline),
                            },
                        )
                    )

        if not findings:
            if not any(
                (
                    merchant.expected_p95 is not None,
                    merchant.expected_p99 is not None,
                    merchant.observed is not None,
                    merchant.operating_hours is not None,
                    merchant.daily_volume_baseline is not None,
                )
            ):
                limitations.append(
                    "Merchant context is incomplete; no deterministically supported merchant evidence is available."
                )
            else:
                limitations.append(
                    "The transaction does not exceed the available merchant baselines or operating-hours checks."
                )
            return AnalysisOutcome(
                findings=[],
                confidence=0.0,
                sufficient_evidence=False,
                limitations=limitations,
            )

        return AnalysisOutcome(
            findings=findings,
            confidence=0.9,
            sufficient_evidence=True,
            limitations=limitations,
        )


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


BusinessContextAnalyzer = BusinessContextAnalyzerImpl

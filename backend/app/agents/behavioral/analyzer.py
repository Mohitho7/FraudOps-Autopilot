"""Behavioral analysis capability (Member 2).

Purpose
-------
Determines whether the transaction is abnormal **for this customer**, using
historical patterns (``Agent System Design`` section 5.1):

* typical transaction amount and frequency,
* recent deviation from the customer's own baseline,
* previous fraud/review outcomes,
* recent spending bursts.

Deterministic vs. AI
--------------------
The numbers -- baseline median, amount multiple, transaction count in the
window, burst size -- come from
:class:`~app.agents.tools.types.CustomerHistory`, i.e. from Python and the
database. The language model may only phrase those findings for a reviewer.

Status
------
Interface only in Batch 1.
"""

from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field

from app.agents.analysis import AnalysisOutcome
from app.agents.graph.state import InvestigationState
from app.agents.tools.types import CustomerHistory
from app.schemas.investigation import AnalysisCategory
from app.schemas.investigation_result import InvestigationFinding

__all__ = [
    "BehavioralAnalyzer",
    "BehavioralAnalyzerStub",
    "BehavioralAnalysisRequest",
    "BEHAVIORAL_ANALYSIS_CATEGORY",
]

BEHAVIORAL_ANALYSIS_CATEGORY = AnalysisCategory.BEHAVIORAL


class BehavioralAnalysisRequest(BaseModel):
    """Inputs the behavioral analyzer needs, all of them stored facts."""

    model_config = ConfigDict(extra="forbid")

    history: CustomerHistory = Field(
        description="Customer history loaded through the approved tool."
    )
    transaction_amount: str = Field(
        min_length=1,
        max_length=64,
        description=(
            "Amount of the transaction under investigation as a decimal string, "
            "exactly as stored. Kept as a string so the model cannot re-parse "
            "or alter it."
        ),
    )
    transaction_currency: str = Field(
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
        description="Currency of the transaction under investigation.",
    )


class BehavioralAnalyzer(Protocol):
    """Contract for the behavioral analysis capability."""

    async def analyze(
        self,
        state: InvestigationState,
        request: BehavioralAnalysisRequest,
    ) -> AnalysisOutcome:
        """Compare the transaction against the customer baseline.

        Args:
            state: Current investigation state, used for evidence references
                and the audit trail.
            request: Deterministic customer history and transaction facts.

        Returns:
            Findings with computed metrics, capability confidence and an
            explicit statement of remaining limitations.

        Raises:
            InvestigationToolError: When the analysis cannot be completed.
        """
        ...


class BehavioralAnalyzerImpl:
    """Deterministic behavioral analysis over the customer history baseline."""

    async def analyze(
        self,
        state: InvestigationState,
        request: BehavioralAnalysisRequest,
    ) -> AnalysisOutcome:
        history = request.history
        stats = history.context.amount_statistics
        limitations: list[str] = []
        findings: list[InvestigationFinding] = []

        try:
            amount = Decimal(request.transaction_amount)
        except InvalidOperation:
            limitations.append("Transaction amount is not a valid decimal value.")
            outcome = AnalysisOutcome(
                findings=[],
                confidence=0.0,
                sufficient_evidence=False,
                limitations=limitations,
            )
            state.behavioral_findings = list(outcome.findings)
            return outcome

        if stats is None or stats.sample_size == 0:
            limitations.append(
                "Customer amount statistics are missing; behavioural comparison is unavailable."
            )
            outcome = AnalysisOutcome(
                findings=[],
                confidence=0.0,
                sufficient_evidence=False,
                limitations=limitations,
            )
            state.behavioral_findings = list(outcome.findings)
            return outcome

        if not history.transactions and stats.sample_size == 0:
            limitations.append(
                "Customer history is missing; no behavioural baseline data is available."
            )
            outcome = AnalysisOutcome(
                findings=[],
                confidence=0.0,
                sufficient_evidence=False,
                limitations=limitations,
            )
            state.behavioral_findings = list(outcome.findings)
            return outcome

        if (
            history.context.default_currency is not None
            and request.transaction_currency != history.context.default_currency
        ):
            limitations.append(
                "Transaction currency differs from the customer's default currency; "
                "the amount comparison is deterministic but not directly equivalent."
            )

        def _finding(title: str, summary: str, metric_values: dict[str, object]) -> InvestigationFinding:
            payload = json.dumps(
                {"title": title, "summary": summary, "metrics": metric_values},
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            return InvestigationFinding(
                finding_id=uuid5(NAMESPACE_URL, payload),
                category=BEHAVIORAL_ANALYSIS_CATEGORY,
                title=title,
                summary=summary,
                confidence=0.9,
                metrics=metric_values,
                evidence_refs=[],
            )

        if stats.median is not None and amount > stats.median:
            ratio = (amount / stats.median).quantize(Decimal("0.01")) if stats.median else None
            findings.append(
                _finding(
                    "Transaction amount exceeds customer median",
                    (
                        f"Transaction amount {amount} exceeds the customer's median "
                        f"amount {stats.median}. The amount is {ratio}x the customer median."
                    ),
                    {
                        "transaction_amount": str(amount),
                        "customer_median": str(stats.median),
                        "amount_multiple_of_customer_median": str(ratio) if ratio is not None else None,
                    },
                )
            )

        if stats.mean is not None and amount > stats.mean:
            ratio = (amount / stats.mean).quantize(Decimal("0.01")) if stats.mean else None
            findings.append(
                _finding(
                    "Transaction amount exceeds customer mean",
                    (
                        f"Transaction amount {amount} is above the customer's mean "
                        f"amount {stats.mean}. The amount is {ratio}x the customer mean."
                    ),
                    {
                        "transaction_amount": str(amount),
                        "customer_mean": str(stats.mean),
                        "amount_multiple_of_customer_mean": str(ratio) if ratio is not None else None,
                    },
                )
            )

        if stats.p95 is not None and amount > stats.p95:
            findings.append(
                _finding(
                    "Transaction amount exceeds customer p95",
                    (
                        f"Transaction amount {amount} exceeds the customer's p95 baseline "
                        f"of {stats.p95}."
                    ),
                    {
                        "transaction_amount": str(amount),
                        "customer_p95": str(stats.p95),
                    },
                )
            )

        if stats.p99 is not None and amount > stats.p99:
            findings.append(
                _finding(
                    "Transaction amount exceeds customer p99",
                    (
                        f"Transaction amount {amount} exceeds the customer's p99 baseline "
                        f"of {stats.p99}."
                    ),
                    {
                        "transaction_amount": str(amount),
                        "customer_p99": str(stats.p99),
                    },
                )
            )

        if not findings:
            limitations.append(
                "The available customer history does not show a supported amount anomaly above the baseline."
            )
            outcome = AnalysisOutcome(
                findings=[],
                confidence=0.0,
                sufficient_evidence=False,
                limitations=limitations,
            )
            state.behavioral_findings = list(outcome.findings)
            return outcome

        outcome = AnalysisOutcome(
            findings=findings,
            confidence=0.9,
            sufficient_evidence=True,
            limitations=limitations,
        )
        state.behavioral_findings = list(outcome.findings)
        return outcome


class BehavioralAnalyzerStub:
    """Batch 1 stub: analysis logic lands in a later batch."""

    async def analyze(
        self,
        state: InvestigationState,
        request: BehavioralAnalysisRequest,
    ) -> AnalysisOutcome:
        """Not implemented in Batch 1."""

        raise NotImplementedError(
            "Behavioral analysis is implemented in Batch 2. Batch 1 only "
            "defines the contract and the deterministic input types."
        )


BehavioralAnalyzer = BehavioralAnalyzerImpl

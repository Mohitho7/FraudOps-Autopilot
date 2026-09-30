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

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.agents.analysis import AnalysisOutcome
from app.agents.graph.state import InvestigationState
from app.agents.tools.types import CustomerHistory
from app.schemas.investigation import AnalysisCategory

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

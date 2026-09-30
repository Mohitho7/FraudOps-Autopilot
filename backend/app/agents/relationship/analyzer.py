"""Relationship analysis capability (Member 2).

Purpose
-------
Finds suspicious connections between the transaction and other entities
(``Agent System Design`` section 5.3): shared device, shared IP address, shared
account attributes, common merchant, unusual location overlap and temporal
clustering of related transactions.

The tool layer reports *links that exist in stored data*; this capability judges
how relevant they are. Its output is advisory and is written to
``case_entities`` so Member 3 can render the fraud network.

Status
------
Interface only in Batch 1.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.agents.analysis import AnalysisOutcome
from app.agents.graph.state import InvestigationState
from app.schemas.investigation import AnalysisCategory
from app.schemas.investigation_result import RelatedEntity

__all__ = [
    "RELATIONSHIP_ANALYSIS_CATEGORY",
    "RelatedEntitiesAnalyzer",
    "RelatedEntitiesAnalyzerStub",
    "RelationshipAnalysisRequest",
]

RELATIONSHIP_ANALYSIS_CATEGORY = AnalysisCategory.RELATIONSHIP


class RelationshipAnalysisRequest(BaseModel):
    """Inputs the relationship analyzer needs, all of them stored facts."""

    model_config = ConfigDict(extra="forbid")

    related_entities: list[RelatedEntity] = Field(
        default_factory=list,
        description="Entities discovered through the approved relationship tool.",
    )
    linked_transaction_count: int = Field(
        default=0,
        ge=0,
        description=(
            "Number of additional transactions linked to the same entities. "
            "Computed by the tool layer, never estimated by the model."
        ),
    )
    shared_entity_count: int = Field(
        default=0,
        ge=0,
        description="Number of distinct shared entities (devices, IPs, accounts).",
    )


class RelatedEntitiesAnalyzer(Protocol):
    """Contract for the relationship analysis capability."""

    async def analyze(
        self,
        state: InvestigationState,
        request: RelationshipAnalysisRequest,
    ) -> AnalysisOutcome:
        """Assess the significance of the discovered entity links.

        Args:
            state: Current investigation state, used for evidence references
                and the audit trail.
            request: Deterministic relationship facts from the tool layer.

        Returns:
            Findings with computed counts, capability confidence and any
            limitations.

        Raises:
            InvestigationToolError: When the analysis cannot be completed.
        """
        ...


class RelatedEntitiesAnalyzerStub:
    """Batch 1 stub: analysis logic lands in a later batch."""

    async def analyze(
        self,
        state: InvestigationState,
        request: RelationshipAnalysisRequest,
    ) -> AnalysisOutcome:
        """Not implemented in Batch 1."""

        raise NotImplementedError(
            "Relationship analysis is implemented in Batch 2. Batch 1 only "
            "defines the contract and the deterministic input types."
        )

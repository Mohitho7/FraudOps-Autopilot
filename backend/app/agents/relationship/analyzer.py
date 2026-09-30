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

import json
from collections import Counter
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field

from app.agents.analysis import AnalysisOutcome
from app.agents.graph.state import InvestigationState
from app.schemas.investigation import AnalysisCategory, RelationType
from app.schemas.investigation_result import InvestigationFinding, RelatedEntity

__all__ = [
    "RELATIONSHIP_ANALYSIS_CATEGORY",
    "RelatedEntitiesAnalyzer",
    "RelatedEntitiesAnalyzerImpl",
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


class RelatedEntitiesAnalyzerImpl:
    """Deterministic direct-relationship summaries over supported relation types."""

    async def analyze(
        self,
        state: InvestigationState,
        request: RelationshipAnalysisRequest,
    ) -> AnalysisOutcome:
        related_entities = list(request.related_entities)
        limitations: list[str] = []
        findings: list[InvestigationFinding] = []

        if not related_entities:
            limitations.append(
                "No related entities were supplied; direct relationship evidence is unavailable."
            )
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
                category=RELATIONSHIP_ANALYSIS_CATEGORY,
                title=title,
                summary=summary,
                confidence=0.9,
                metrics=metrics,
                evidence_refs=[],
            )

        counts = Counter(entity.relation_type for entity in related_entities)

        if counts.get(RelationType.SHARED_DEVICE, 0) > 0:
            findings.append(
                _finding(
                    "Shared-device relationships are present",
                    (
                        f"The transaction is linked to {counts[RelationType.SHARED_DEVICE]} "
                        "shared-device relationship(s)."
                    ),
                    {"shared_device_count": counts[RelationType.SHARED_DEVICE]},
                )
            )

        if counts.get(RelationType.SHARED_IP_ADDRESS, 0) > 0:
            findings.append(
                _finding(
                    "Shared IP relationships are present",
                    (
                        f"The transaction is linked to {counts[RelationType.SHARED_IP_ADDRESS]} "
                        "shared-IP relationship(s)."
                    ),
                    {"shared_ip_count": counts[RelationType.SHARED_IP_ADDRESS]},
                )
            )

        if counts.get(RelationType.SHARED_ACCOUNT, 0) > 0:
            findings.append(
                _finding(
                    "Shared-account relationships are present",
                    (
                        f"The transaction is linked to {counts[RelationType.SHARED_ACCOUNT]} "
                        "shared-account relationship(s)."
                    ),
                    {"shared_account_count": counts[RelationType.SHARED_ACCOUNT]},
                )
            )

        if counts.get(RelationType.SHARED_MERCHANT, 0) > 0:
            findings.append(
                _finding(
                    "Shared-merchant relationships are present",
                    (
                        f"The transaction is linked to {counts[RelationType.SHARED_MERCHANT]} "
                        "shared-merchant relationship(s)."
                    ),
                    {"shared_merchant_count": counts[RelationType.SHARED_MERCHANT]},
                )
            )

        if counts.get(RelationType.LINKED_TRANSACTION, 0) > 0:
            findings.append(
                _finding(
                    "Linked-transactions are present",
                    (
                        f"The transaction is linked to {counts[RelationType.LINKED_TRANSACTION]} "
                        "linked-transaction relationship(s)."
                    ),
                    {"linked_transaction_count": counts[RelationType.LINKED_TRANSACTION]},
                )
            )

        if counts.get(RelationType.LOCATION_OVERLAP, 0) > 0:
            findings.append(
                _finding(
                    "Location-overlap relationships are present",
                    (
                        f"The transaction is linked to {counts[RelationType.LOCATION_OVERLAP]} "
                        "location-overlap relationship(s)."
                    ),
                    {"location_overlap_count": counts[RelationType.LOCATION_OVERLAP]},
                )
            )

        if counts.get(RelationType.TEMPORAL_CLUSTER, 0) > 0:
            findings.append(
                _finding(
                    "Temporal-cluster relationships are present",
                    (
                        f"The transaction is linked to {counts[RelationType.TEMPORAL_CLUSTER]} "
                        "temporal-cluster relationship(s)."
                    ),
                    {"temporal_cluster_count": counts[RelationType.TEMPORAL_CLUSTER]},
                )
            )

        if len({entity.related_case_id for entity in related_entities if entity.related_case_id is not None}) > 0:
            findings.append(
                _finding(
                    "Relationship records reference related cases",
                    "At least one direct relationship points to a prior related case.",
                    {"related_case_count": len({entity.related_case_id for entity in related_entities if entity.related_case_id is not None})},
                )
            )

        if request.linked_transaction_count > 0:
            findings.append(
                _finding(
                    "Additional linked transactions are present",
                    (
                        f"The tool layer reported {request.linked_transaction_count} additional linked transaction(s)."
                    ),
                    {"linked_transaction_count": request.linked_transaction_count},
                )
            )

        if request.shared_entity_count > 0 and len({entity.relation_type for entity in related_entities}) > 1:
            findings.append(
                _finding(
                    "Multiple direct relationship types are present",
                    (
                        f"The transaction has {request.shared_entity_count} distinct shared entities across "
                        f"{len({entity.relation_type for entity in related_entities})} relationship types."
                    ),
                    {
                        "shared_entity_count": request.shared_entity_count,
                        "relationship_type_count": len({entity.relation_type for entity in related_entities}),
                    },
                )
            )

        if not findings:
            limitations.append(
                "No deterministic direct relationship evidence exceeded the empty/no-signal baseline."
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


RelatedEntitiesAnalyzer = RelatedEntitiesAnalyzerImpl

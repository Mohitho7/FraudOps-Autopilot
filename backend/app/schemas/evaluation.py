"""
Fraud evaluation aggregate schema and risk classification types.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.rule import RuleResult


class RiskLevel(str, Enum):
    """
    Case-level categorical risk classifications determined by the deterministic Risk Engine.
    Distinct from individual rule severity signals.
    """
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskEvaluationStatus(str, Enum):
    """
    Operational completeness status of risk evaluation.
    """
    COMPLETE = "COMPLETE"              # All configured rules evaluated successfully
    PARTIAL = "PARTIAL"                # Subset of rules evaluated successfully; coverage < 1.0
    NO_VALID_SIGNALS = "NO_VALID_SIGNALS"  # All rules failed with ERROR; no valid risk signal


class FraudEvaluation(BaseModel):
    """
    Evaluation container collecting all rule evaluation outcomes and aggregated risk signals
    for a transaction.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    transaction_id: str = Field(..., min_length=1, description="Reference transaction identifier")
    rule_results: List[RuleResult] = Field(default_factory=list, description="List of rule evaluation results")
    risk_score: Optional[int] = Field(default=None, ge=0, le=100, description="Aggregate normalized risk score (0-100)")
    risk_level: Optional[str] = Field(default=None, description="Categorical case risk level (LOW, MEDIUM, HIGH, CRITICAL)")
    evaluation_status: Optional[str] = Field(
        default=None,
        description="Risk evaluation status: COMPLETE, PARTIAL, or NO_VALID_SIGNALS",
    )
    coverage_ratio: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Proportion of total configured rule weight that successfully evaluated",
    )
    triggered_rules: List[str] = Field(
        default_factory=list,
        description="Rule IDs of rules that triggered an anomaly",
    )
    clean_rules: List[str] = Field(
        default_factory=list,
        description="Rule IDs of rules that evaluated successfully without triggering",
    )
    failed_rules: List[str] = Field(
        default_factory=list,
        description="Rule IDs of rules that failed execution with ERROR status",
    )
    evaluation_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timezone-aware timestamp of when evaluation was conducted",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic and contextual evaluation metadata")

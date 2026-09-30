"""
Fraud rule result and severity schemas.
"""

from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Severity(str, Enum):
    """
    Standard severity classifications for triggered fraud rules.
    """
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RuleExecutionStatus(str, Enum):
    """
    Execution status of a fraud rule evaluation.
    Distinguishes rules that executed successfully from rules that crashed or could not evaluate.
    """
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


class RuleResult(BaseModel):
    """
    Unified result structure returned by every fraud rule evaluation.
    Machine-readable evidence dictionary is required for downstream agent synthesis.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(..., min_length=1, description="Unique identifier of the rule")
    rule_name: str = Field(..., min_length=1, description="Human-readable rule name")
    triggered: bool = Field(..., description="Whether the rule criteria was violated")
    score: int = Field(default=0, ge=0, le=100, description="Deterministic risk contribution score (0-100)")
    severity: Severity = Field(default=Severity.NONE, description="Severity rating of the violation")
    reason: str = Field(default="", description="Human-readable explanation of evaluation outcome")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Structured key/value evidence for agent consumption")
    execution_time_ms: Optional[float] = Field(default=None, ge=0.0, description="Evaluation execution duration in milliseconds")
    status: RuleExecutionStatus = Field(
        default=RuleExecutionStatus.SUCCESS,
        description="Execution outcome status (SUCCESS or ERROR)",
    )

    @field_validator("rule_id", "rule_name")
    @classmethod
    def not_empty_or_whitespace(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field cannot be empty or whitespace only")
        return stripped

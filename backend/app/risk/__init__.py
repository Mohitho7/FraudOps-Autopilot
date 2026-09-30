"""
Risk Scoring & Aggregation Engine package.
Provides deterministic case-level risk synthesis from rule evaluation results.
"""

from app.risk.config import (
    DEFAULT_RULE_WEIGHTS,
    REQUIRED_BATCH_3_RULES,
    RiskConfiguration,
)
from app.risk.engine import RiskEngine
from app.risk.exceptions import (
    DuplicateRuleResultError,
    EmptyRuleResultsError,
    InvalidScoreError,
    RiskConfigurationError,
    RiskEngineError,
    UnknownRuleResultError,
)
from app.risk.helpers import (
    calculate_coverage,
    calculate_weighted_score,
    map_score_to_risk_level,
)
from app.schemas.evaluation import FraudEvaluation, RiskEvaluationStatus, RiskLevel

__all__ = [
    "DEFAULT_RULE_WEIGHTS",
    "DuplicateRuleResultError",
    "EmptyRuleResultsError",
    "FraudEvaluation",
    "InvalidScoreError",
    "REQUIRED_BATCH_3_RULES",
    "RiskConfiguration",
    "RiskConfigurationError",
    "RiskEngine",
    "RiskEngineError",
    "RiskEvaluationStatus",
    "RiskLevel",
    "UnknownRuleResultError",
    "calculate_coverage",
    "calculate_weighted_score",
    "map_score_to_risk_level",
]

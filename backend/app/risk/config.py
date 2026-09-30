"""
Risk configuration and rule weighting models.
Defines heuristic weights and boundary classifications for case-level risk scoring.
"""

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.risk.exceptions import RiskConfigurationError


# Standard heuristic default rule weights for Batch 3 rules.
# NOTE: These values are demonstration/default heuristic weights and are NOT
# claimed to be machine-learned or statistically calibrated from production fraud data.
DEFAULT_RULE_WEIGHTS: Dict[str, Decimal] = {
    "transaction_velocity": Decimal("0.20"),
    "unusual_amount": Decimal("0.25"),
    "impossible_location": Decimal("0.30"),
    "merchant_context": Decimal("0.25"),
}

REQUIRED_BATCH_3_RULES: Set[str] = {
    "transaction_velocity",
    "unusual_amount",
    "impossible_location",
    "merchant_context",
}


class RiskConfiguration(BaseModel):
    """
    Configuration specifying rule weights and categorical risk level boundaries
    for the deterministic RiskEngine.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_weights: Dict[str, Decimal] = Field(
        default_factory=lambda: dict(DEFAULT_RULE_WEIGHTS),
        description="Mapping of rule_id to Decimal weight. Total must sum to 1.00.",
    )
    low_threshold: int = Field(default=39, ge=0, le=100, description="Upper bound for LOW risk (0-39)")
    medium_threshold: int = Field(default=69, ge=0, le=100, description="Upper bound for MEDIUM risk (40-69)")
    high_threshold: int = Field(default=89, ge=0, le=100, description="Upper bound for HIGH risk (70-89)")
    require_all_batch3_rules: bool = Field(
        default=True,
        description="Whether configuration must explicitly define weights for all Batch 3 rules",
    )

    @field_validator("rule_weights", mode="before")
    @classmethod
    def normalize_and_validate_weights(cls, v: Any) -> Dict[str, Decimal]:
        if not isinstance(v, dict):
            raise RiskConfigurationError(f"rule_weights must be a dictionary, got {type(v).__name__}")
        if not v:
            raise RiskConfigurationError("rule_weights cannot be empty")

        converted: Dict[str, Decimal] = {}
        for rule_id, weight in v.items():
            if not isinstance(rule_id, str) or not rule_id.strip():
                raise RiskConfigurationError("rule_id in rule_weights must be a non-empty string")
            rule_id = rule_id.strip()

            try:
                dec_weight = Decimal(str(weight))
            except (InvalidOperation, TypeError, ValueError) as e:
                raise RiskConfigurationError(
                    f"Weight for rule '{rule_id}' must be a valid numeric Decimal, got '{weight}'"
                ) from e

            if dec_weight < Decimal("0.00"):
                raise RiskConfigurationError(
                    f"Weight for rule '{rule_id}' cannot be negative, got {dec_weight}"
                )

            converted[rule_id] = dec_weight

        return converted

    @model_validator(mode="after")
    def validate_totals_and_thresholds(self) -> "RiskConfiguration":
        # 1. Validate required Batch 3 rules
        if self.require_all_batch3_rules:
            missing = REQUIRED_BATCH_3_RULES - set(self.rule_weights.keys())
            if missing:
                raise RiskConfigurationError(
                    f"Configuration is missing required Batch 3 rule weights: {sorted(missing)}"
                )

        # 2. Validate exact sum of weights == 1.00
        total = sum(self.rule_weights.values())
        if total != Decimal("1.00"):
            raise RiskConfigurationError(
                f"Rule weights must sum to exactly 1.00, got {total}"
            )

        # 3. Validate threshold sequence
        if not (self.low_threshold < self.medium_threshold < self.high_threshold):
            raise RiskConfigurationError(
                f"Risk level thresholds must be strictly ascending: "
                f"low ({self.low_threshold}) < medium ({self.medium_threshold}) < high ({self.high_threshold})"
            )

        return self

    @classmethod
    def from_pairs(
        cls,
        pairs: Sequence[Tuple[str, Any]],
        require_all_batch3_rules: bool = True,
        **kwargs: Any,
    ) -> "RiskConfiguration":
        """
        Construct RiskConfiguration from a sequence of (rule_id, weight) pairs.
        Explicitly detects and rejects duplicate rule IDs.
        """
        seen: Set[str] = set()
        weights: Dict[str, Decimal] = {}

        for rule_id, weight in pairs:
            clean_id = rule_id.strip() if isinstance(rule_id, str) else rule_id
            if clean_id in seen:
                raise RiskConfigurationError(f"Duplicate rule ID '{clean_id}' in configuration pairs")
            seen.add(clean_id)
            weights[clean_id] = Decimal(str(weight))

        return cls(
            rule_weights=weights,
            require_all_batch3_rules=require_all_batch3_rules,
            **kwargs,
        )

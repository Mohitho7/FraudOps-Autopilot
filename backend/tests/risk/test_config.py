"""
Unit tests for RiskConfiguration and rule weight validation.
"""

from decimal import Decimal
import pytest

from app.risk.config import DEFAULT_RULE_WEIGHTS, RiskConfiguration
from app.risk.exceptions import RiskConfigurationError


class TestRiskConfiguration:
    def test_default_configuration_is_valid(self):
        config = RiskConfiguration()
        assert sum(config.rule_weights.values()) == Decimal("1.00")
        assert len(config.rule_weights) == 4
        assert config.rule_weights["transaction_velocity"] == Decimal("0.20")
        assert config.rule_weights["unusual_amount"] == Decimal("0.25")
        assert config.rule_weights["impossible_location"] == Decimal("0.30")
        assert config.rule_weights["merchant_context"] == Decimal("0.25")
        assert config.low_threshold == 39
        assert config.medium_threshold == 69
        assert config.high_threshold == 89

    def test_custom_valid_weights(self):
        weights = {
            "transaction_velocity": Decimal("0.25"),
            "unusual_amount": Decimal("0.25"),
            "impossible_location": Decimal("0.25"),
            "merchant_context": Decimal("0.25"),
        }
        config = RiskConfiguration(rule_weights=weights)
        assert config.rule_weights["transaction_velocity"] == Decimal("0.25")
        assert sum(config.rule_weights.values()) == Decimal("1.00")

    def test_negative_weight_rejected(self):
        weights = {
            "transaction_velocity": Decimal("-0.10"),
            "unusual_amount": Decimal("0.35"),
            "impossible_location": Decimal("0.50"),
            "merchant_context": Decimal("0.25"),
        }
        with pytest.raises(RiskConfigurationError, match="cannot be negative"):
            RiskConfiguration(rule_weights=weights)

    def test_missing_batch3_rule_rejected(self):
        # Missing merchant_context
        weights = {
            "transaction_velocity": Decimal("0.30"),
            "unusual_amount": Decimal("0.30"),
            "impossible_location": Decimal("0.40"),
        }
        with pytest.raises(RiskConfigurationError, match="missing required Batch 3 rule weights"):
            RiskConfiguration(rule_weights=weights)

    def test_weights_sum_greater_than_one_rejected(self):
        weights = {
            "transaction_velocity": Decimal("0.30"),
            "unusual_amount": Decimal("0.30"),
            "impossible_location": Decimal("0.30"),
            "merchant_context": Decimal("0.30"),  # Total = 1.20
        }
        with pytest.raises(RiskConfigurationError, match="must sum to exactly 1.00"):
            RiskConfiguration(rule_weights=weights)

    def test_weights_sum_less_than_one_rejected(self):
        weights = {
            "transaction_velocity": Decimal("0.20"),
            "unusual_amount": Decimal("0.20"),
            "impossible_location": Decimal("0.20"),
            "merchant_context": Decimal("0.20"),  # Total = 0.80
        }
        with pytest.raises(RiskConfigurationError, match="must sum to exactly 1.00"):
            RiskConfiguration(rule_weights=weights)

    def test_non_dict_rule_weights_rejected(self):
        with pytest.raises(RiskConfigurationError, match="must be a dictionary"):
            RiskConfiguration(rule_weights="invalid_weights")

    def test_empty_rule_weights_rejected(self):
        with pytest.raises(RiskConfigurationError, match="cannot be empty"):
            RiskConfiguration(rule_weights={})

    def test_invalid_numeric_weight_rejected(self):
        weights = {
            "transaction_velocity": "not_a_number",
            "unusual_amount": Decimal("0.25"),
            "impossible_location": Decimal("0.30"),
            "merchant_context": Decimal("0.25"),
        }
        with pytest.raises(RiskConfigurationError, match="must be a valid numeric Decimal"):
            RiskConfiguration(rule_weights=weights)

    def test_from_pairs_detects_duplicate_rule_id(self):
        pairs = [
            ("transaction_velocity", Decimal("0.10")),
            ("transaction_velocity", Decimal("0.10")),
            ("unusual_amount", Decimal("0.25")),
            ("impossible_location", Decimal("0.30")),
            ("merchant_context", Decimal("0.25")),
        ]
        with pytest.raises(RiskConfigurationError, match="Duplicate rule ID 'transaction_velocity'"):
            RiskConfiguration.from_pairs(pairs)

    def test_invalid_threshold_order_rejected(self):
        with pytest.raises(RiskConfigurationError, match="strictly ascending"):
            RiskConfiguration(low_threshold=70, medium_threshold=50, high_threshold=90)

    # -------------------------------------------------------------------------
    # F-02: Custom Configuration Flexibility (require_all_batch3_rules=False)
    # -------------------------------------------------------------------------
    def test_custom_mode_accepts_valid_two_rule_subset(self):
        """
        Finding F-02: When require_all_batch3_rules=False, a subset of rules is permitted
        as long as weights are valid Decimals summing to 1.00.
        """
        weights = {
            "transaction_velocity": Decimal("0.50"),
            "merchant_context": Decimal("0.50"),
        }
        config = RiskConfiguration(rule_weights=weights, require_all_batch3_rules=False)
        assert config.require_all_batch3_rules is False
        assert len(config.rule_weights) == 2
        assert config.rule_weights["transaction_velocity"] == Decimal("0.50")
        assert config.rule_weights["merchant_context"] == Decimal("0.50")
        assert sum(config.rule_weights.values()) == Decimal("1.00")

    def test_custom_mode_rejects_negative_weight(self):
        """
        Finding F-02: Custom mode still strictly rejects negative weights.
        """
        weights = {
            "transaction_velocity": Decimal("-0.10"),
            "merchant_context": Decimal("1.10"),
        }
        with pytest.raises(RiskConfigurationError, match="cannot be negative"):
            RiskConfiguration(rule_weights=weights, require_all_batch3_rules=False)

    def test_custom_mode_rejects_invalid_total_weight(self):
        """
        Finding F-02: Custom mode still strictly enforces that weights sum to exactly 1.00.
        """
        weights = {
            "transaction_velocity": Decimal("0.40"),
            "merchant_context": Decimal("0.50"),  # Total = 0.90
        }
        with pytest.raises(RiskConfigurationError, match="must sum to exactly 1.00"):
            RiskConfiguration(rule_weights=weights, require_all_batch3_rules=False)

    def test_custom_mode_rejects_non_numeric_weight(self):
        """
        Finding F-02: Custom mode still enforces valid Decimal weight values.
        """
        weights = {
            "transaction_velocity": "not_a_valid_number",
            "merchant_context": Decimal("0.50"),
        }
        with pytest.raises(RiskConfigurationError, match="must be a valid numeric Decimal"):
            RiskConfiguration(rule_weights=weights, require_all_batch3_rules=False)

    def test_custom_mode_from_pairs_rejects_duplicate_rule_id(self):
        """
        Finding F-02: Constructing from pairs with custom mode still rejects duplicate rule IDs.
        """
        pairs = [
            ("custom_rule_a", Decimal("0.50")),
            ("custom_rule_a", Decimal("0.50")),
        ]
        with pytest.raises(RiskConfigurationError, match="Duplicate rule ID 'custom_rule_a'"):
            RiskConfiguration.from_pairs(pairs, require_all_batch3_rules=False)

    def test_custom_mode_does_not_modify_default_weights_or_state(self):
        """
        Finding F-02: Creating a custom configuration does not modify DEFAULT_RULE_WEIGHTS
        or standard default RiskConfiguration instances.
        """
        custom_weights = {
            "transaction_velocity": Decimal("0.60"),
            "merchant_context": Decimal("0.40"),
        }
        custom_config = RiskConfiguration(rule_weights=custom_weights, require_all_batch3_rules=False)

        # Standard default remains intact
        default_config = RiskConfiguration()
        assert default_config.require_all_batch3_rules is True
        assert len(default_config.rule_weights) == 4
        assert default_config.rule_weights["transaction_velocity"] == Decimal("0.20")
        assert DEFAULT_RULE_WEIGHTS["transaction_velocity"] == Decimal("0.20")

    def test_risk_engine_operates_with_custom_configuration(self):
        """
        Finding F-02: RiskEngine correctly processes evaluations when configured
        with a valid custom RiskConfiguration subset.
        """
        from app.risk.engine import RiskEngine
        from app.schemas.rule import RuleResult, Severity, RuleExecutionStatus

        custom_weights = {
            "transaction_velocity": Decimal("0.60"),
            "merchant_context": Decimal("0.40"),
        }
        config = RiskConfiguration(rule_weights=custom_weights, require_all_batch3_rules=False)
        engine = RiskEngine(config=config)

        results = [
            RuleResult(
                rule_id="transaction_velocity",
                rule_name="Velocity",
                triggered=True,
                score=50,
                severity=Severity.MEDIUM,
                status=RuleExecutionStatus.SUCCESS,
            ),
            RuleResult(
                rule_id="merchant_context",
                rule_name="Merchant Context",
                triggered=False,
                score=0,
                severity=Severity.NONE,
                status=RuleExecutionStatus.SUCCESS,
            ),
        ]

        evaluation = engine.evaluate(results, transaction_id="tx_custom_cfg")
        # 50 * 0.60 + 0 * 0.40 = 30.0 -> score = 30
        assert evaluation.risk_score == 30
        assert evaluation.coverage_ratio == 1.0
        assert evaluation.evaluation_status == "COMPLETE"
        assert evaluation.triggered_rules == ["transaction_velocity"]
        assert evaluation.clean_rules == ["merchant_context"]


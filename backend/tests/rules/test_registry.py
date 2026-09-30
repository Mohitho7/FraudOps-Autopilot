"""
Tests for RuleRegistry.
"""

import pytest

from app.rules.exceptions import DuplicateRuleError, InvalidRuleError, RuleNotFoundError
from app.rules.registry import RuleRegistry
from tests.rules.doubles import DummyCleanRule, DummyTriggeredRule


def test_register_and_retrieve_rule():
    registry = RuleRegistry()
    rule = DummyTriggeredRule()

    registry.register(rule)
    assert len(registry) == 1
    assert "test_dummy_triggered" in registry

    retrieved = registry.get("test_dummy_triggered")
    assert retrieved is rule

    # get_or_raise
    assert registry.get_or_raise("test_dummy_triggered") is rule


def test_get_nonexistent_rule_returns_none_or_raises():
    registry = RuleRegistry()
    assert registry.get("nonexistent") is None

    with pytest.raises(RuleNotFoundError):
        registry.get_or_raise("nonexistent")


def test_duplicate_rule_registration_raises():
    registry = RuleRegistry()
    rule1 = DummyTriggeredRule()
    rule2 = DummyTriggeredRule()

    registry.register(rule1)
    with pytest.raises(DuplicateRuleError):
        registry.register(rule2)


def test_invalid_rule_registration_raises():
    registry = RuleRegistry()

    # Not a FraudRule instance
    with pytest.raises(InvalidRuleError):
        registry.register("not_a_rule")  # type: ignore

    # Lacks a valid rule_id
    class NoIdRule(DummyCleanRule):
        rule_id = ""

    with pytest.raises(InvalidRuleError):
        registry.register(NoIdRule())


def test_unregister_and_remove_rule():
    registry = RuleRegistry()
    rule = DummyCleanRule()
    registry.register(rule)

    unregistered = registry.unregister(rule.rule_id)
    assert unregistered is rule
    assert len(registry) == 0
    assert rule.rule_id not in registry

    # Unregistering non-existent rule raises RuleNotFoundError
    with pytest.raises(RuleNotFoundError):
        registry.unregister("already_removed")


def test_get_all_and_get_enabled():
    registry = RuleRegistry()
    rule_enabled = DummyTriggeredRule(is_enabled=True)
    rule_disabled = DummyCleanRule()
    rule_disabled.is_enabled = False

    registry.register(rule_enabled)
    registry.register(rule_disabled)

    assert len(registry.get_all()) == 2
    enabled_rules = registry.get_enabled()
    assert len(enabled_rules) == 1
    assert enabled_rules[0] is rule_enabled


def test_clear_registry():
    registry = RuleRegistry()
    registry.register(DummyTriggeredRule())
    registry.register(DummyCleanRule())
    assert len(registry) == 2

    registry.clear()
    assert len(registry) == 0

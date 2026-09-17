"""Tests for the documented fail-open contract in lwb_core/config.py."""

from lwb_core.config import Policy, RuleMode, load_policy_dict


def test_none_policy_is_all_off_and_degraded():
    policy = load_policy_dict(None)
    assert isinstance(policy, Policy)
    assert policy.degraded is True
    assert policy.rule_config("lwb_version").mode is RuleMode.OFF


def test_missing_rules_key_is_degraded_and_empty():
    policy = load_policy_dict({"not_rules": {}})
    assert policy.degraded is True
    assert policy.rules == {}


def test_unknown_rule_mode_string_coerces_to_off():
    policy = load_policy_dict({"rules": {"lwb_version": {"mode": "block-everything"}}})
    assert policy.rule_config("lwb_version").mode is RuleMode.OFF


def test_unconfigured_rule_defaults_to_off_without_being_degraded():
    policy = load_policy_dict({"rules": {}})
    assert policy.degraded is False
    assert policy.rule_config("lwb_version").mode is RuleMode.OFF


def test_valid_policy_round_trips_mode_and_options():
    policy = load_policy_dict(
        {"rules": {"lwb_version": {"mode": "deny", "options": {"x": 1}}}}
    )
    assert policy.degraded is False
    cfg = policy.rule_config("lwb_version")
    assert cfg.mode is RuleMode.DENY
    assert cfg.options == {"x": 1}

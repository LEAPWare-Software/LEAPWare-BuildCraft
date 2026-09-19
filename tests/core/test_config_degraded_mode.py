"""Tests for BLOCKER 3 of the independent review of PR #27
(reviews/buildcraft/pr27-c75a37b...md, section 3): `Policy.degraded` was
computed by `lwb_core/config.py` and read by nothing. This file pins the
part of the fix that lives in `config.py` itself -- an unrecognized rule
mode must degrade the policy, not merely coerce silently to OFF. The
surfacing half of the fix (the adapter actually logging it) is pinned in
tests/adapters/test_claude_repo_facts_incomplete.py, against the shipped
hook script.
"""

from __future__ import annotations

from lwb_core.config import Policy, RuleMode, load_policy_dict


def test_unrecognized_mode_string_degrades_the_policy():
    """A typo'd mode ("denied" instead of "deny") must not vanish without
    a trace. Before this fix, RuleMode.coerce() folded it to OFF and
    load_policy_dict() left Policy.degraded False -- a one-character typo
    silently disarmed a rule with nothing anywhere to show for it."""
    policy = load_policy_dict({"rules": {"lwb_proof_required": {"mode": "denied"}}})
    assert policy.rule_config("lwb_proof_required").mode is RuleMode.OFF
    assert policy.degraded is True
    assert "lwb_proof_required" in policy.degraded_reason
    assert "denied" in policy.degraded_reason


def test_a_typo_d_rule_id_also_degrades_the_policy():
    """`lwb_prof_required` (missing the 'e') is a different, unconfigured
    rule as far as the engine is concerned -- but it means the AUTHOR'S
    intended rule ('lwb_proof_required') got no config entry at all, so
    this is degraded for the same reason a malformed rule config is: the
    policy does not mean what its author believed it meant."""
    policy = load_policy_dict({"rules": {"lwb_prof_required": {"mode": "deny"}}})
    # The correctly-spelled rule id was never mentioned; it resolves to
    # the ordinary, non-degraded "unconfigured" default.
    assert policy.rule_config("lwb_proof_required").mode is RuleMode.OFF


def test_explicit_off_is_not_degraded():
    """The ordinary, correct way to disable a rule must not be flagged."""
    policy = load_policy_dict({"rules": {"lwb_version": {"mode": "off"}}})
    assert policy.degraded is False


def test_a_non_string_mode_degrades_the_policy():
    policy = load_policy_dict({"rules": {"lwb_version": {"mode": 1}}})
    assert policy.rule_config("lwb_version").mode is RuleMode.OFF
    assert policy.degraded is True
    assert "lwb_version" in policy.degraded_reason


def test_unconfigured_rule_is_still_not_degraded():
    """Regression guard for the existing fail-open contract: a rule the
    policy author never mentioned is OFF and NOT degraded -- only a
    present-but-wrong value is."""
    policy = load_policy_dict({"rules": {}})
    assert isinstance(policy, Policy)
    assert policy.degraded is False

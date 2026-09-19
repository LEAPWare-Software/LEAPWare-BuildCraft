"""Test for MEDIUM 7 of the independent review of PR #27
(reviews/buildcraft/pr27-c75a37b...md, section 7): `render_decision`
dropped every warning on a deny. `decision.warnings` reached the ledger
but never `permissionDecisionReason`, so a warning that fired alongside a
deny was invisible to the user even though the engine had already
collected it.
"""

from __future__ import annotations

from adapters.claude.hook_io import render_decision
from lwb_core.engine import Decision, Finding
from lwb_core.config import RuleMode


def test_a_deny_still_surfaces_warnings_from_rules_that_fired_before_it():
    decision = Decision(
        permit=False,
        deny_reason="publish blocked",
        warnings=["lwb 0.1.0: reporting only, no policy enforced yet"],
        findings=[
            Finding(rule_id="lwb_version", mode=RuleMode.WARN, reason="lwb 0.1.0: reporting only, no policy enforced yet"),
            Finding(rule_id="lwb_proof_required", mode=RuleMode.DENY, reason="publish blocked"),
        ],
    )
    output = render_decision(decision)
    reason = output["hookSpecificOutput"]["permissionDecisionReason"]
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "publish blocked" in reason
    assert "lwb 0.1.0: reporting only" in reason


def test_a_deny_with_no_warnings_is_unchanged():
    decision = Decision(permit=False, deny_reason="publish blocked", warnings=[], findings=[])
    output = render_decision(decision)
    assert output["hookSpecificOutput"]["permissionDecisionReason"] == "publish blocked"

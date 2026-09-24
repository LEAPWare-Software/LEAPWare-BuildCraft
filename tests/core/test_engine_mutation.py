"""Mutation-style test: proves the rule registry is load-bearing.

This does not edit rules/__init__.py on disk. Instead it monkeypatches
`lwb_core.engine.RULES` to an empty list — the same effect as removing
`lwb_version` from the registry — and asserts its finding disappears. If
someone ever made `evaluate()` report a finding unconditionally (e.g.
hardcoded, ignoring the registry), this test would still pass with the real
registry but FAIL here, since an empty registry would then still produce a
finding.

`lwb_proof_coverage` and `lwb_proof_integrity` (Phase 1 item 1.1) get the
same treatment further down: a real `RepoFacts` fixture that gives each of
them something to say, evaluated against the REAL registry first (proving
they are actually wired into `RULES`), then again against a registry with
that one rule filtered out (proving the registry, not a hardcoded call, is
what produces the finding). `lwb_no_unauthorised_destructive_action`
(Phase 1 item 1.6) gets the same treatment further down still.
"""

import lwb_core.engine as engine_module
from lwb_core.config import Policy, RuleConfig, RuleMode
from lwb_core.events import Event, RepoFacts
from lwb_core.rules import RULES as REAL_RULES


def _dispatch_event() -> Event:
    return Event(
        hook_event="PreToolUse",
        tool_name="Agent",
        tool_input={"prompt": "Fix the bug"},
        prompt="Fix the bug",
    )


def test_real_registry_reports_the_walking_skeleton_case():
    policy = Policy(rules={"lwb_version": RuleConfig(mode=RuleMode.WARN)})
    decision = engine_module.evaluate(_dispatch_event(), policy)
    assert decision.permit is True
    assert decision.findings, "expected lwb_version's finding to be recorded"


def test_removing_the_rule_from_the_registry_removes_its_finding(monkeypatch):
    monkeypatch.setattr(engine_module, "RULES", [])
    policy = Policy(rules={"lwb_version": RuleConfig(mode=RuleMode.WARN)})
    decision = engine_module.evaluate(_dispatch_event(), policy)
    assert decision.permit is True
    assert decision.findings == []


# --------------------------------------------------------------------
# lwb_proof_coverage and lwb_proof_integrity (Phase 1 item 1.1): the same
# load-bearing proof `lwb_version` gets above, extended to both new rules.
# --------------------------------------------------------------------


def _publish_event() -> Event:
    repo = RepoFacts(
        branch="main",
        proof_ids=(),
        landed_unproven=("abc123def456 (#41)",),
        matched_proof_self_certified=True,
        matched_proof_has_failed_command=False,
    )
    return Event(
        hook_event="PreToolUse",
        tool_name="Bash",
        tool_input={"command": "git push"},
        repo=repo,
    )


def test_real_registry_reports_lwb_proof_coverage():
    policy = Policy(rules={"lwb_proof_coverage": RuleConfig(mode=RuleMode.WARN)})
    decision = engine_module.evaluate(_publish_event(), policy)
    assert decision.permit is True
    assert [f.rule_id for f in decision.findings] == ["lwb_proof_coverage"]


def test_removing_lwb_proof_coverage_from_the_registry_removes_its_finding(monkeypatch):
    monkeypatch.setattr(
        engine_module, "RULES", [r for r in REAL_RULES if r.rule_id != "lwb_proof_coverage"]
    )
    policy = Policy(rules={"lwb_proof_coverage": RuleConfig(mode=RuleMode.WARN)})
    decision = engine_module.evaluate(_publish_event(), policy)
    assert decision.permit is True
    assert decision.findings == []


def test_real_registry_reports_lwb_proof_integrity():
    policy = Policy(rules={"lwb_proof_integrity": RuleConfig(mode=RuleMode.WARN)})
    decision = engine_module.evaluate(_publish_event(), policy)
    assert decision.permit is True
    assert [f.rule_id for f in decision.findings] == ["lwb_proof_integrity"]


def test_removing_lwb_proof_integrity_from_the_registry_removes_its_finding(monkeypatch):
    monkeypatch.setattr(
        engine_module, "RULES", [r for r in REAL_RULES if r.rule_id != "lwb_proof_integrity"]
    )
    policy = Policy(rules={"lwb_proof_integrity": RuleConfig(mode=RuleMode.WARN)})
    decision = engine_module.evaluate(_publish_event(), policy)
    assert decision.permit is True
    assert decision.findings == []


# --------------------------------------------------------------------
# lwb_no_unauthorised_destructive_action (Phase 1 item 1.6): same
# load-bearing proof, for the plan's second deny-capable rule (D9).
# --------------------------------------------------------------------


def _force_push_event() -> Event:
    repo = RepoFacts(branch="main", proof_ids=())
    return Event(
        hook_event="PreToolUse",
        tool_name="Bash",
        tool_input={"command": "git push -f origin main"},
        repo=repo,
    )


def test_real_registry_reports_lwb_no_unauthorised_destructive_action():
    policy = Policy(
        rules={"lwb_no_unauthorised_destructive_action": RuleConfig(mode=RuleMode.WARN)}
    )
    decision = engine_module.evaluate(_force_push_event(), policy)
    assert decision.permit is True
    assert [f.rule_id for f in decision.findings] == [
        "lwb_no_unauthorised_destructive_action"
    ]


def test_removing_lwb_no_unauthorised_destructive_action_from_the_registry_removes_its_finding(
    monkeypatch,
):
    monkeypatch.setattr(
        engine_module,
        "RULES",
        [r for r in REAL_RULES if r.rule_id != "lwb_no_unauthorised_destructive_action"],
    )
    policy = Policy(
        rules={"lwb_no_unauthorised_destructive_action": RuleConfig(mode=RuleMode.WARN)}
    )
    decision = engine_module.evaluate(_force_push_event(), policy)
    assert decision.permit is True
    assert decision.findings == []

"""Mutation-style test: proves the rule registry is load-bearing.

This does not edit rules/__init__.py on disk. Instead it monkeypatches
`lwb_core.engine.RULES` to an empty list — the same effect as removing
`lwb_version` from the registry — and asserts its finding disappears. If
someone ever made `evaluate()` report a finding unconditionally (e.g.
hardcoded, ignoring the registry), this test would still pass with the real
registry but FAIL here, since an empty registry would then still produce a
finding.
"""

import lwb_core.engine as engine_module
from lwb_core.config import Policy, RuleConfig, RuleMode
from lwb_core.events import Event


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

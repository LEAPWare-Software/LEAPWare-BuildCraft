"""Tests for adapters/claude/hook_io.py against the sanitized fixtures."""

import json
from pathlib import Path

from adapters.claude.hook_io import parse_event, render_decision
from lwb_core.config import Policy, RuleConfig, RuleMode
from lwb_core.engine import evaluate

FIXTURES = Path(__file__).parent / "fixtures" / "claude"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_event_extracts_prompt_from_agent_dispatch():
    event = parse_event(_load("pretooluse_agent_no_budget.json"))
    assert event.hook_event == "PreToolUse"
    assert event.tool_name == "Agent"
    assert event.prompt and "example_module" in event.prompt


def test_parse_event_preserves_unknown_fields_in_extra():
    raw = _load("pretooluse_agent_no_budget.json")
    raw["cwd"] = "/sanitized/path"
    event = parse_event(raw)
    assert event.extra.get("cwd") == "/sanitized/path"


def test_parse_event_non_agent_tool_has_no_prompt():
    event = parse_event(_load("pretooluse_read.json"))
    assert event.tool_name == "Read"
    assert event.prompt is None


def test_render_decision_never_denies_even_when_misconfigured_to_deny():
    """lwb_version is a no-op: it always allows, even under a policy that
    (incorrectly) sets it to "deny"."""
    policy = Policy(rules={"lwb_version": RuleConfig(mode=RuleMode.DENY)})
    event = parse_event(_load("pretooluse_agent_no_budget.json"))
    decision = evaluate(event, policy)
    output = render_decision(decision)
    assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert "lwb" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_render_decision_allow_shape_under_shipped_default():
    policy = Policy(rules={"lwb_version": RuleConfig(mode=RuleMode.WARN)})
    event = parse_event(_load("pretooluse_agent_with_budget.json"))
    decision = evaluate(event, policy)
    output = render_decision(decision)
    assert output["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_render_decision_allow_with_version_report():
    policy = Policy(rules={"lwb_version": RuleConfig(mode=RuleMode.WARN)})
    event = parse_event(_load("pretooluse_agent_no_budget.json"))
    decision = evaluate(event, policy)
    output = render_decision(decision)
    assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert "lwb" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_lifecycle_hooks_with_no_tool_are_parsed_without_error():
    for name in ("subagent_stop.json", "stop.json"):
        event = parse_event(_load(name))
        assert event.tool_name is None
        assert event.prompt is None

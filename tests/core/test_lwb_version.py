"""Unit tests for the lwb_version rule and its engine wiring."""

from lwb_core import __version__
from lwb_core.config import Policy, RuleConfig, RuleMode
from lwb_core.engine import evaluate
from lwb_core.events import Event
from lwb_core.rules import lwb_version


def _agent_event(prompt: str = "Fix the bug") -> Event:
    return Event(
        hook_event="PreToolUse",
        tool_name="Agent",
        tool_input={"prompt": prompt},
        prompt=prompt,
    )


def test_fires_on_every_event_regardless_of_shape():
    for event in (
        _agent_event(),
        Event(hook_event="PreToolUse", tool_name="Read", tool_input={}),
        Event(hook_event="Stop"),
        Event(hook_event="SubagentStop"),
    ):
        finding = lwb_version.evaluate(event, RuleConfig(mode=RuleMode.WARN))
        assert finding is not None
        assert __version__ in finding.reason


def test_finding_is_always_warn_even_when_configured_to_deny():
    """The no-op guarantee: this rule never denies, even under a
    misconfigured policy that sets it to "deny"."""
    finding = lwb_version.evaluate(_agent_event(), RuleConfig(mode=RuleMode.DENY))
    assert finding is not None
    assert finding.mode is RuleMode.WARN


def test_engine_allows_walking_skeleton_dispatch_under_shipped_mode():
    policy = Policy(rules={"lwb_version": RuleConfig(mode=RuleMode.WARN)})
    decision = evaluate(_agent_event(), policy)
    assert decision.permit is True
    assert decision.warnings, "expected the version report to be recorded"


def test_engine_still_permits_even_if_misconfigured_to_deny():
    policy = Policy(rules={"lwb_version": RuleConfig(mode=RuleMode.DENY)})
    decision = evaluate(_agent_event(), policy)
    assert decision.permit is True, "lwb_version must never deny, regardless of policy mode"


def test_off_mode_produces_no_finding():
    policy = Policy(rules={"lwb_version": RuleConfig(mode=RuleMode.OFF)})
    decision = evaluate(_agent_event(), policy)
    assert decision.permit is True
    assert decision.findings == []

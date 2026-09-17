"""Conformance test: the same neutral event yields the same Decision through
both adapters' `parse_event`, for every hook shape Codex's parser also
supports — and, since both adapters now render an enforcing hook decision,
the same rendered `hookSpecificOutput` JSON through both `render_decision`s
too.

This is the test the walking-skeleton pipeline is built to satisfy: buildcraft's
engine must not silently branch on which host produced the event, and a
DENY on one host must render byte-for-byte the same shape on the other.
Where Codex's fixture set has no equivalent of a Claude-only field (e.g.
`transcript_path`), the test only asserts on the fields both adapters
populate — `hook_event`, `tool_name`, `prompt` — since those are the only
fields `lwb_version` (or any rule in the registry) reads.
"""

import json
from pathlib import Path

from adapters.claude.hook_io import parse_event as claude_parse_event
from adapters.claude.hook_io import render_decision as claude_render_decision
from adapters.codex.hook_io import parse_event as codex_parse_event
from adapters.codex.hook_io import render_decision as codex_render_decision
from lwb_core.config import Policy, RuleConfig, RuleMode
from lwb_core.engine import evaluate

CLAUDE_FIXTURES = Path(__file__).parent.parent / "adapters" / "fixtures" / "claude"
CODEX_FIXTURES = Path(__file__).parent.parent / "adapters" / "fixtures" / "codex"

# (claude fixture name, codex fixture name) pairs describing the SAME
# logical event in each host's native shape.
PAIRED_FIXTURES = [
    ("pretooluse_agent_no_budget.json", "pretooluse_agent_no_budget.json"),
    ("pretooluse_agent_with_budget.json", "pretooluse_agent_with_budget.json"),
]

DENY_POLICY = Policy(rules={"lwb_version": RuleConfig(mode=RuleMode.DENY)})  # lwb_version ignores this and still allows


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_paired_fixtures_produce_identical_decisions():
    for claude_name, codex_name in PAIRED_FIXTURES:
        claude_event = claude_parse_event(_load(CLAUDE_FIXTURES / claude_name))
        codex_event = codex_parse_event(_load(CODEX_FIXTURES / codex_name))

        assert claude_event.hook_event == codex_event.hook_event
        assert claude_event.tool_name == codex_event.tool_name
        assert claude_event.prompt == codex_event.prompt

        claude_decision = evaluate(claude_event, DENY_POLICY)
        codex_decision = evaluate(codex_event, DENY_POLICY)

        assert claude_decision.permit == codex_decision.permit
        assert claude_decision.deny_reason == codex_decision.deny_reason
        assert [f.rule_id for f in claude_decision.findings] == [
            f.rule_id for f in codex_decision.findings
        ]

        # Both hooks now enforce; the rendered hookSpecificOutput JSON must
        # match exactly, not just the underlying Decision.
        assert claude_render_decision(claude_decision) == codex_render_decision(codex_decision)


def test_warn_mode_decision_renders_identically_both_adapters():
    """A WARN (not DENY) finding still renders the same allow+reason shape."""
    warn_policy = Policy(rules={"lwb_version": RuleConfig(mode=RuleMode.WARN)})
    claude_event = claude_parse_event(_load(CLAUDE_FIXTURES / "pretooluse_agent_no_budget.json"))
    codex_event = codex_parse_event(_load(CODEX_FIXTURES / "pretooluse_agent_no_budget.json"))

    claude_decision = evaluate(claude_event, warn_policy)
    codex_decision = evaluate(codex_event, warn_policy)

    assert claude_render_decision(claude_decision) == codex_render_decision(codex_decision)

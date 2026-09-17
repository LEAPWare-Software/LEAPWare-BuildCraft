"""Codex adapter: translate Codex's hook JSON <-> lwb_core's neutral shapes.

Superseded 2026-09-17 (owner ruling: "Codex supports hooks, so full
enforcement"). The prior reporting-only decision rested on recon that could
not confirm a documented plugin-bundled-hooks manifest shape; a direct fetch
of the canonical docs page confirmed one. Codex's `PreToolUse` hook uses the
SAME `hookSpecificOutput.permissionDecision` (`"allow"` / `"deny"`) shape
Claude Code's does, so `render_decision` below is a straight port of
`adapters/claude/hook_io.py`'s. See docs/install-codex.md for the full
citation trail and quoted source text; sources:
  - https://developers.openai.com/codex/hooks (redirects to
    https://learn.chatgpt.com/docs/hooks) — hook event/handler/stdin/stdout
    shapes, plugin-bundled hooks via `plugin.json`'s `hooks` field.
  - https://developers.openai.com/codex/plugins (redirects to
    https://learn.chatgpt.com/docs/plugins) — plugin manifest shape.

This module does the I/O-adjacent translation ONLY, same split as the
Claude adapter: see `plugins/codex/lwb/bin/lwb_hook.py` for the thin script
that reads stdin / writes stdout / sets the exit code.

`render_report` and the lwb-report skill are kept: a human-readable report
is still useful even though the hook itself now enforces mechanically.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from lwb_core.config import Policy, load_policy_dict
from lwb_core.engine import Decision
from lwb_core.events import Event

#: Codex's env var naming the installed plugin's own root directory, used in
#: hooks.json command args (e.g. "${PLUGIN_ROOT}/bin/lwb_hook.py"). Per the
#: fetched hooks doc: "Plugin hooks receive environment variables: PLUGIN_ROOT
#: — installed plugin directory, PLUGIN_DATA — writable plugin data directory."
PLUGIN_ROOT_VAR = "PLUGIN_ROOT"
#: Writable per-plugin data directory, used for the ledger path (mirrors
#: Claude's CLAUDE_PLUGIN_DATA in plugins/claude/lwb/bin/lwb_hook.py).
PLUGIN_DATA_VAR = "PLUGIN_DATA"


def parse_event(raw: Mapping[str, Any]) -> Event:
    """Build a neutral `Event` from a Codex-shaped event dict.

    Codex does not ship a documented hook input schema this project could
    cite (see module docstring), so this parser accepts the same neutral
    field names the test fixtures under tests/adapters/fixtures/codex/ use:
    `hook_event_name`, `tool_name`, `tool_input`, `session_id`. This keeps
    the conformance test meaningful without asserting a wire format Codex
    has not published.
    """
    hook_event = str(raw.get("hook_event_name", ""))
    tool_name = raw.get("tool_name")
    tool_input = raw.get("tool_input")
    if not isinstance(tool_input, Mapping):
        tool_input = {}

    prompt: Optional[str] = None
    for key in ("prompt", "description"):
        value = tool_input.get(key)
        if isinstance(value, str):
            prompt = value
            break

    known = {"hook_event_name", "tool_name", "tool_input", "session_id", "transcript_path"}
    extra = {k: v for k, v in raw.items() if k not in known}

    return Event(
        hook_event=hook_event,
        tool_name=tool_name if isinstance(tool_name, str) else None,
        tool_input=tool_input,
        prompt=prompt,
        session_id=raw.get("session_id") if isinstance(raw.get("session_id"), str) else None,
        transcript_path=None,
        extra=extra,
    )


def render_decision(decision: Decision) -> dict:
    """Build the JSON dict Codex's PreToolUse hook expects on stdout.

    Identical shape to `adapters.claude.hook_io.render_decision`: a DENY
    finding maps to `hookSpecificOutput.permissionDecision: "deny"` with
    `permissionDecisionReason` set; a clean or WARN-only decision maps to
    `"allow"`, with warnings joined into `permissionDecisionReason` too.
    Per the fetched hooks doc's "PreToolUse — deny/allow/rewrite decisions"
    example, this is the documented Codex shape, not a guess ported from
    Claude — the two happening to match is what makes the conformance test
    in tests/conformance/ meaningful for `render_decision`, not just
    `parse_event`.
    """
    if not decision.permit:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": decision.deny_reason or "denied by policy",
            }
        }

    output: dict = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
    }
    if decision.warnings:
        output["hookSpecificOutput"]["permissionDecisionReason"] = "; ".join(decision.warnings)
    return output


def render_report(decision: Decision) -> str:
    """Human-readable text for the lwb-report skill. Reporting only — never blocks."""
    lines = []
    if decision.permit:
        lines.append("lwb: would ALLOW under current policy.")
    else:
        lines.append(f"lwb: would DENY under current policy — {decision.deny_reason}")
    for warning in decision.warnings:
        lines.append(f"lwb: warning — {warning}")
    if not decision.findings:
        lines.append("lwb: no rule had an opinion on this event.")
    return "\n".join(lines)


def load_policy(raw: Any) -> Policy:
    return load_policy_dict(raw)

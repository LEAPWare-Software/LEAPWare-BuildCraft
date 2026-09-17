"""Claude Code adapter: translate Claude's hook JSON <-> lwb_core's neutral shapes.

This module does the I/O-adjacent translation ONLY: parsing a dict already
read from stdin into an `Event`, and turning a `Decision` into the dict
Claude Code's hook protocol expects on stdout. It does not read stdin, write
stdout, or call sys.exit — see `plugins/claude/lwb/bin/lwb_hook.py` for the
thin script that does that, so this module stays unit-testable against
fixtures with no subprocess involved.

Claude Code hook JSON shapes referenced here (PreToolUse input, PreToolUse
output's `hookSpecificOutput.permissionDecision`) are documented at
https://docs.claude.com/en/docs/claude-code/hooks; see docs/install-claude.md
for the exact citations and the sanitized fixtures this adapter is tested
against in tests/adapters/fixtures/claude/.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from lwb_core.config import Policy
from lwb_core.engine import Decision
from lwb_core.events import Event

#: Claude's env var naming the plugin's own root directory, used in
#: hooks.json command args (e.g. "${CLAUDE_PLUGIN_ROOT}/bin/lwb_hook.py").
#: Per Claude Code's own plugins reference.
PLUGIN_ROOT_VAR = "CLAUDE_PLUGIN_ROOT"


def parse_event(raw: Mapping[str, Any]) -> Event:
    """Build a neutral `Event` from a Claude Code hook's stdin JSON.

    Recognized top-level fields (per Claude Code hooks docs): `hook_event_name`,
    `tool_name`, `tool_input`, `session_id`, `transcript_path`. Any other
    field is preserved under `Event.extra` rather than dropped.
    """
    hook_event = str(raw.get("hook_event_name", ""))
    tool_name = raw.get("tool_name")
    tool_input = raw.get("tool_input")
    if not isinstance(tool_input, Mapping):
        tool_input = {}

    prompt: Optional[str] = None
    if isinstance(tool_input, Mapping):
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
        transcript_path=(
            raw.get("transcript_path") if isinstance(raw.get("transcript_path"), str) else None
        ),
        extra=extra,
    )


def render_decision(decision: Decision) -> dict:
    """Build the JSON dict Claude Code expects on a PreToolUse hook's stdout.

    A DENY finding maps to `hookSpecificOutput.permissionDecision: "deny"`
    with `permissionDecisionReason` set to the deny reason. A WARN-only or
    clean decision maps to `"allow"`; warnings are carried in
    `permissionDecisionReason` too, joined, so they are visible in the
    transcript even though they never block.
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


def load_policy(raw: Any) -> Policy:
    """Thin re-export so callers only need to import this module.

    Kept here (rather than making bin/lwb_hook.py import lwb_core.config
    directly) so every Claude-facing translation lives in one file.
    """
    from lwb_core.config import load_policy_dict

    return load_policy_dict(raw)

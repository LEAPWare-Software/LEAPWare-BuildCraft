---
name: lwb-report
description: Run lwb's policy engine over a described action and report what it WOULD decide, without waiting for the real PreToolUse hook to fire (Codex side; see hooks/hooks.json for the enforcing hook itself).
---

# lwb-report (Codex)

The Codex plugin now also ships an enforcing `PreToolUse` hook
(`hooks/hooks.json`, running `bin/lwb_hook.py`), the same mechanism the
Claude Code plugin uses. This skill is a preview path on top of the same
engine: given a description of an action (e.g. a sub-task dispatch and its
prompt), it runs `lwb_core.engine.evaluate` via `adapters/codex/hook_io.py`
and reports the decision in plain language using `render_report`, useful
for checking a policy change before a real dispatch exercises it.

## Usage

1. Build a neutral event: `hook_event_name`, `tool_name`, and `tool_input`
   (at minimum a `prompt` key for a dispatch-shaped action).
2. Load the active policy the same way lwb-config does.
3. Run `adapters.codex.hook_io.parse_event`, then `lwb_core.engine.evaluate`,
   then `adapters.codex.hook_io.render_report`.
4. Present the report verbatim; a reported DENY here means the enforcing
   hook would also deny the same event in `hookSpecificOutput` shape.

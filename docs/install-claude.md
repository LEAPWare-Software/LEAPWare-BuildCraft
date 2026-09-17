# Installing buildcraft on Claude Code

## From this local checkout (development)

1. In Claude Code, add this repository as a marketplace source pointing at
   `.claude-plugin/marketplace.json` (root of this repo), or add
   `plugins/claude/lwb` directly as a local plugin path, per Claude Code's
   own plugin-development docs.
2. Before installing, run `python scripts/lwb_build.py` from the repo root so
   `plugins/claude/lwb/vendor/` contains a current copy of `lwb_core` and
   `adapters/claude` — the plugin cannot import from outside its own
   directory once installed.
3. Enable the `buildcraft` plugin.

## What it registers

One hook, in `plugins/claude/lwb/hooks/hooks.json`:

```json
{
  "matcher": "Agent",
  "hooks": [
    {
      "type": "command",
      "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/bin/lwb_hook.py\" || python \"${CLAUDE_PLUGIN_ROOT}/bin/lwb_hook.py\""
    }
  ]
}
```

on `PreToolUse`. `${CLAUDE_PLUGIN_ROOT}` is the variable name Claude Code's
own hooks documentation uses for a plugin's own install directory. The
`python3 ... || python ...` form is this project's own portable
dual-interpreter launch — see `docs/architecture.md#the-hook-launch-method`
for why it is safe (this hook always exits `0` and signals its decision on
stdout, never via exit code) and for the official docs consulted.

## What it does on each dispatch

`plugins/claude/lwb/bin/lwb_hook.py` reads the `PreToolUse` JSON from
stdin, evaluates it against the active policy (see `docs/policy.md`), and
writes a JSON decision to stdout:

- A `deny`-mode finding produces
  `hookSpecificOutput.permissionDecision: "deny"` with
  `permissionDecisionReason` set — Claude Code blocks the dispatch and
  shows the reason.
- Otherwise, `permissionDecision: "allow"`, with `permissionDecisionReason`
  carrying any `warn`-mode findings (visible, non-blocking).

Every evaluated event is also appended as one JSON line to a ledger file —
see `docs/rules/lwb-version.md` and `lwb-report`'s `SKILL.md` for how to
read it.

## Hook event JSON shapes referenced

`docs/rules/lwb-version.md` and `adapters/claude/hook_io.py` were written
against the Claude Code hooks reference:
`https://docs.claude.com/en/docs/claude-code/hooks` — `PreToolUse` input
fields (`hook_event_name`, `tool_name`, `tool_input`, `session_id`,
`transcript_path`) and the `hookSpecificOutput.permissionDecision` /
`permissionDecisionReason` output shape for `PreToolUse`.

Sanitized fixtures built from these shapes live under
`tests/adapters/fixtures/claude/`; every value in them is placeholder text,
not data from any real session.

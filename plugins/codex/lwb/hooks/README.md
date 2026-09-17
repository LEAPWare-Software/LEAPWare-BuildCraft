# hooks/hooks.json — enforcing, same as the Claude Code plugin

This directory registers a real, DENY-capable `PreToolUse` hook, the Codex
equivalent of `plugins/claude/lwb/hooks/hooks.json`. Both plugins run the
same `lwb_core` engine and the same rules; only the wire format differs.

## Why this changed (was reporting-only)

Earlier recon (kept in `docs/install-codex.md`'s history via git blame, and
summarized there) could not confirm a documented `plugin.json` manifest
shape for plugin-bundled hooks from the sources it reached, so this plugin
shipped reporting-only (skills only, no hook). A direct fetch of the
canonical docs page (`https://developers.openai.com/codex/hooks`,
redirecting to `https://learn.chatgpt.com/docs/hooks`) resolved that gap:
hooks are enabled by default, plugin-bundled hooks are documented (a
`plugin.json` `hooks` field pointing at a `hooks/hooks.json` file, exactly
the layout used here), and `PreToolUse` uses the same
`hookSpecificOutput.permissionDecision` allow/deny shape Claude Code's hook
protocol uses. See `docs/install-codex.md` for the full citation trail.

## What ships here

- `hooks.json` — one `PreToolUse` hook, matcher `Agent`, running
  `bin/lwb_hook.py` (mirrors `plugins/claude/lwb/bin/lwb_hook.py`) via the
  `${PLUGIN_ROOT}` env var Codex sets for a plugin-bundled hook's command,
  with a `commandWindows` override per the docs' Windows guidance.
- `bin/lwb_hook.py` — reads the hook's stdin JSON, evaluates it through
  `lwb_core.engine.evaluate`, appends one ledger line under
  `${PLUGIN_DATA}` (Codex's writable per-plugin data directory, mirroring
  Claude's `CLAUDE_PLUGIN_DATA`), and writes the Codex-shaped decision to
  stdout via `adapters/codex/hook_io.render_decision`.

## Trust step

Per the fetched docs, a plugin-bundled hook is not auto-trusted: a user
reviews and trusts it once via `/hooks` before Codex runs it. That is a
one-time step per install, not a per-session one, and it does not change
the shipped behavior once trusted — `docs/install-codex.md` documents it as
an install step, not grounds to withhold the hook.

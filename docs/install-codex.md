# Installing buildcraft on Codex CLI

The Codex plugin now ships the same enforcement the Claude Code plugin
does: an enforcing `PreToolUse` hook (`hooks/hooks.json`, running
`bin/lwb_hook.py`), backed by the same `lwb_core` engine and policy format,
via `adapters/codex/hook_io.py`. It also installs `skills/lwb-config` and
`skills/lwb-report`, unchanged in purpose (inspect policy / preview a
decision) now that the hook itself enforces.

## Why this is enforcing now — the recon this decision rests on

The owner's standing instruction for this project: *"Codex supports hooks,
so full enforcement on both; no reporting-only constraint."* This section
records the recon that confirms that instruction is buildable, superseding
an earlier reporting-only decision made under an unresolved manifest-shape
question (see git history of this file for that earlier text, and
`plugins/codex/lwb/hooks/README.md` for the same "why this changed" note
kept next to the hook it now explains).

### What Codex CLI hook support looks like (checked September 2026, direct doc fetch)

A direct fetch of the canonical docs page
(`https://developers.openai.com/codex/hooks`, which 308-redirects to
`https://learn.chatgpt.com/docs/hooks`) resolved every open question the
earlier recon left:

- **Hooks are enabled by default.** Disable with `[features] hooks = false`
  in config — this plugin relies on the default.
- **Windows is supported**, via a `commandWindows` field on a hook handler
  for a platform-specific command override (this plugin's
  `hooks/hooks.json` uses it) and a separate `windows_managed_dir` for
  enterprise-managed hooks (not used here).
- **Plugin-bundled hooks are documented.** A plugin's `.codex-plugin/plugin.json`
  declares a `hooks` field, either a path to a `hooks/hooks.json` file
  (the shape this plugin uses: `"hooks": "./hooks/hooks.json"`) or an
  inline array. `hooks/hooks.json` itself organizes as event → matcher
  group → handler, the same three-level shape as a Claude Code plugin's
  `hooks/hooks.json`.
- **`PreToolUse`'s decision shape matches Claude Code's exactly**: a
  handler's stdout JSON carries
  `hookSpecificOutput.permissionDecision` (`"allow"` or `"deny"`,
  `permissionDecisionReason` for either), and a handler receives the same
  family of stdin fields (`session_id`, `cwd`, `hook_event_name`, ...).
  This is why `adapters/codex/hook_io.render_decision` is a straight port
  of `adapters/claude/hook_io.render_decision` rather than a new shape.
- **Plugin hooks receive `PLUGIN_ROOT`** (the installed plugin directory)
  and `PLUGIN_DATA` (a writable per-plugin data directory) as environment
  variables — the Codex equivalents of Claude Code's `CLAUDE_PLUGIN_ROOT`
  and `CLAUDE_PLUGIN_DATA`, used the same way in `bin/lwb_hook.py`.
- **Trust step**: a plugin-bundled ("non-managed") hook still requires a
  user to review and trust it via `/hooks` before its first execution.
  That is a real UX step this project cannot remove, but it is a one-time
  install-time step, not a per-session gate that would defeat "mechanical,
  no-prompting enforcement" as a design goal — so it is not grounds to
  withhold the hook, only to document it (see
  `plugins/codex/lwb/hooks/README.md`).

An earlier recon pass (general web search plus the same canonical-docs
fetch) had read these two sources as disagreeing on default-enablement and
Windows support, and could not locate the manifest shape at all. Re-fetching
the canonical docs page directly, quoted above, resolves that disagreement
in the canonical page's favor and supplies the manifest shape that was
previously missing.

### Sources checked

- https://developers.openai.com/codex/hooks (redirects to
  https://learn.chatgpt.com/docs/hooks) — hook events, handler fields,
  stdin/stdout schema, plugin-bundled hooks, default-enabled state,
  Windows support.
- https://developers.openai.com/codex/plugins (redirects to
  https://learn.chatgpt.com/docs/plugins) — plugin manifest shape.

## What IS installed

- `hooks/hooks.json` — one `PreToolUse` hook, matcher `Agent`, running
  `bin/lwb_hook.py` via `${PLUGIN_ROOT}`, with a `commandWindows` override.
- `bin/lwb_hook.py` — reads stdin, evaluates the event through the shared
  engine, appends one ledger line under `${PLUGIN_DATA}`, writes the
  decision to stdout.
- `skills/lwb-config/SKILL.md` — read/edit the active policy file (same
  format as Claude Code's, see `docs/policy.md`).
- `skills/lwb-report/SKILL.md` — run the same engine over a described
  action and report the decision in plain language, useful for previewing
  a policy change without waiting for a real dispatch to hit the hook.

## Conformance with the Claude Code plugin

`tests/conformance/test_same_decision_both_adapters.py` feeds the same
neutral event through both adapters' `parse_event` and asserts the
resulting `Decision` (and, for the paired `render_decision` case, the full
rendered JSON) is identical — proof the engine's behavior does not silently
change by host. `tests/adapters/fixtures/codex/` holds Codex's own fixture
event shapes; `tests/adapters/test_codex_hook_io.py` covers
`render_decision`'s allow/deny/warn shapes directly.

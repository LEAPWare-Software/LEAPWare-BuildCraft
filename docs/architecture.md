# Architecture

## The pure core / impure edges split

```
                event (native JSON)
                      |
                      v
            +-------------------+
            |  adapter.parse_event()  |   adapters/claude/hook_io.py
            +-------------------+        adapters/codex/hook_io.py
                      |
                      v
                Event (neutral)          core/lwb_core/events.py
                      |
                      v
            +-------------------+
            |  engine.evaluate()  |      core/lwb_core/engine.py
            +-------------------+
                 /            \
        Policy (loaded)   RULES (registry)
     core/lwb_core/config.py   core/lwb_core/rules/__init__.py
                      |
                      v
                Decision (neutral)       core/lwb_core/engine.py
                      |
                      v
            +----------------------+
            | adapter.render_*()   |     adapters/claude/hook_io.py: render_decision
            +----------------------+     adapters/codex/hook_io.py: render_report
                      |
                      v
              host-native output
```

`core/lwb_core` does **no I/O**: no file reads, no stdin, no environment
variables, no clock. Every function in it is `(data in) -> (data out)`.
This is what the mutation test in `tests/core/test_engine_mutation.py` and
the conformance test in `tests/conformance/` rely on: the same `Event`
through the same `Policy` always produces the same `Decision`, regardless of
which adapter built the `Event` or what will be done with the `Decision`.

Everything that touches the outside world — reading stdin, resolving a
policy file path, appending a ledger line, writing stdout, setting an exit
code — lives in an adapter or a plugin's `bin/` script
(`plugins/claude/lwb/bin/lwb_hook.py`).

## Why two adapters, one core

Claude Code and Codex CLI have different hook JSON shapes and different
manifest formats — both now enforce a `PreToolUse` decision the same way
(`hookSpecificOutput.permissionDecision`, see `docs/install-codex.md`).
Rather than writing the `lwb_version` rule twice, or writing a
Claude-specific engine, every rule is written once against the neutral
`Event`/`Decision` shapes, and each host gets a thin adapter that
translates its native format at the edges.

## The vendoring step

A Claude Code plugin (and a Codex plugin) is distributed as its own
self-contained directory — it cannot import a sibling package from outside
that directory at install time. `scripts/lwb_build.py` copies `core/lwb_core`,
`core/policy`, and the matching `adapters/<host>` into
`plugins/<host>/lwb/vendor/` before a plugin is installed or released.
`scripts/lwb_build.py --check` (run in CI) fails if a committed `vendor/`
directory — during local development, not committed per `.gitignore` — has
drifted from its source. Nobody should hand-edit anything under `vendor/`.

## The hook launch method

SACRED (owner directive 8): the plugin must not depend on this machine —
not `python3` vs. `python`, not a pinned minor version, not a Windows
Python-Launcher (`py`) that on some Windows installs is a Microsoft Store
stub that prints a store prompt instead of running anything.

`plugins/claude/lwb/hooks/hooks.json`'s `command` is a single string, run
through the platform shell exactly as Claude Code invokes any `"type":
"command"` hook (`cmd.exe` on Windows, `sh` elsewhere — confirmed by
testing, see below):

```
python3 "${CLAUDE_PLUGIN_ROOT}/bin/lwb_hook.py" || python "${CLAUDE_PLUGIN_ROOT}/bin/lwb_hook.py"
```

`||` is a shell primitive both `cmd.exe` and POSIX `sh` support: the right
side only runs if the left side's command could not even be started (exit
127 on POSIX, 9009 on `cmd.exe` — "not recognized"). This is safe here, and
would NOT be safe for a script that signals its decision through its exit
code, because `${CLAUDE_PLUGIN_ROOT}/bin/lwb_hook.py` always exits `0` and
carries its decision in `hookSpecificOutput.permissionDecision` on stdout
instead (see `docs/install-claude.md`) — so a `python3` run that
successfully denies still exits `0`, and the `python` fallback is never
spuriously re-run on top of it.

Sources consulted for this design (both `WebFetch`ed during this change):

- Claude Code plugins reference —
  `https://code.claude.com/docs/en/plugins-reference` — confirms
  `${CLAUDE_PLUGIN_ROOT}` is substituted by Claude Code itself (not the
  shell) before the command runs, and that a plugin cannot rely on a
  hard-coded absolute path.
- `anthropics/claude-code`'s own `hook-development` skill —
  `https://github.com/anthropics/claude-code/blob/main/plugins/plugin-dev/skills/hook-development/SKILL.md`
  — confirmed this project's own reading: it documents `${CLAUDE_PLUGIN_ROOT}`
  and quoting bash variables, but does **not** itself prescribe a
  cross-platform Python interpreter selection — that choice, and its
  reasoning above, is this project's own.

`scripts/lwb_check_hook_launch.py` (the `lwb-portable` CI job, run on all
three hosted OSes with nothing installed beyond `actions/setup-python`)
extracts this exact `command` string from `hooks.json`, substitutes
`${CLAUDE_PLUGIN_ROOT}` the same way, and runs it through the shell against
a `warn`-mode `lwb_version` policy and a fixture event — asserting
`hookSpecificOutput.permissionDecision == "allow"` on real output, not a
mock of the launch mechanism.

## Fail-open, everywhere

Three independent layers all fail open, each documented at its own layer
rather than assumed:

1. `lwb_core.config.load_policy_dict`: a missing or malformed policy
   dict resolves every unmentioned or misconfigured rule to `off`. See
   `docs/policy.md#fail-open`.
2. `lwb_core.engine.evaluate`: an exception raised inside a single rule is
   caught and downgraded to a `warn`-shaped finding rather than propagating
   or defaulting to `deny`.
3. `plugins/claude/lwb/bin/lwb_hook.py`: a policy file that cannot be
   read or parsed at all is treated as `None`, which layer 1 above then
   treats as an all-`off` policy. A ledger write failure is swallowed
   rather than blocking the decision from being returned.

The engine never turns "something went wrong" into "block the action" on
its own; only an explicit, successfully-loaded `deny`-mode rule blocks
anything.

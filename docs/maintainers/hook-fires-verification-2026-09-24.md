# Verification: the hook genuinely fires from `hooks.json` (2026-09-24)

Item 1.8 of `docs/requirements/build-plan.md`: "Confirm the hook fires from
`hooks.json` — never once observed in this product's life."

**Verdict: CONFIRMED for both registered matchers, on this environment.**
`plugins/claude/lwb/bin/lwb_hook.py` genuinely runs as a `PreToolUse` hook
in a real, live, non-simulated Claude Code session that loaded the `lwb`
plugin through Claude Code's own plugin-loading path (`--plugin-dir`), for
both a real `Bash` tool dispatch and a real `Agent`/subagent (`Task` tool)
dispatch. This is new evidence: nothing before this document ran the
plugin inside an actual Claude Code session and observed the hook produce
output. `scripts/lwb_check_hook_launch.py` (the `lwb-portable` CI job)
proves only the *launch mechanics* of the command string in `hooks.json`
via `subprocess` — it never loads the plugin into a real session, so it
could not and did not establish this.

## What this does NOT prove

Read this section before citing this document for more than it says.

- **OS/interpreter coverage.** Everything below ran on one Linux
  container: Ubuntu 24.04.4 LTS, `Python 3.11.15`, Claude Code `2.1.282`
  (`/opt/node22/bin/claude`). CI's `lwb-portable` job (launch mechanics
  only, not a live session) runs on Windows and macOS too; this document
  does not extend live-session evidence to those OSes or to any other
  Python or Claude Code version.
- **Only `dontAsk` permission mode was tested end-to-end.** Root/sudo
  privileges in this container refuse `--dangerously-skip-permissions` and
  `--permission-mode bypassPermissions` outright (see reproduction below);
  the hook was observed firing under `--permission-mode dontAsk` with a
  `--settings` file pre-allowing `Bash` and `Task`. Other permission modes
  were not exercised.
- **Only one event per matcher.** Each run below issued exactly one
  qualifying tool call and observed exactly one ledger line. This does not
  characterize behavior under concurrent tool calls, denied events, or a
  session issuing many dispatches.
- **Policy content is untested here.** The bundled default policy only
  ever produced `lwb_version`'s `warn`-mode, always-allow finding in these
  runs (`plugins/claude/lwb/vendor/policy/default.json`). This document is
  about whether the hook *fires and is observed*, not about deny-mode
  policy behavior.
- **The historical 30-second-timeout defect
  (`docs/maintainers/session-handoff-2026-09-19.md`) is not re-litigated
  here.** `scripts/lwb_check_hook_launch.py` already reads its subprocess
  timeout from `hooks.json` itself rather than hardcoding one (see that
  script's `_check_one` docstring); this document's live runs completed in
  a few seconds each, well inside the `10`s `hooks.json` declares, so they
  neither reproduce nor rule out a timeout-related failure under load.

## Environment

```
$ /opt/node22/bin/claude --version
2.1.282 (Claude Code)
$ python3 --version
Python 3.11.15
$ uname -a
Linux vm 6.18.44-fc-v37 #1 SMP PREEMPT_DYNAMIC @0 x86_64 x86_64 x86_64 GNU/Linux
$ cat /etc/os-release | head -3
PRETTY_NAME="Ubuntu 24.04.4 LTS"
NAME="Ubuntu"
VERSION_ID="24.04"
```

## Reproduction

All commands below were run from an isolated scratch directory
(`/tmp/lwb-hook-scratch/work`), **not** from inside this repository
checkout, so the nested session's own git/tool activity could not touch
this repo's state. Before any of this, `python scripts/lwb_build.py` was
run from the repo root so `plugins/claude/lwb/vendor/` was current (a
plugin cannot import outside its own directory once "installed" — see
`docs/architecture.md#the-vendoring-step`).

### 0. Settings file (pre-allows the tools so a non-interactive session does not hang on a permission prompt)

`/tmp/lwb-hook-scratch/work/settings.json`:

```json
{
  "permissions": {
    "allow": ["Bash", "Task"]
  }
}
```

`--dangerously-skip-permissions` / `--permission-mode bypassPermissions`
were tried first and refused outright by the CLI in this container
(running as root):

```
$ claude -p "..." --plugin-dir .../plugins/claude/lwb --permission-mode bypassPermissions ...
--dangerously-skip-permissions cannot be used with root/sudo privileges for security reasons
```

exit code 1, no session ran, nothing to observe. Switching to
`--permission-mode dontAsk` with the `--settings` allow-list above worked
non-interactively.

### 1. `Bash` matcher

```
$ cd /tmp/lwb-hook-scratch/work
$ LWB_LEDGER_PATH=/tmp/lwb-hook-scratch/work/ledger-bash.jsonl \
  claude -p "Run the shell command: echo hello-lwb-hook-test    Use the Bash tool to run it, then tell me exactly what it printed." \
    --plugin-dir <repo>/plugins/claude/lwb \
    --settings /tmp/lwb-hook-scratch/work/settings.json \
    --permission-mode dontAsk \
    --output-format json \
    --add-dir /tmp/lwb-hook-scratch/work
```

Exit code `0`. Transcript (`--output-format json`) `result`:

```
It printed: `hello-lwb-hook-test`
```

`ledger-bash.jsonl` (the whole file — one line, gained by this one run):

```json
{"timestamp": "2026-09-24T20:17:34.440553+00:00", "hook_event": "PreToolUse", "tool_name": "Bash", "session_id": "03c8c1e5-6749-5af0-94c6-8fd72836d10c", "permit": true, "deny_reason": null, "warnings": ["lwb 0.1.0: reporting only, no policy enforced yet"], "findings": [{"rule_id": "lwb_version", "mode": "warn", "reason": "lwb 0.1.0: reporting only, no policy enforced yet"}]}
```

`tool_name: "Bash"` and the `lwb_version` `warn` finding (the only rule the
bundled default policy currently arms) match the live Bash dispatch
exactly. The ledger file did not exist before this run.

### 2. `Agent` matcher (subagent dispatch via the `Task` tool)

```
$ LWB_LEDGER_PATH=/tmp/lwb-hook-scratch/work/ledger-agent.jsonl \
  claude -p "Use the Task tool to dispatch a general-purpose subagent with the instruction: 'Reply with the exact text: subagent-lwb-hook-test-ok'. Wait for it to finish and then tell me exactly what the subagent returned." \
    --plugin-dir <repo>/plugins/claude/lwb \
    --settings /tmp/lwb-hook-scratch/work/settings.json \
    --permission-mode dontAsk \
    --output-format json \
    --add-dir /tmp/lwb-hook-scratch/work
```

Exit code `0`. Transcript `result`:

```
The subagent returned exactly: `subagent-lwb-hook-test-ok`
```

Transcript's own `subagent_stats`: `"spawned":1,...,"by_type":{"general-purpose":1}}`
— confirms a real subagent dispatch happened, not just a text description
of one.

`ledger-agent.jsonl` (the whole file — one line):

```json
{"timestamp": "2026-09-24T20:17:48.746823+00:00", "hook_event": "PreToolUse", "tool_name": "Agent", "session_id": "03c8c1e5-6749-5af0-94c6-8fd72836d10c", "permit": true, "deny_reason": null, "warnings": ["lwb 0.1.0: reporting only, no policy enforced yet"], "findings": [{"rule_id": "lwb_version", "mode": "warn", "reason": "lwb 0.1.0: reporting only, no policy enforced yet"}]}
```

Note for anyone rerunning this: Claude Code's `PreToolUse` matcher name
for a subagent dispatch is `Agent` (matching `hooks.json`'s second entry),
even though the tool the model calls is named `Task` — confirmed here
empirically by `tool_name: "Agent"` in the ledger line produced by a
`Task`-tool dispatch. This is exactly the entry `hooks.json`'s `"matcher":
"Agent"` block is written to catch.

## Falsifying this

Anyone with `claude` CLI `2.1.282` (or checking their own version first)
and network access to the Anthropic API can rerun the two commands in
section 1 and 2 verbatim (substituting their own checkout path for
`<repo>` and an isolated scratch directory for
`/tmp/lwb-hook-scratch/work`) and either see a ledger line appear each
time, matching the shapes above, or not. `LWB_LEDGER_PATH` isolates the
observation from any other ledger a real install might have.

## Bearing on `docs/maintainers/proof-of-completion-plan.md`

That document's "foolproof" row (`| "foolproof" | The only hook the
product ships (`matcher: "Agent"`) has never been observed to fire. ... |`)
predates this document and is not corrected here — it is outside the
`HANDOFF.md` / `docs/requirements/build-plan.md` pointers this deliverable
was scoped to update. It now also predates this evidence: item 1.8's
one-matcher framing ("`matcher: "Agent"`") is itself out of date, since
`hooks.json` registers `Agent` **and** `Bash` as two separate `PreToolUse`
entries — both are now confirmed firing per this document, with the scope
limits above.

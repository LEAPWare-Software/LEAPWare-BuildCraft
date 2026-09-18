# LEAPWare BuildCraft

**New session? Read [HANDOFF.md](HANDOFF.md) first.**

**BuildCraft makes delivery discipline unskippable for AI coding agents.**
Stages, roles and gates are decided at the CLI's own hook boundary —
allow, warn or deny — and every decision and every claim of *done* leaves
an evidence record a human can audit later. See
[`docs/requirements/mission.md`](docs/requirements/mission.md).

`LEAPWare-BuildCraft-legacy` is a separate, private, archived repository;
this repo does not continue it, and nothing from it has been carried over
here (see `HANDOFF.md`).

Shipped as two plugins sharing one policy engine:

| Host | Package | What it does |
|---|---|---|
| Claude Code | `plugins/claude/lwb/` | Registers an enforcing `PreToolUse` hook. |
| Codex CLI | `plugins/codex/lwb/` | Registers an enforcing `PreToolUse` hook, same engine as Claude Code. See [docs/install-codex.md](docs/install-codex.md). |

Runtime dependency policy: **Python 3.10+ standard library only.** No
third-party package is imported by `core/`, `adapters/`, or any shipped
plugin script. `pytest` is a dev-only dependency for running the test suite.

License: [Apache-2.0](LICENSE).

## The walking skeleton

One rule ships today, `lwb_version` (see
[docs/rules/lwb-version.md](docs/rules/lwb-version.md)): a safe no-op that
fires on every event, reports this build's `lwb_core.__version__`, and
never denies — even a policy file that (incorrectly) configures it to
`deny` still allows. It exists to prove the whole pipeline end to end —
event in, pure decision, decision out — without shipping any real
enforcement yet: BuildCraft's actual SDLC gate rules (stage checks, role
lanes, and the enforcement behind them — see
[docs/requirements/owner-directives.md](docs/requirements/owner-directives.md)
for this project's own requirements-gathering placeholder) are designed
and built in a later session.

## How it fits together

```
core/lwb_core/          pure engine: (Event, Policy) -> Decision. No I/O.
core/policy/              policy JSON schema + bundled default policy.
adapters/claude/          Claude Code hook JSON <-> neutral Event/Decision.
adapters/codex/           Codex event shape <-> neutral Event; enforcing hook.
plugins/claude/lwb/      the installable Claude Code plugin (vendors core+adapter).
plugins/codex/lwb/       the installable Codex plugin (vendors core+adapter).
scripts/lwb_build.py          copies core/ + the matching adapter into each plugin's vendor/.
```

See [docs/architecture.md](docs/architecture.md) for the full data flow and
[docs/policy.md](docs/policy.md) for the policy file format and the
fail-open contract.

## Installing

- Claude Code: [docs/install-claude.md](docs/install-claude.md).
- Codex CLI: [docs/install-codex.md](docs/install-codex.md).

## Developing

```
python -m pytest -q                    # unit + adapter + conformance tests
python scripts/lwb_build.py                # refresh both plugins' vendor/ trees
python scripts/lwb_build.py --check        # fail if vendor/ has drifted from source
python scripts/lwb_validate_claude_plugin.py
python scripts/lwb_validate_codex_plugin.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow and
[SECURITY.md](SECURITY.md) for how to report a vulnerability.

## Status

Early scaffold: one rule, two adapters, a pure engine, and the tests and CI
that keep them honest. See `HANDOFF.md` for what is in flight.

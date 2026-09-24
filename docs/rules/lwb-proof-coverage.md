# Rule: `lwb_proof_coverage`

**Status:** shipped, report-only. Source:
`core/lwb_core/rules/lwb_proof_coverage.py`. Default mode: `warn` (see
`core/policy/default.json`).

`docs/requirements/build-plan.md`, Phase 1 item 1.1. `proof_coverage` has
existed since PR #6 only as an internal CI script
(`scripts/lwb_check_proof.py::check_coverage`, the `lwb-proof-coverage`
job in `.github/workflows/ci.yml`, run post-merge on push to `main`) —
named in the plan, absent from the shipped plugin. This is what makes it a
**rule**: installed into every consuming repo, not just enforced inside
this one.

## What it checks

Landed deliverables — commits whose subject looks like a GitHub
squash-merge (a trailing `(#N)`) — that have no matching `proof/*.json`
record, honouring `proof/exempt.json`'s carve-out. Same shape of check as
CI's `check_coverage`, adapted to run where CI's version cannot.

## Why this is not the same check CI runs

CI's `check_coverage` runs `git log` over a full revision range, with a
real subprocess and full repository history — and it still runs,
unchanged, as `lwb-proof-coverage` in `.github/workflows/ci.yml`. That
mechanism is not available to a rule: `core/lwb_core` does no I/O, and
`adapters/claude/repo_facts.py` — the module that gathers facts for every
rule — must not shell out to `git` (owner directive 8) and must stay cheap
enough to run before every hook event.

So this rule reads a **best-effort, bounded, local approximation**
instead: `adapters/claude/repo_facts.collect_landed_unproven` walks loose
commit objects reachable from HEAD, first-parent only, up to a fixed
depth (40 commits), stopping the moment it reaches one that is not a
loose object. That stopping point is common and expected, not a bug: a
fresh clone transfers its history as a packfile, and `git gc` packs loose
objects once there are enough of them, so a repository with no recent
local commits may yield nothing here at all. **An empty result means
"found none within what was walkable", never "confirmed fully covered."**
This rule's finding says so explicitly, every time it fires.

If you want the exhaustive, `git log`-backed version of this check, adopt
this repository's own CI job pattern (`scripts/lwb_check_proof.py
--coverage <range>`) rather than relying on the hook for it.

## Trigger

Fires on the same event `lwb_proof_required` does: a `PreToolUse` `Bash`
event whose command publishes (`git push`, `gh pr create`, `gh pr merge`).
It reuses `lwb_proof_required`'s own command-scanning logic
(`_scan_command`) rather than re-implementing it, so the two rules can
never disagree about what counts as a publish. This keeps the rule as
rare and meaningful as the one it sits beside, instead of firing on every
Bash call in a session.

## What it reports

```
3 landed deliverable(s) reachable from HEAD have no matching proof record
(best-effort local scan, not exhaustive -- see
docs/rules/lwb-proof-coverage.md): a1b2c3d4e5f6 (#41), ...
Add a proof/<id>.json for each, or list it in proof/exempt.json with a
reason.
```

## When it says nothing, on purpose

- `event.repo is None` — the adapter gathered no facts.
- `event.repo.facts_incomplete` — the adapter looked and could not fully
  read something; same posture as `lwb_proof_required`.
- `event.repo.landed_unproven == ()` — nothing found, or the walk could
  not reach far enough. Both look identical to this rule, deliberately.
- The command does not publish.

## Mode

| Mode | Behavior |
|---|---|
| `off` | No check runs. |
| `warn` | **Shipped default.** The finding is surfaced but the command proceeds. |
| `deny` | The publish is blocked. |

Ships at `warn`: this repository's own discipline is to land a new gate
report-only first and arm it in a separate, later change once there is
ledger evidence about what it actually fires on.

## Tests

- `tests/core/test_lwb_proof_coverage.py` — the rule as a pure unit.
- `tests/adapters/test_claude_repo_facts_landed_unproven.py` — the impure
  collector (`collect_landed_unproven`, `resolve_head_commit`) against
  real on-disk git layouts.

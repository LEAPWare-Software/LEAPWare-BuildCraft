# Rule: `lwb_proof_integrity`

**Status:** shipped, report-only. Source:
`core/lwb_core/rules/lwb_proof_integrity.py`. Default mode: `warn` (see
`core/policy/default.json`).

`docs/requirements/build-plan.md`, Phase 1 item 1.1. `proof_integrity` is
the other half named in the plan and, until now, absent from the shipped
plugin: in CI, `scripts/lwb_check_proof.py --reexecute` actually RE-RUNS
every command a proof record claims is `verifiable: true` and compares
the resulting digest against what the record recorded — the check that
makes a record hard to fake. It runs report-only in CI
(`continue-on-error: true`) because digest reproducibility across hosted
runners has not yet been proven (see the comment above that step in
`.github/workflows/ci.yml`); Phase 1 item 1.4 ("make re-execution
blocking") is a separate, later piece of work.

## Why this rule does not re-execute anything

Re-running a proof record's commands means spawning arbitrary recorded
subprocesses — potentially a full test suite — from inside a
`PreToolUse` hook. D17 (`docs/requirements/decisions.md`) settled this for
the whole architecture: hooks **gate**, a separate runner (not yet built —
Phase 3 item 3.5) **sequences**, precisely because invoking something that
can take minutes inside a hook puts that latency in front of every tool
call and turns a hung command into a hung session.

So this rule is a **structural, execution-free** check: it reasons only
from what the matched proof record's own JSON already claims about
itself, never from re-running it. It does not solve cross-runner digest
reproducibility — that stays CI's job until item 1.4 lands it as its own,
separate, blocking change.

## What it checks

For the ONE proof record whose id equals the checked-out branch name (the
identifier available without parsing the triggering command — see
"Why branch-only matching" below):

- **Self-certification.** The record's own `checked_by` equals its own
  `author` — the same defect `scripts/lwb_check_proof.py`'s
  `_validate_record` rejects in CI, surfaced here at the moment the
  publish is about to happen rather than only after a PR is opened.
- **A recorded failure.** Some `commands[]` entry's own `exit` does not
  equal its own `expect_exit` — the record admits, in its own content,
  that a command it lists did not pass.

Both are read straight off the record's JSON by
`adapters/claude/repo_facts.collect_matched_proof_facts`; neither
requires running anything.

## Why branch-only matching

`lwb_proof_required` matches a claim against a proof record three ways: a
PR number named on the command line, the branch name, or a number
embedded in the branch name (see `docs/rules/lwb-proof-required.md`). That
logic lives in the pure core and needs the *command text* to extract a PR
number. This rule's matching fact is gathered in the impure adapter,
independent of what command is being run, so it uses only the narrowest,
always-available identifier — the branch name — rather than duplicating
command-parsing logic across the pure/impure boundary. This means the
rule can miss a record matched only by PR number or branch-embedded
number; that is an accepted under-match, not a bug — see "Parsing
posture" in `lwb-proof-required.md` for why this repository resolves that
kind of ambiguity toward silence.

## Trigger

Fires on the same event `lwb_proof_required` and `lwb_proof_coverage` do:
a `PreToolUse` `Bash` event whose command publishes. Reuses
`lwb_proof_required`'s own `_scan_command`.

## What it reports

```
the proof record for 'lwb-ship-the-thing' looks compromised: checked_by
equals author -- it certifies itself. This is a structural, execution-free
check -- it does not re-run any command; see docs/rules/lwb-proof-integrity.md
```

## When it says nothing, on purpose

- No matching record for the branch, or the record could not be read or
  parsed as a JSON object — `matched_proof_self_certified` /
  `matched_proof_has_failed_command` are `None`, and `None` means
  no-opinion, the same discipline `repo is None` gets. This is
  `lwb_proof_required`'s territory, not this rule's.
- `event.repo is None` or `event.repo.facts_incomplete`.
- The command does not publish.
- Neither structural problem is present — this is not a full validator;
  `scripts/lwb_check_proof.py` remains that.

## Mode

| Mode | Behavior |
|---|---|
| `off` | No check runs. |
| `warn` | **Shipped default.** The finding is surfaced but the command proceeds. |
| `deny` | The publish is blocked. |

Ships at `warn`, same discipline as every rule in this family: report-only
first, armed later, separately, once there is ledger evidence about what
it fires on.

## Tests

- `tests/core/test_lwb_proof_integrity.py` — the rule as a pure unit.
- `tests/adapters/test_claude_repo_facts_matched_proof.py` — the impure
  collector (`collect_matched_proof_facts`) against real on-disk records.

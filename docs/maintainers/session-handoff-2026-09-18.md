# Session handoff — 2026-09-17/18

The full record of a long session. `HANDOFF.md` is the one-page
transition; this is the detail behind it. `docs/requirements/decisions.md`
holds D1-D14 and the required-work list; `docs/maintainers/session-protocol.md`
holds how to operate. Read all three.

## Re-derive first, trust nothing here

```
git fetch origin && git status -sb
git for-each-ref --format='%(refname)' refs/heads refs/remotes
git log --oneline origin/main -5
gh pr list --state open
gh run list --branch main --limit 5
```

`git branch -a` is NOT sufficient — its output can be condensed into a
summary that hides remote refs. That trap cost this session a false
"clean" report.

## State at handoff

- `main` at `c33b560`, clean, CI green.
- Remote `lwb-mission-final` at `4b84b5c` holds
  7 commits of unmerged work.
  This is the deliverable. It is NOT merged.
- Remote `lwb-mission-settled` is a leftover from abandoned PR #12; safe
  to delete once `lwb-mission-final` lands.
- PRs #12 and #13 are CLOSED and abandoned. No PR is open.
- Ruleset 23627212 protects `main`: no deletion, no force-push, PR
  required, 9 required checks, squash-only, merge queue.

## What landed on main this session

PRs #1-#11. The scaffold, then: directive 8's leak gate armed after five
private-name literals were found committed in plaintext to this public
repo; `tests/` made a shared lane because it previously belonged to
neither CLI and so nobody could write a test for a shared script;
directives 5 and 7 made enforceable; the no-left-behinds rule; and the
mission renamed to what it actually is.

## What is on `lwb-mission-final`, unmerged

The settled mission with token efficiency as a first-class goal; a quality
floor that is testable today; `acceptance_criteria` and `tokens` required
on proof records from PR 12 onward; `reviewed_commit` binding a review to
the commit it examined; and decisions D9-D14.

## Why PR #13 was abandoned

Its branch history contained a commit that wrote the operator's username
into `proof/13.json`'s `tokens.source` — the sanitiser covered captured
command output but not a field written separately. The env-leak history
scan caught it, on the record that claimed the work was done. Repairing it
needed a force-push the permission layer refuses, so the clean sequence
moved to `lwb-mission-final`.

**Land it with `lwb_check_env_leak.py --range origin/main..HEAD` run
BEFORE opening the PR.** That is the check that caught the leak.

## Five gates that could not do their job

Each was written in good faith, looked correct, and was found by review or
by another gate — never by its author. Assume a sixth exists.

1. `--coverage` ran at PR time hunting a squash subject GitHub only
   creates at merge time. It could never fire.
2. The shared-path review rule demanded a record from a CLI vendor nobody
   runs. It could never be satisfied.
3. The proof gate accepted a digit-string `deliverable` as a PR alias, so
   a record for step 6 of an unrelated plan satisfied PR #6.
4. `reviewed_commit` required matching the head, but committing the record
   moved the head. It could never pass.
5. The env-leak check shipped a placeholder needle, so directive 8 —
   marked SACRED — enforced its path half and no-opped its name half.

A check that passes without checking looks exactly like a check that works.

## The honest state of the product

The plugin registers exactly one rule, `lwb_version`, a deliberate no-op.
Everything with teeth guards this repository's own development, not any
user's. The mission is proven on this repo and unimplemented as a product.

## Environment changed on the operator's machine

- **RTK removed** — hook, binary, and the `@RTK.md` import from global
  `CLAUDE.md`, whose text told every session its output was condensed.
  The owner's own records had rejected RTK; it was found installed and
  wired on every Bash call. `rtk` remains a dangling entry on the user
  PATH, left for the owner.
- **Ponytail skill deleted** — its headline benchmark was independently
  shown to be an artefact of an unfair baseline.
- **caveman enabled, output-compression half only.** Its memory-file
  compression half is contested by the same paper that validates the
  output half; that half is a separate skill and stays dormant.
- Backups: `~/.claude/CLAUDE.md.bak-2026-09-18`,
  `~/.claude/settings.json.bak-2026-09-18`,
  `~/.claude/settings.json.bak2-2026-09-18`.

## Common misreadings to avoid

- `CLAUDE.md` still reads as though independent review is a hard pre-merge
  gate. Decision D10 overrides it: the OWNER approves; review is advisory.
- `mission.md`'s scope table marks all rule families PROPOSED without the
  deny/warn split. D9 has it: `proof_required` and
  `no_unauthorised_destructive_action` are deny-capable in 1.0;
  `stage_order` and `independence` are warn-only.
- "Required work, not deferred" in `decisions.md` is owed work, not a
  backlog. The owner's rule is that nothing is deferred; Codex under D11
  is the single approved exception.

## Where the assessment stopped

Roughly halfway. Settled: the mission, the quality floor, the tech-stack
evidence, D9-D14. Not assessed: roles and stages (D2/D3 were built without
the adoption check the mission requires), the architecture under D12, the
trial protocol D13 needs, the legacy lift, and the consolidated plan the
owner originally asked for. All are listed as required work.

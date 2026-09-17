# HANDOFF

One page. Read this before any other file when starting a new session on
this repo. See `docs/handoff-protocol.md` for the full protocol this file
follows.

## Start of session

- [ ] Read this whole file.
- [ ] Run the commands in "Re-derive state" below — trust their output,
      not this file's prose (except the "In flight" narrative, which is
      the current plan of record).
- [ ] Confirm which CLI you are (Claude Code or Codex) and work only in
      your lane: see `CLAUDE.md` / `AGENTS.md`.
- [ ] If nothing below is in flight, ENTER PLAN MODE and pick up the next
      unchecked step.

## In flight

The plan, in order. Do not skip a step; do not start step *n+1* before
step *n* is done and proven.

1. **DONE.** This repo stands up as the generic, project-neutral SDLC
   scaffold (code `lwb`): the private `LEAPWare-BuildCraft` repo was
   renamed to `LEAPWare-BuildCraft-legacy` (stays private, untouched)
   to free this name; this repo was scaffolded fresh from the same
   template as `LEAPWare-SessionKeeper`/`LEAPWare-TokenWise`, with every
   subject-specific (rate-limit/runway) reference stripped and a TODO
   placeholder left where real content would have to be invented (see
   `docs/requirements/owner-directives.md`). The bootstrap PR (#1,
   branch `lwb-bootstrap`) squash-merged with 16/16 checks green. This
   repo is **PUBLIC** under Apache-2.0 — everything committed here is
   world-readable, permanently, including history.
2. Once step 1's PR is green and merged: apply the repository ruleset,
   create the two GitHub Apps (`lwb-claude`, `lwb-codex`) from the
   committed manifests in `.github/apps/`, using a browser-enabled
   session. Install each on this repo only. Store each private key in the
   owner's secrets manager, never in the repo. Record App ids in
   `docs/maintainers/github-apps.md` via PR.
2b. **IN PROGRESS.** Owner decisions for step 3 are recorded: all three
   rule families (stage, role, proof) ship in 1.0 **warn-only**, deny
   modes enabled in 1.1 from ledger evidence; stages are legacy's seven
   roles (`design → qa → review → security → delivery → release →
   operations`); role separation is reviewer-independence only (a
   `qa`/`review`/`security` author must not author any earlier stage of
   the same deliverable), policy may tighten never loosen; stage state
   is derived from `proof/*.json` (which already carries `deliverable`,
   `author`, `checked_by`) plus one added `stage` field — no new state
   store, no network from a hook.
3. **Next real step of substance:** the requirements package (per
   `docs/requirements/approach.md`) — this repo's own owner directives,
   gathered fresh, replacing the TODO placeholder in
   `docs/requirements/owner-directives.md` — plus the lift from the
   private `LEAPWare-BuildCraft-legacy` repo (the acceptance checker and
   its tests, and the provenance/vendor pattern), each piece of that lift
   subject to its own origin and licence check before anything from it
   lands here. ENTER PLAN MODE (each CLI in its own lane) for this step;
   present the plan to the owner for approval before building.
4. Every deliverable follows `docs/handoff-protocol.md`: proof record,
   pushed, CI green, alert line `LWB - Alert: <id> DONE ...`.

<!-- lwb-handoff:begin -->

Generated: 2026-09-17 21:23 UTC
main SHA: 31a75abfbc23770b157b804322088130ac62aa28
CLI: claude
Session: requirements-2026-09-17

Open PRs:
#4 chore(deps): bump softprops/action-gh-release from 2 to 3 (dependabot/github_actions/softprops/action-gh-release-3)
#3 chore(deps): bump actions/setup-python from 6 to 7 (dependabot/github_actions/actions/setup-python-7)
#2 chore(deps): bump actions/checkout from 5 to 7 (dependabot/github_actions/actions/checkout-7)

Deliverable proof state (from proof/):
(none yet)

<!-- lwb-handoff:end -->

## Re-derive state

```
git fetch origin
git status
git log --oneline -10
gh pr list --state open
gh run list --limit 10
gh api repos/LEAPWare-Software/LEAPWare-BuildCraft/rulesets
```

`gh` and `git` are the state of record. This file's "In flight" list is
the plan; the commands above are the facts.

## Hard rules

- Work from this repo only; clone fresh on any machine, any OS. No
  dependence on, or leak of, the local environment or a private project
  (directive 8, **SACRED** — see `scripts/lwb_check_env_leak.py`).
- Python 3.10+ standard library only, everywhere in `core/`, `adapters/`,
  and any shipped plugin script.
- The plugin never reads or depends on `CLAUDE.md` or `AGENTS.md` at
  runtime — those are contributor-only docs.
- Any stage/gate state this plugin comes to track is enforced mechanically
  (allow/warn/deny), never by trust.
- No repo settings change, no merge, no force-push, no history rewrite
  without the owner.
- One GitHub App per CLI; no shared credential.

## Traps

- `gh pr list --jq` without `--json` exits 1; use `--json` + `--template`
  or `--jq` with `gh api`.
- A linked worktree's `.git` is a file, not a directory.
- `git diff` omits untracked files; check
  `git ls-files --others --exclude-standard` too.
- Squash-merge only happens through the merge queue — never merge locally
  and push to `main`.
- `scripts/lwb_handoff.py --write` requires `gh` auth for the PR list; it
  degrades to "(unavailable)" rather than failing when `gh` is missing or
  unauthenticated, so a green `--check` does not by itself prove the PR
  list is current — re-read the "Generated" timestamp.

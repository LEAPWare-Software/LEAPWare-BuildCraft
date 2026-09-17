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

1. **IN PROGRESS.** Stand up this repo as the generic, project-neutral
   SDLC scaffold (code `lwb`): the private `LEAPWare-BuildCraft` repo was
   renamed to `LEAPWare-BuildCraft-legacy` (stays private, untouched)
   to free this name; this repo was scaffolded fresh from the same
   template as `LEAPWare-SessionKeeper`/`LEAPWare-TokenWise`, with every
   subject-specific (rate-limit/runway) reference stripped and a TODO
   placeholder left where real content would have to be invented (see
   `docs/requirements/owner-directives.md`). The bootstrap PR (branch
   `lwb-bootstrap`, containing everything — core, adapters, plugins,
   scripts, tests, docs, `.github/`) is open; its number is not yet
   known — read it from `gh pr list` below, not from this prose. Do NOT
   merge it and do NOT apply `.github/rulesets/main.json` until its
   required checks are green (the ruleset names CI job/check contexts
   that only exist once this PR has run).
2. Once step 1's PR is green and merged: apply the repository ruleset,
   create the two GitHub Apps (`lwb-claude`, `lwb-codex`) from the
   committed manifests in `.github/apps/`, using a browser-enabled
   session. Install each on this repo only. Store each private key in the
   owner's secrets manager, never in the repo. Record App ids in
   `docs/maintainers/github-apps.md` via PR.
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

Generated: 2026-09-17 20:53 UTC
main SHA: 521ec0206b6c1468ae97697981202aaa69073fa4
CLI: claude
Session: bootstrap-2026-09-17

Open PRs:
(unavailable: no `gh` auth in this environment, or no open PRs)

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

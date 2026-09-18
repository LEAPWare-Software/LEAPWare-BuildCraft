# Handoff protocol

`HANDOFF.md`, at the repo root, is the single re-derivable state file a
new session reads first. This document is the protocol that keeps it
true. It has no runtime role — the lwb plugin never reads it.

## When to write a handoff

Write (or update) `HANDOFF.md` at each of these points:

1. Before ending any session, whatever the reason.
2. At any rate-limit or context warning from the host CLI.
3. After each deliverable lands (its own Proof of Completion, see below,
   plus an updated "next step" in the "In flight" section).

A handoff is cheap and mechanical (`scripts/lwb_handoff.py --write`); the
cost of skipping one is a session that starts from guesswork instead of
fact.

## What the generated block contains

Between `<!-- lwb-handoff:begin -->` and `<!-- lwb-handoff:end -->` in
`HANDOFF.md`, `scripts/lwb_handoff.py --write` regenerates:

- UTC timestamp of generation.
- CLI name and session id (when the caller supplies them; omitted rather
  than guessed otherwise).
- `main`'s current SHA.
- Open PRs with their CI state.
- Deliverables in flight with their proof state.
- The next step to take.

## Only the block is regenerated

Everything in `HANDOFF.md` outside the begin/end markers — the "In
flight" narrative, "Hard rules", "Traps", the checklist — is prose a
session wrote by hand. `--write` never touches it. If the narrative plan
changes (a step finishes, a new one starts), edit that prose by hand in
the same commit that regenerates the block.

## Size cap

`HANDOFF.md` must stay at or under **3000 bytes** (owner ruling,
2026-09-17). This is not a soft target — `scripts/lwb_handoff.py --check`
fails the build over it. `HANDOFF.md` carries the transition only: where
`main` is, what landed, what is in flight, the next step.

**A cap reached is a signal to move content into `docs/`, never to trim
meaning.** The durable reference below used to live in `HANDOFF.md`; it
moved here when the cap dropped. `--check` asserts these sections still
exist in this file, so trimming the handoff cannot quietly delete the
hard rules.

## Start of session

- [ ] Read `HANDOFF.md`, then this file.
- [ ] Run the "Re-derive state" commands below — trust their output, not
      either file's prose (except `HANDOFF.md`'s "In flight" narrative,
      which is the current plan of record).
- [ ] Confirm which CLI you are (Claude Code or Codex) and work only in
      your lane: see `CLAUDE.md` / `AGENTS.md`.
- [ ] If nothing is in flight, ENTER PLAN MODE and pick up the next
      unchecked step.

## Re-derive state

```
git fetch origin
git status
git log --oneline -10
gh pr list --state open
gh run list --limit 10
gh api repos/LEAPWare-Software/LEAPWare-BuildCraft/rulesets
```

`gh` and `git` are the state of record. `HANDOFF.md`'s "In flight" list is
the plan; the commands above are the facts. Where they disagree, the
commands win and the narrative is corrected in the same session.

## Hard rules

- Work from this repo only; clone fresh on any machine, any OS. No
  dependence on, or leak of, the local environment or a private project
  (directive 8, **SACRED** — see `scripts/lwb_check_env_leak.py`, and set
  `LWB_PRIVATE_NEEDLES` or that check fails as UNCONFIGURED).
- This repo is **PUBLIC** under Apache-2.0. Everything committed is
  world-readable permanently, history included. Never commit a private
  project or org name — supply those to the leak check out of band.
- Python 3.10+ standard library only, everywhere in `core/`, `adapters/`,
  and any shipped plugin script.
- The plugin never reads or depends on `CLAUDE.md` or `AGENTS.md` at
  runtime — those are contributor-only docs.
- Any stage/gate state this plugin tracks is enforced mechanically
  (allow/warn/deny), never by trust.
- No repo settings change, no merge, no force-push, no history rewrite
  without the owner.
- One GitHub App per CLI; no shared credential.
- **No left behinds.** Finishing a task includes deleting what it created
  that is not the deliverable: merged branches **local and remote**,
  worktrees, stashes, scratch scripts, untracked files. A squash-merged
  branch needs `git branch -D`; `-d` refuses it because its commits are
  not ancestors of `main`, and that refusal is not evidence of unlanded
  work. Verify a branch's work actually landed before deleting it —
  compare its tip against the squash commit it produced
  (`git diff --stat <tip> <squash-sha>`), never against current `main`,
  which has moved on. Owner ruling, 2026-09-18.

## Traps

- `gh pr list --jq` without `--json` exits 1; use `--json` + `--template`
  or `--jq` with `gh api`.
- A linked worktree's `.git` is a file, not a directory.
- `git diff` omits untracked files; check
  `git ls-files --others --exclude-standard` too.
- Squash-merge only through the PR; never merge locally and push to `main`.
- `scripts/lwb_handoff.py --write` requires `gh` auth for the PR list; it
  degrades to "(unavailable)" rather than failing when `gh` is missing or
  unauthenticated, so a green `--check` does not by itself prove the PR
  list is current — re-read the "Generated" timestamp.
- Dependabot consumes PR numbers. Any rule keyed to a PR *number* (such as
  the lane bootstrap window) will be eaten by bot PRs opened overnight.
- Human-formatted command output can be condensed into a summary that
  looks complete and is not. `git branch -a` had its remote refs
  collapsed into a single `remote-only (N)` line, which read as "no
  remote branches" — and three merged branches survived a cleanup that
  reported success on the strength of it. For any state that gates a
  decision, use a record-per-line machine form instead:
  `git for-each-ref --format='%(refname)' refs/heads refs/remotes`,
  `git status --porcelain`, `gh ... --json`. A summary that looks
  complete is more dangerous than one that looks broken.
- Stale local branches, stashes and untracked files are invisible to CI:
  it runs on a fresh checkout, so a CI job asserting a clean workspace
  would always pass and prove nothing. This class of debris can only be
  caught at a session boundary — a `Stop`-hook rule or an operator-run
  skill, not a CI check.

## Done means committed and pushed

A handoff is DONE only when it is committed to the branch and pushed to
`origin`. A regenerated `HANDOFF.md` sitting only in a working tree is not
a handoff — the next session (possibly on a different machine) cannot see
it.

## The next session re-derives state, never trusts prose

Every session, CLI, or machine starts by running the commands in
`HANDOFF.md`'s "Re-derive state" section — `git`, `gh` — and treats their
output as fact. The "In flight" narrative is the *plan*; the command
output is the *state*. Where they disagree, the commands win, and the
narrative gets corrected in the same session.

## Proof of Completion

A deliverable is DONE only when: committed, pushed, CI is green on that
push, and a proof record exists (what changed, why, how it was verified —
commit message and/or PR description is sufficient; no separate proof
file is required). Every proven delivery is announced with a line
starting `LWB - Alert: <id> DONE ...` so it is grep-able across a long
session.

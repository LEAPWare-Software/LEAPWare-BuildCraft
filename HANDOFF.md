# HANDOFF

The transition only: where `main` is, what landed, what is in flight, the
next step. Session start, re-derive commands, hard rules and traps live in
`docs/handoff-protocol.md` — read that first, every session.

## In flight

In order. Do not start step *n+1* before step *n* is done and proven.

**THE PLAN IS `docs/requirements/build-plan.md`** -- seven phases,
owner-approved 2026-09-19. Session detail:
`docs/maintainers/session-handoff-2026-09-19.md`. Gate traps:
`docs/maintainers/proof-of-completion-plan.md`.

**THE CONDITION ON EVERY PHASE:** absolutely, positively double-check
that no WORTHY AND VETTED tool already does it before building anything.

1. **DONE: #7-#56** (see generated block below for `main`'s live SHA
   -- do not trust a number here, re-derive). Decisions:
   `docs/requirements/decisions.md` -- READ FIRST, do not re-decide.
2. **THE CLOUD LOOP IS LIVE (D27).** A conductor routine picks work
   every 2h; a separate reviewer routine writes the gating record
   hourly. D27's rule: separate cron entries, no trigger path
   conductor->reviewer -- PROCEDURAL, not mechanical: #27's own
   reviewer was manually fired by its author's session
   (`reviews/27/dispatch-correction.md`); no gate caught it.
3. **1.1 SHIPPED** (`lwb_proof_coverage` + `lwb_proof_integrity` at
   `warn`, via #50, after #49 was re-cut for a bad-identity commit).
   Track A also has many open PRs for 1.2/1.4/1.6/1.7/1.8 and lane
   fixes -- `gh pr list --state open` before starting new work.
4. **1.6:** #52 re-cut as **#53** (bad identity was `bcee47f`, not
   reviewer B's correctly-authored `3056493`). #52 left open. #53's
   `test` job was red repo-wide from an unrelated pre-existing bug
   (`resolve_reviewable_head` needs `--first-parent`, fixed on open
   #63) -- ported onto #53; now waits on a fresh independent review.
5. **BLOCKS 1.0.0:** 0/13 stages, 0 rules armed to deny, 2/8 skills
   working.
6. **DEFECT PATTERN:** "I could not check" must never share a
   representation with "I checked and found nothing". Live in Codex's
   lane. The hook has still never been seen to fire from `hooks.json`.
7. Every deliverable: proof record, pushed, CI green, announced
   `LWB - Alert: <id> DONE ...`.

<!-- lwb-handoff:begin -->

Generated: 2026-09-25 04:23 UTC
main SHA: 0d1be714ac028d9b2204bf997d49296c32378ff1
CLI: claude
Session: session_018EQTARPxaim19t3Rw5dvVJ

Open PRs:
(unavailable: no `gh` auth in this environment, or no open PRs)

Deliverable proof state (from proof/):
25/25 proven
(all proven; none outstanding)

<!-- lwb-handoff:end -->

## Where to look

- Session start, re-derive commands, hard rules, traps →
  `docs/handoff-protocol.md`
- Architecture, policy format → `docs/architecture.md`, `docs/policy.md`
- Session detail, gates that failed, environment changes →
  `docs/maintainers/session-handoff-2026-09-18.md`
- Proof-of-completion plan, open blockers, what it will NOT cover →
  `docs/maintainers/proof-of-completion-plan.md`

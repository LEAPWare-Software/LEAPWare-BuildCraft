# HANDOFF

The transition only: where `main` is, what landed, what is in flight, the
next step. Session start, re-derive commands, hard rules and traps live in
`docs/handoff-protocol.md` — read that first, every session.

## In flight

In order. Do not start step *n+1* before step *n* is done and proven.

**THE PLAN IS `docs/requirements/build-plan.md`** -- seven phases,
owner-approved 2026-09-19. Read it before starting anything. Session
detail: `docs/maintainers/session-handoff-2026-09-19.md`. Gate traps:
`docs/maintainers/proof-of-completion-plan.md`.

**THE CONDITION ON EVERY PHASE:** absolutely, positively double-check
that no WORTHY AND VETTED tool already does it before building anything.

1. **DONE: #7-#27, #31.** Decisions: `docs/requirements/decisions.md`
   -- READ FIRST, do not re-decide. `main`'s tip is #34, NOT green:
   `lwb-proof-coverage` fails (#34 shipped with no proof/34.json, not
   in proof/exempt.json) -- #34's gap. Re-derive branch/PR state per
   `docs/handoff-protocol.md`.
2. **THE CLOUD LOOP IS LIVE (D27).** A conductor routine picks work
   every 2h; a separate reviewer routine writes the gating record
   hourly. D27's rule: separate cron entries, no trigger path
   conductor->reviewer -- PROCEDURAL, not mechanical: #27's own
   reviewer was manually fired by its author's session
   (`reviews/27/dispatch-correction.md`); no gate caught it.
3. **IN FLIGHT, each blocked on a DISAGREE review at its head:**
   #35 (this PR -- re-cuts #30, dead: its commits fail commit-identity
   permanently and force-push can't fix them; do not touch #30), #29
   (cloud-only runbook; also conflicts with main), #32 (correction to
   #27's review record). Plan, not fact -- re-derive every SHA.
4. **WHAT BLOCKS 1.0.0.** 0 of 13 stages enforced, 2 rules shipped,
   0 armed to deny, 2 of 8 skills working. **A consuming repo installs
   `lwb` and gets a no-op.** Phase 1 is `lwbpoce`.
5. **DEFECT PATTERN:** "I could not check" must never share a
   representation with "I checked and found nothing". Live in Codex's
   lane. The hook has still never been seen to fire from `hooks.json`.
6. Every deliverable: proof record, pushed, CI green, announced
   `LWB - Alert: <id> DONE ...`.

<!-- lwb-handoff:begin -->

Generated: 2026-09-19 17:00 UTC
main SHA: bfe850796969980545811e1ffa551b9143965faf
CLI: claude
Session: conductor-track-a-01PDRLaG5

Open PRs:
(unavailable: no `gh` auth in this environment, or no open PRs)

Deliverable proof state (from proof/):
21/21 proven
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

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

1. **DONE: #7-#39, #50.** Decisions: `docs/requirements/decisions.md`
   -- READ FIRST, do not re-decide. Re-derive branch/PR state per
   `docs/handoff-protocol.md`; it drifts fast here.
2. **THE CLOUD LOOP IS LIVE (D27).** A conductor routine picks work
   every 2h; a separate reviewer routine writes the gating record
   hourly. D27's rule: separate cron entries, no trigger path
   conductor->reviewer -- PROCEDURAL, not mechanical: #27's own
   reviewer was manually fired by its author's session
   (`reviews/27/dispatch-correction.md`); no gate caught it.
3. **IN FLIGHT:** #51 (item 1.2, `deny` fails closed on unreadable
   git). #56 landed (lwb_lanes stale-veto + merge-first-parent fix +
   identity hook) -- it changes `resolve_reviewable_head`, so merging
   main into #51 stales its AGREE records; a fresh review is expected
   next, not a defect. Re-derive dead/live PR state per
   `docs/handoff-protocol.md`; it drifts fast here.
4. **WHAT BLOCKS 1.0.0.** 0 of 13 stages enforced, 4 rules shipped,
   0 armed to deny, 2 of 8 skills working. **A consuming repo installs
   `lwb` and gets a no-op.** Phase 1 is `lwbpoce`.
5. **DEFECT PATTERN:** "I could not check" must never share a
   representation with "I checked and found nothing". Live in Codex's
   lane. The hook has still never been seen to fire from `hooks.json`.
6. Every deliverable: proof record, pushed, CI green, announced
   `LWB - Alert: <id> DONE ...`.

<!-- lwb-handoff:begin -->

Generated: 2026-09-25 03:13 UTC
main SHA: 0d1be714ac028d9b2204bf997d49296c32378ff1
CLI: claude
Session: 01oyCUXLqcRyXy8deLZYtH

Open PRs:
(unavailable: no `gh` auth in this environment, or no open PRs)

Deliverable proof state (from proof/):
24/24 proven
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

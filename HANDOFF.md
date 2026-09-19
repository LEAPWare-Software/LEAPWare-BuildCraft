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

1. **DONE: #7-#27, #31.** `main` green. Decisions:
   `docs/requirements/decisions.md` -- READ FIRST, do not re-decide.
   Branch tips and PR state are not written here; re-derive per
   `docs/handoff-protocol.md`.
2. **THE CLOUD LOOP IS LIVE (D27).** A conductor routine picks work
   every 2h; a separate reviewer routine writes the gating record
   hourly. No routine can create a routine, so a conductor CANNOT
   dispatch its reviewer -- independence is structural.
3. **IN FLIGHT, each blocked on a DISAGREE review at its current
   head:** #30 (this PR -- plan + D21-D27 onto main, which the
   conductor reads), #29 (cloud-only runbook; also conflicts with
   main), #32 (correction to #27's review record). This list is the
   plan, not the fact -- re-derive every SHA per
   `docs/handoff-protocol.md`.
4. **WHAT BLOCKS 1.0.0.** 0 of 13 stages enforced, 2 rules shipped,
   0 armed to deny, 2 of 8 skills working. **A consuming repo installs
   `lwb` and gets a no-op.** Phase 1 is `lwbpoce`.
5. **DEFECT PATTERN:** "I could not check" must never share a
   representation with "I checked and found nothing". Live in Codex's
   lane. The hook has still never been seen to fire from `hooks.json`.
6. Every deliverable: proof record, pushed, CI green, announced
   `LWB - Alert: <id> DONE ...`.

<!-- lwb-handoff:begin -->

Generated: 2026-09-19 15:22 UTC
main SHA: de27f7230da32ccdeb25374781f81d60ad5e9940
CLI: unknown
Session: unknown

Open PRs:
#32 #27's review record claims a dispatch that did not happen (lwb-correct-27-dispatch)
#30 The plan and the decisions the cloud routines read — they are not on main (lwb-capture-d21-d22)
#29 Cloud-only operation: the protocol, the roles, and the merge path that was broken for a routine (cloud/runbook)

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

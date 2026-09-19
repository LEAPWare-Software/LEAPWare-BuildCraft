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

1. **DONE: #17-#27.** `main` green. Decisions:
   `docs/requirements/decisions.md` -- READ FIRST, do not re-decide.
2. **THE CLOUD LOOP IS LIVE (D27).** A conductor routine picks work
   every 2h; a separate reviewer routine writes the gating record
   hourly. No routine can create a routine, so a conductor CANNOT
   dispatch its reviewer -- independence is structural. #27 landed on a
   routine's record. Same account: separation of dispatch and context,
   NOT of interest.
3. **IN FLIGHT.** #30 (plan + D21-D27 onto main, which the conductor
   reads), #31 (Actions merge path, re-cut after `.claude/` paths
   killed #28), #29 (runbook, routine specs, `.claude/` lane fix). Each
   needs `proof/<pr>.json` AND a review record. Re-derive every SHA.
4. **WHAT BLOCKS 1.0.0.** 0 of 13 stages enforced, 2 rules shipped,
   **0 armed to deny**, 2 of 8 skills working. **A consuming repo
   installs `lwb` and gets a no-op.** Phase 1 is `lwbpoce`.
5. **DEFECT PATTERN:** "I could not check" must never share a
   representation with "I checked and found nothing". Live in Codex's
   lane. The hook has still never been seen to fire from `hooks.json`.
6. Every deliverable: proof record, pushed, CI green, announced
   `LWB - Alert: <id> DONE ...`.

<!-- lwb-handoff:begin -->

Generated: 2026-09-19 14:20 UTC
main SHA: f9b4deadbb441f0c1046a0d73b0434424f1cf13c
CLI: unknown
Session: unknown

Open PRs:
#31 Re-cut the cloud merge path onto a branch the lane gate can pass (supersedes #28) (lwb-cloud-autoqueue-v2)
#30 The plan and the decisions the cloud routines read — they are not on main (lwb-capture-d21-d22)
#29 Cloud-only operation: the protocol, the roles, and the merge path that was broken for a routine (cloud/runbook)

Deliverable proof state (from proof/):
18/18 proven
(all proven; none outstanding)

<!-- lwb-handoff:end -->

## Where to look

- Session start, re-derive commands, hard rules, traps →
  `docs/handoff-protocol.md`
- Architecture, policy format → `docs/architecture.md`, `docs/policy.md`
- Session detail, gates that failed →
  `docs/maintainers/session-handoff-2026-09-19.md`
- Proof-of-completion plan, open blockers, what it will NOT cover →
  `docs/maintainers/proof-of-completion-plan.md`

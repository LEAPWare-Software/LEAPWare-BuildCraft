# HANDOFF

The transition only: where `main` is, what landed, what is in flight, the
next step. Session start, re-derive commands, hard rules and traps live in
`docs/handoff-protocol.md` — read that first, every session.

## In flight

In order. Do not start step *n+1* before step *n* is done and proven.

Detail for every item: `docs/maintainers/proof-of-completion-plan.md`.
Read it before touching a gate.

1. **DONE: #17-#27.** `main` green. Repo is **PUBLIC** (Apache-2.0):
   every commit world-readable, forever. Decisions:
   `docs/requirements/decisions.md` -- READ FIRST, do not re-decide.
2. **THE CLOUD LOOP IS LIVE (D27).** A conductor picks work every 2h;
   two reviewer routines write the gating records hourly, oldest-first
   and newest-first; a watchdog reports to ledger issue #33. No routine
   can create a routine, so a conductor CANNOT dispatch its reviewer --
   independence is structural, not promised. Same account: separation of
   dispatch and context, NOT of interest.
3. **IN FLIGHT.** #29 (runbook, routine specs, `.claude/` lane fix),
   #30 (plan + D21-D27 onto main), #31 (Actions merge path), #32 (the
   #27 provenance correction). Each needs `proof/<pr>.json` AND a review
   record naming its CURRENT head. Re-derive every SHA.
4. **WHAT BLOCKS 1.0.0.** 0 of 13 stages enforced, 2 rules shipped,
   **0 armed to deny**, 4 skills. **A consuming repo installs `lwb` and
   gets a no-op.** Phase 1 is `lwbpoce`.
5. **TWO KNOWN HOLES, both measured by cloud reviewers, neither fixed:**
   a `reviews/`-or-`proof/`-only PR bypasses the review gate with
   respect to its own content; and `reviewer_was_dispatched_by_author`
   is advisory -- `true` prints a NOTICE and still passes.
6. Every deliverable: proof record, pushed, CI green, announced
   `LWB - Alert: <id> DONE ...`.

<!-- lwb-handoff:begin -->

Generated: 2026-09-19 15:06 UTC
main SHA: f9b4deadbb441f0c1046a0d73b0434424f1cf13c
CLI: unknown
Session: unknown

Open PRs:
#32 #27's review record claims a dispatch that did not happen (lwb-correct-27-dispatch)
#31 Re-cut the cloud merge path onto a branch the lane gate can pass (supersedes #28) (lwb-cloud-autoqueue-v2)
#30 The plan and the decisions the cloud routines read — they are not on main (lwb-capture-d21-d22)
#29 Cloud-only operation: the protocol, the roles, and the merge path that was broken for a routine (cloud/runbook)

Deliverable proof state (from proof/):
20/20 proven
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

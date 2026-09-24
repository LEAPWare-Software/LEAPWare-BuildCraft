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
3. **IN FLIGHT:** #39 (this PR -- re-cuts dead #38/#37/#35/#30, don't
   touch any). Segment-collision gate defect fixed (author id renamed);
   blocked only on `lwb-lanes`: 0 reviews in reviews/39/ -- needs a fresh
   review, not an owner call. #29 (runbook, conflicts w/ main), #32 (#27
   correction). Re-derive SHAs.
4. **WHAT BLOCKS 1.0.0.** 0 of 13 stages enforced, 2 rules shipped,
   0 armed to deny, 2 of 8 skills working. **A consuming repo installs
   `lwb` and gets a no-op.** Phase 1 is `lwbpoce`.
5. **DEFECT PATTERN:** "I could not check" must never share a
   representation with "I checked and found nothing". Live in Codex's
   lane. The hook has still never been seen to fire from `hooks.json`.
6. Every deliverable: proof record, pushed, CI green, announced
   `LWB - Alert: <id> DONE ...`.

<!-- lwb-handoff:begin -->

Generated: 2026-09-20 04:07 UTC
main SHA: e5f29bfaccec90199f983b778c1d7689b8c24d33
CLI: unknown
Session: unknown

Open PRs:
#44 fix(cloud): auto-queue's trigger has fired zero times (lwb-autoqueue-trigger)
#43 Re-cut #42 to fix a wrong-identity commit (supersedes #42) (lwb-correct-27-dispatch-v4)
#40 Fix lane-collision false positive and asymmetric record-only exemption (owner-directed) (fix/lane-collision-and-identity-record-exemption)

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

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

1. **STANDING BY.** D21-D26 and the build plan are committed LOCALLY and
   NOT PUSHED on `lwb-capture-d21-d22`. Pushing opens a PR. Owner's call.
2. **DONE.** Scaffold, ruleset, mission, proof-of-completion in CI
   (#17-#26). `main` green. Decisions:
   `docs/requirements/decisions.md` -- READ FIRST, do not re-decide.
3. **IN FLIGHT: PR #27, NOT NEARLY DONE.** TWO DISAGREE verdicts;
   the second found FOUR MORE blockers. A CLOUD agent is fixing them and
   pushes itself, so **do not assume a head SHA -- re-derive**. An hourly
   cloud watcher reviews each new head and publishes to
   `LEAPWare-ShellUX`, branch `reviews/buildcraft`,
   `reviews/buildcraft/pr27-<full-head-sha>.md`. **That branch is the
   source of truth.** File the newest verbatim into `reviews/27/`, then
   merge only on AGREE. Detail: session handoff.
4. **WHAT BLOCKS 1.0.0 -- not a gate fix.** 0 of 13 stages enforced,
   2 rules shipped, **0 armed to deny**, 2 of 8 skills working, no
   adoption register. **A consuming repo installs `lwb` and gets a
   no-op.** Phase 1 is `lwbpoce`, internal AND external.
5. **DEFECT PATTERN, 3x in 3 layers:** "I could not check" must never
   share a representation with "I checked and found nothing". Still live
   in Codex's lane.
6. **One reviewer identity = single point of failure.** Item 1.7.
7. **The hook has never been seen to fire from `hooks.json`.** Item 1.8.
8. Every deliverable: proof record, pushed, CI green, announced
   `LWB - Alert: <id> DONE ...`.

<!-- lwb-handoff:begin -->

Generated: 2026-09-19 09:32 UTC
main SHA: 55f38ae1c46b5e8fa06d25eb9ac6887fc98000cf
CLI: claude
Session: goal-1.0.0

Open PRs:
#26 lwb_proof_required — the first rule that ships, and the first that can deny (lwb-ship-proof-rule)

Deliverable proof state (from proof/):
18/18 proven
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

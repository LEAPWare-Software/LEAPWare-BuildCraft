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
   #30 (plan + D21-D27 onto main), #31 (Actions merge path). #32 (the #27
   provenance correction) is PERMANENTLY BLOCKED -- six DISAGREE reviewer
   records from six one-shot identities that no longer exist to update
   them, a stale HANDOFF.md baked into an old commit, and a leaked
   private domain unrepairable without a force-push -- and is superseded
   by a re-cut PR carrying only its four content commits. #32 itself is
   left open, commented as superseded, not closed by this session. Each
   open item needs `proof/<pr>.json` AND a review record naming its
   CURRENT head. Re-derive every SHA.
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

Generated: 2026-09-19 20:21 UTC
main SHA: bfe850796969980545811e1ffa551b9143965faf
CLI: claude
Session: session_01EkvcWAEAV2sJYoN51CPrTF

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

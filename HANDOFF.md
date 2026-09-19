# HANDOFF

The transition only: where `main` is, what landed, what is in flight, the
next step. Session start, re-derive commands, hard rules and traps live in
`docs/handoff-protocol.md` — read that first, every session.

## In flight

In order. Do not start step *n+1* before step *n* is done and proven.

1. **DONE.** SDLC scaffold (`lwb`) up. Repo is **PUBLIC** (Apache-2.0):
   everything committed is world-readable, history included.
2. **DONE; GitHub Apps DEFERRED.** Ruleset `main` (23627212) active. See
   `docs/requirements/decisions.md` for both.
3. **DONE. Mission landed.** `docs/requirements/mission.md` carries the
   owner-approved mission. The numbered decisions and the open-items list
   are in `docs/requirements/decisions.md` -- READ IT FIRST; do not
   re-decide settled questions. Environment changes this session: D14.
   Branch tips, counts and PR state are NOT written here -- they rot in
   minutes. Re-derive per `docs/handoff-protocol.md`; the block below is
   a timestamped snapshot, not the truth.
4. **IN FLIGHT. Proof of completion made mechanical**, in five small PRs
   -- one big one is what killed #13 and #14. Two adversarial audit
   rounds found 13 blockers; the open ones, the five-PR split and the
   list of what this will NOT cover are in
   `docs/maintainers/proof-of-completion-plan.md`. Read it before
   touching any gate.
5. Every deliverable: proof record, pushed, CI green, announced
   `LWB - Alert: <id> DONE ...`.

<!-- lwb-handoff:begin -->

Generated: 2026-09-19 02:59 UTC
main SHA: 39c951b4dd49c49f5b399eb08ab58798747889ee
CLI: claude
Session: goal-1.0.0

Open PRs:
#19 A parseable reviewer identity, and an honest admission it is not independence (lwb-review-identity)

Deliverable proof state (from proof/):
11/11 proven
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

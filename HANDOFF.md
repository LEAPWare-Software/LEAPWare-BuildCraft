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
3. **DONE. Mission landed.** Decisions and open items:
   `docs/requirements/decisions.md` -- READ IT FIRST, do not re-decide.
   Branch tips, counts and PR state are NOT written here; they rot in
   minutes. Re-derive per `docs/handoff-protocol.md`.
4. **Proof of completion: four PRs landed, one BLOCKED.** Digests are
   re-executed and compared in CI, report-only. Read
   `docs/maintainers/proof-of-completion-plan.md` before touching a gate.
5. **BLOCKED, needs the owner. PR #21 cannot satisfy its own
   independent-review gate** -- see D20: a session cannot produce an
   independent reviewer identity, because none exists to produce. Work
   complete, process requirement unmet. Owner's choice: a review from a
   GENUINELY SEPARATE session, or merge with the non-independence
   recorded. Do NOT relabel an identifier.
6. **AT SESSION START, before anything: verify the shipped hook fires.**
   `hooks.json` uses `"matcher": "Agent"`, never confirmed against a live
   tool name. Register a marker hook, START A NEW SESSION, dispatch a
   subagent, check the marker; repeat for `"Task"`. A mid-session edit is
   never read -- measured. If neither fires, the only hook this product
   ships has never run.
7. **Then:** make re-execution blocking (only after a Linux runner shows
   digests reproducing); close the fork gap (no secrets on a fork, so no
   outside PR can go green while `CONTRIBUTING.md` says otherwise);
   install the plugin in this repo.
8. Every deliverable: proof record, pushed, CI green, announced
   `LWB - Alert: <id> DONE ...`.

<!-- lwb-handoff:begin -->

Generated: 2026-09-19 05:15 UTC
main SHA: f8cb7706488feb29cf6cd2a950a4f82f3dd879b7
CLI: claude
Session: goal-1.0.0

Open PRs:
#21 CI re-executes verifiable commands — and it caught main on its first run (lwb-reexecute-digests)

Deliverable proof state (from proof/):
13/13 proven
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

# HANDOFF

The transition only: where `main` is, what landed, what is in flight, the
next step. Session start, re-derive commands, hard rules and traps live in
`docs/handoff-protocol.md` — read that first, every session.

## In flight

In order. Do not start step *n+1* before step *n* is done and proven.

Detail for every item: `docs/maintainers/proof-of-completion-plan.md`.
Read it before touching a gate.

1. **DONE.** Scaffold, ruleset, mission. Repo is **PUBLIC** (Apache-2.0):
   all commits world-readable. Decisions:
   `docs/requirements/decisions.md` -- READ FIRST, do not re-decide.
   Branch tips and PR state are not written here; re-derive per
   `docs/handoff-protocol.md`.
2. **DONE. Proof of completion in CI: #17-#22.** `main` green.
3. **IN FLIGHT:** #23 re-execute hardening, #24 open-PR post-merge. Both
   carry an independent AGREE.
4. **WHAT ACTUALLY BLOCKS 1.0.0 -- not a gate fix.** Version **0.1.0**,
   zero tags, no release ever run; `core/lwb_core/rules/` holds ONE
   rule, a self-declared no-op; every gate is a `scripts/` file wired to
   THIS repo's CI. **A consuming repo installs `lwb` and gets a no-op.**
   Plan doc, "1.0.0 readiness".
5. **SETTLE FIRST -- touches the owner's permission prompts.** The lane
   hook returns explicit `"permissionDecision": "allow"` for every edit
   it does not deny, which may suppress the normal prompt. PLAUSIBLE.
6. **Lane guard is a NUDGE by design**, so the ungated `Bash` path is
   not a broken premise. Two real defects: a worktree inside the
   checkout is denied wrongly, one outside is never checked.
7. **The shipped hook has never been seen to fire** (`"matcher":
   "Agent"`). Needs a NEW session, marker registered BEFORE start.
   The *lane* hook does fire and deny, so the mechanism works.
8. **Then:** re-execution blocking; the fork gap; install the plugin
   here.
9. Every deliverable: proof record, pushed, CI green, announced
   `LWB - Alert: <id> DONE ...`.

<!-- lwb-handoff:begin -->

Generated: 2026-09-20 03:54 UTC
main SHA: bfe850796969980545811e1ffa551b9143965faf
CLI: unknown
Session: unknown

Open PRs:
#43 Re-cut #42 to fix a wrong-identity commit (supersedes #42) (lwb-correct-27-dispatch-v4)
#40 Fix lane-collision false positive and asymmetric record-only exemption (owner-directed) (fix/lane-collision-and-identity-record-exemption)

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

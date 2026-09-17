# HANDOFF

The transition only: where `main` is, what landed, what is in flight, the
next step. Session start, re-derive commands, hard rules and traps live in
`docs/handoff-protocol.md` — read that first, every session.

## In flight

In order. Do not start step *n+1* before step *n* is done and proven.

1. **DONE.** This repo stands up as the project-neutral SDLC scaffold
   (`lwb`). PR #1 squash-merged, 16/16 green. The repo is **PUBLIC** under
   Apache-2.0: everything committed is world-readable permanently, history
   included.
2. **Apply the repository ruleset; create the two GitHub Apps**
   (`lwb-claude`, `lwb-codex`) from `.github/apps/`, in a browser session.
   Install on this repo only; each private key goes to the owner's secrets
   manager, never the repo. Record App ids in
   `docs/maintainers/github-apps.md` via PR.
3. **The requirements package**, per `docs/requirements/approach.md`,
   replacing the TODO placeholder in
   `docs/requirements/owner-directives.md`. Owner decisions recorded: all
   three rule families (stage, role, proof) ship in 1.0 **warn-only**, deny
   modes from 1.1 on ledger evidence; stages are `design → qa → review →
   security → delivery → release → operations`; role separation is
   reviewer-independence only (a `qa`/`review`/`security` author may not
   have authored an earlier stage of the same deliverable), and policy may
   tighten it, never loosen it; stage state derives from `proof/*.json`
   plus one added `stage` field — no new state store, no network in a hook.
   Then the lift from the private legacy repo (acceptance checker and its
   tests, provenance/vendor pattern), each piece origin- and
   licence-checked before it lands.
4. Every deliverable: proof record, pushed, CI green, announced
   `LWB - Alert: <id> DONE ...`.

<!-- lwb-handoff:begin -->

Generated: 2026-09-17 21:35 UTC
main SHA: 31a75abfbc23770b157b804322088130ac62aa28
CLI: claude
Session: requirements-2026-09-17

Open PRs:
#5 Arm directive 8's private-name gate; make tests/ a shared lane (lwb-leak-gate-handoff)
#4 chore(deps): bump softprops/action-gh-release from 2 to 3 (dependabot/github_actions/softprops/action-gh-release-3)
#3 chore(deps): bump actions/setup-python from 6 to 7 (dependabot/github_actions/actions/setup-python-7)
#2 chore(deps): bump actions/checkout from 5 to 7 (dependabot/github_actions/actions/checkout-7)

Deliverable proof state (from proof/):
(none yet)

<!-- lwb-handoff:end -->

## Where to look

- Session start, re-derive commands, hard rules, traps →
  `docs/handoff-protocol.md`
- Pure core, adapters, lanes, fail-open layers → `docs/architecture.md`
- Policy file format and mode semantics → `docs/policy.md`

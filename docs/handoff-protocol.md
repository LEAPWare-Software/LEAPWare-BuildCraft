# Handoff protocol

`HANDOFF.md`, at the repo root, is the single re-derivable state file a
new session reads first. This document is the protocol that keeps it
true. It has no runtime role — the lwb plugin never reads it.

## When to write a handoff

Write (or update) `HANDOFF.md` at each of these points:

1. Before ending any session, whatever the reason.
2. At any rate-limit or context warning from the host CLI.
3. After each deliverable lands (its own Proof of Completion, see below,
   plus an updated "next step" in the "In flight" section).

A handoff is cheap and mechanical (`scripts/lwb_handoff.py --write`); the
cost of skipping one is a session that starts from guesswork instead of
fact.

## What the generated block contains

Between `<!-- lwb-handoff:begin -->` and `<!-- lwb-handoff:end -->` in
`HANDOFF.md`, `scripts/lwb_handoff.py --write` regenerates:

- UTC timestamp of generation.
- CLI name and session id (when the caller supplies them; omitted rather
  than guessed otherwise).
- `main`'s current SHA.
- Open PRs with their CI state.
- Deliverables in flight with their proof state.
- The next step to take.

## Only the block is regenerated

Everything in `HANDOFF.md` outside the begin/end markers — the "In
flight" narrative, "Hard rules", "Traps", the checklist — is prose a
session wrote by hand. `--write` never touches it. If the narrative plan
changes (a step finishes, a new one starts), edit that prose by hand in
the same commit that regenerates the block.

## Size cap

`HANDOFF.md` must stay at or under **6000 bytes**. This is not a soft
target — `scripts/lwb_handoff.py --check` fails the build over it. A
one-page handoff that nobody reads in full is worse than no handoff;
trim prose before growing the cap.

## Done means committed and pushed

A handoff is DONE only when it is committed to the branch and pushed to
`origin`. A regenerated `HANDOFF.md` sitting only in a working tree is not
a handoff — the next session (possibly on a different machine) cannot see
it.

## The next session re-derives state, never trusts prose

Every session, CLI, or machine starts by running the commands in
`HANDOFF.md`'s "Re-derive state" section — `git`, `gh` — and treats their
output as fact. The "In flight" narrative is the *plan*; the command
output is the *state*. Where they disagree, the commands win, and the
narrative gets corrected in the same session.

## Proof of Completion

A deliverable is DONE only when: committed, pushed, CI is green on that
push, and a proof record exists (what changed, why, how it was verified —
commit message and/or PR description is sufficient; no separate proof
file is required). Every proven delivery is announced with a line
starting `LWB - Alert: <id> DONE ...` so it is grep-able across a long
session.

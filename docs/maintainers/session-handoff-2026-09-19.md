# Session handoff — 2026-09-19

Written at the owner's instruction at the end of the session that produced
`docs/requirements/build-plan.md`. Read that plan first; this document is
what a next session needs that the plan does not say.

## The one correction that matters most

**Everything built before this session was the EVIDENCE layer, and almost
none of it ships.** The owner had to say so directly, twice, because the
PR titles said otherwise: *"the first rule that ships, and the first that
can deny"*, *"a blocking re-execute gate"*. A reader skimming those and a
green ledger would conclude BuildCraft is a working quality gate. It is
not. `HANDOFF.md` has said the true thing all along, in its own words: **a
consuming repo installs `lwb` and gets a no-op.**

The audit that followed, measured not asserted:

| unit | planned | built |
|---|---|---|
| stages enforced | 13 | 0 |
| rules shipped in the plugin | ~10 | 2 (one no-op, one warn) |
| rules armed to deny | 2 | **0** |
| working skills | 8 | 2 |
| adoption register entries | 8 surveyed | **0** |

A next session that reports progress should state which side of the
internal/shipping line it is on. Every gate in `scripts/` guards *this
repository's own contributions* and travels nowhere.

## What was actually decided (D21-D26)

Six decisions, all owner-made, all in `docs/requirements/decisions.md`:

- **D21** trial the adoptable components before building more rules.
- **D22** 1.0.0 requires lwb driving an SDLC in a REAL repo. Demo
  explicitly rejected.
- **D23** the thirteen stages — **this closed required-work item 8**,
  which had been open since D15 declared the old seven superseded and did
  not do the rewrite.
- **D24** acceptance criteria anchored to GitHub's clock. Closes the
  design gap in quality-floor item **1**, the floor's first item, which
  had no mechanical check and no design.
- **D25** efficiency claims are order-of-magnitude only.
- **D26** SessionKeeper or Pulse first, ShellUX for the real bar.

`docs/requirements/build-plan.md` **closes required-work item 6**, the
consolidated plan, open since 2026-09-18.

## The defect pattern this session found three times

In three different layers, the same shape:

1. `core/lwb_core/engine.py` — a caught rule exception went into
   `findings` but never `warnings`, and the hook's reason is built only
   from `warnings`. **A rule crashing on every event was indistinguishable
   from a rule that found nothing wrong.** Live in every build we had ever
   produced.
2. `adapters/claude/repo_facts.py` raising — hook returned `allow` with
   only the version line.
3. Bundled policy unreadable — `allow` with **no reason at all**.

All three: exit 0, no test covering them, each found by an independent
reviewer deliberately breaking something rather than by reading.

**The rule, which belongs in code and not only here:** *"I checked and
found nothing"* and *"I could not check"* must never share a
representation. Failing open is deliberate in this product; failing
**silent** is the defect. A fourth instance will appear unless a test
enforces it.

**Known, unfixed, flagged rather than left quiet:** the identical
policy-unreadable defect exists in `plugins/codex/lwb/bin/lwb_hook.py`.
That is Codex's lane and was not edited.

## The review bottleneck, and why item 1.7 exists

PR #27 was code-complete and could not land, because the repository had
**exactly one reachable independent reviewer identity** and that peer
session had been paused by its own owner. Correctness was irrelevant.

Two reviewers became reachable within the hour once the owner said to fix
it, and **the second immediately found defects the first had not** —
including a gate that reported green for a plugin that could never fire in
a real session, because it ran the hook with a 30-second timeout while
`hooks.json` declares 10.

Two lessons for a next session. First, one reviewer identity is a single
point of failure and the plan now carries an item to fix it. Second, the
sharpest finding of the day came from comparing **what code reads from a
config object against what it ignores in the same object** — we read
`command` from a hooks.json entry to avoid hardcoding it, then ignored the
`timeout` sitting beside it.

## State at handoff

**DO NOT TRUST ANY SHA IN THIS DOCUMENT. RE-DERIVE.** An earlier version
of this section pinned `main` and PR #27 to specific commits; both were
stale within minutes, in a file no gate protects. That is this
repository's signature defect, written into the handoff that warns about
it. Re-derive per `docs/handoff-protocol.md`.

- `main` -- re-derive. It was green at the time of writing.
- **PR #27 IS NOT NEARLY DONE.** It carries **TWO DISAGREE verdicts**.
  The first round's three findings were fixed. The SECOND review then
  found **four more blockers**, and the lead one was a false claim in the
  author's own commit: a timeout fix was applied to
  `lwb_check_foreign_repo.py` and declared repo-wide in the commit
  message, while the sibling `scripts/lwb_check_hook_launch.py` kept the
  identical defect -- so the `lwb-portable` CI job reports green for a
  plugin Claude Code would kill mid-run in any real session. The other
  three: nothing enforces the new behaviour by test; `Policy.degraded` is
  computed and discarded two lines from the fix; and the repo-facts path
  that was patched barely occurs while the reachable ones stay conflated.
- **A CLOUD AGENT is fixing all four.** It commits and pushes itself, so
  the head will move with no local session running. An hourly cloud
  watcher reviews every new head and publishes to
  `LEAPWare-Software/LEAPWare-ShellUX`, branch `reviews/buildcraft`, path
  `reviews/buildcraft/pr27-<full-head-sha>.md`. **That branch is the
  source of truth** and does not depend on any session staying alive.
  Read the newest file there, file it into `reviews/27/` verbatim, then
  merge -- only if it says AGREE.
- **D21-D26 and the build plan are PUSHED** on branch
  `lwb-capture-d21-d22`. No PR was opened for them; that decision is the
  owner's and is still open.

## What a next session must not do

- Do not report `scripts/` gates as product progress. They guard us only.
- Do not treat a version number as a reason to release. A goal-tracker
  reporting 0.1.0 as unmet prompted a 1.0.0 release question that should
  never have been asked; the owner's reply was *"I am unclear why you
  think we are at a 1.0.0 release level"*, and the audit proved him right.
- Do not fabricate or relabel a reviewer identity to pass the lane gate.
- Do not build anything before checking, absolutely and positively, that
  no worthy vetted tool already does it. That is the owner's condition on
  every phase of the plan.
- Do not pin a SHA, count or PR state in prose. The generated block at
  the bottom of `HANDOFF.md` is gated by
  `scripts/lwb_check_state_claims.py`; the prose above it is NOT, and an
  earlier version of this very document pinned two SHAs that were stale
  within minutes.

## Loose end found in the audit, not fixed

`plugins/claude/lwb/skills/` contains **five** directories, not four:
`lwb-config`, `lwb-handoff`, `lwb-report`, `lwb-status`, and a nested
**`skills/skills/`**. The fifth is either junk or a packaging fault, and
it ships. Nobody has looked at it. It was found by auditing a count the
author had stated without verifying.

## The next step

Phase 1 of `docs/requirements/build-plan.md`, item by item — but only
after the owner clears the standing-by state. Nothing in the plan is
authorised to start yet.

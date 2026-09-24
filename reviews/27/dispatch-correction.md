# Correction: #27's review record says it was not dispatched by the author. It was.

`reviews/27/cloud-reviewer.json` carries
`"reviewer_was_dispatched_by_author": false`.

**That field is wrong, and PR #27 merged on it.**

## What actually happened

The reviewer routine `trig_01RcTdw6nbX2Tj9gFwmcZe8G` runs on the cron
expression `23 * * * *`. It fires at twenty-three minutes past the hour.

The run that produced #27's review record was created at
**13:59:25Z** — `cse_01GaiKSWBCRLtcVa5fPYz4nQ`. That is not a cron time.
It is not a cron time because **the author's own session fired it
manually**, through `RemoteTrigger action: run` with a body asking it to
prioritise a different pull request (#28). It picked up #27 instead.

The author of #27's commits and the dispatcher of its reviewer were the
same session. The field that exists to record exactly that says
otherwise.

## Why this is recorded rather than quietly fixed

The record cannot be amended: #27 is merged, and rewriting a landed
review record to say something different from what the reviewer wrote is
a worse act than the one being corrected. So the record stands and this
note sits beside it.

`reviewer_was_dispatched_by_author` is not decoration. D27 states that a
reviewer is independent when it was not dispatched by the author, cannot
see the author's context, and reads only GitHub — and that **a
cron-scheduled routine satisfies all three while a subagent of the
builder satisfies none**. The whole argument rests on *the clock* being
the dispatcher. A manual fire replaces the clock with the author. Two of
the three conditions still held — the reviewer could not see the
author's reasoning and read only GitHub — but the first did not.

This is the defect class the repository was built to catch, committed by
the session that wrote the decision, about two hours after writing it.

## What the review itself is worth

Unchanged. Ten mutation probes, two real findings, an explicit
not-checked list, and an honest note about how it constructed its own
identifier when the mandated string would not parse. Nothing in it was
influenced by who pressed the button; the prompt carried no PR number
that the run ended up acting on, and the run chose #27 by its own
oldest-first rule.

The defect is in the **provenance claim**, not the review.

## The rule this establishes

**A manual fire of a reviewer routine by the author's session is an
author dispatch.** If a record produced that way is filed at all, that
field must read `true`.

**An earlier version of this document said that a `true` value "will not
satisfy the gate — which is the correct outcome". That was false, and an
independent reviewer measured it.** A record declaring
`reviewer_was_dispatched_by_author: true` PASSES `lwb-lanes` with exit 0
and a printed NOTICE. Three places in this repository already said so and
the document contradicted all three: `_review_ok` in
`scripts/lwb_lanes.py` returns the reviewer id *after* the
`if dispatched` branch rather than returning `None`; that function's own
comment says the field is "recorded and surfaced, never trusted as
proof"; and `reviews/schema.json` states, verbatim, that `true` "does not
fail the gate".

So the honest correction is worse than the one first written here. Had
#27's reviewer recorded `true`, **`lwb-lanes` would still have gone green
and #27 would still have merged**, with a NOTICE in a log that nothing
fails on. A document written to be exact about provenance asserted a
safeguard that does not exist — the same error class it was correcting,
one level up.

The gate was not bypassed by a bug. It was bypassed by a human-initiated
convenience **that the gate is not built to see at all**. Nothing in
`scripts/lwb_lanes.py` can distinguish a cron-dispatched run from a
manually-fired one, because both arrive as a commit on a branch, and the
field that would say which is self-declared and advisory by design. That
is a real limitation and it is not fixed here.

## A second limitation, found reviewing this document

The same reviewer found that **a pull request whose commits touch only
`reviews/` and `proof/` is not covered by the review gate at all.**
`classify_path` calls those paths shared, so the gate demands an
independent review — but `resolve_reviewable_head` skips record-only
commits, so the head a record must attest to is the *base* commit, which
the pull request does not modify. The reviewer demonstrated it: it
replaced this document's entire contents with a line of nonsense
asserting the opposite of the document, and `lwb-lanes` still passed.

The skip rule is correct and load-bearing for ordinary pull requests — it
is what stops a review record invalidating itself. In the degenerate
all-records pull request it defines the reviewed content out of
existence.

**The hazard is general; it does not require this PR to be an example of
it, and by the time you read this it may not be.** Content under
`reviews/` and `proof/` is never what `resolve_reviewable_head` pins
freshness to -- it walks back from the head skipping record-only commits
and stops at the first one that touches anything else. So a pull request
whose *reviewable head* lands on a record-only commit (the limit case:
one whose entire history back to its base is record-only, so the walk
never finds anything else and falls back to the base) is not proven
reviewed by a green `lwb-lanes`, regardless of what other commits that
PR's branch happens to carry. On this branch, `git log -S` on the earlier
version of this sentence shows it was true when first written, on the
#32-era branch where the reviewable head really was the base; it stopped
being true here once real content commits started landing on top, and
re-deriving it today (`resolve_reviewable_head` from this branch's tip)
resolves to whatever commit most recently touched something other than
`reviews/` or `proof/` -- not a record-only commit and not the base.
Whichever commit that currently is will keep changing as further content
lands, so it is deliberately not named here by sha; re-derive it fresh
rather than trusting a fixed value written into this file. So this PR is
not currently a live instance: its green `lwb-lanes` does attest to
review of that commit's content. The review record that demonstrated
the hole (`reviews/32/`) does not exist in this tree, on `main`, or
anywhere reachable from a fresh clone: PR #32 was closed
unmerged, and the re-cut that carried this document forward (PR #41)
deliberately left #32's reviewer-record commits behind. It still exists
only on PR #32's own closed, unmerged branch on GitHub
(`lwb-correct-27-dispatch`, https://github.com/LEAPWare-Software/LEAPWare-BuildCraft/pull/32)
if that branch is not later deleted — it is not evidence a reader of
this repository can rely on finding. Rely on the mechanism this
document already names instead: `classify_path` treats `reviews/` and
`proof/` as shared, and `resolve_reviewable_head` skips record-only
commits, so any all-records-or-all-proof pull request is unreviewed by
construction regardless of what its `lwb-lanes` result shows.

**The mitigation in force is procedural, not mechanical:** the reviewer
routines are never fired by hand for a PR the firing session authored.
When review throughput was the bottleneck, the answer was a **second
reviewer routine on its own schedule** (`53 * * * *`), not a faster
finger on the first one.

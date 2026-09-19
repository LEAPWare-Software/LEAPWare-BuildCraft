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

**This pull request is itself an instance.** A green `lwb-lanes` here is
not evidence that anything in this file was reviewed. Treat the review
record under `reviews/32/` as the evidence, and read it.

**The mitigation in force is procedural, not mechanical:** the reviewer
routines are never fired by hand for a PR the firing session authored.
When review throughput was the bottleneck, the answer was a **second
reviewer routine on its own schedule** (`53 * * * *`), not a faster
finger on the first one.

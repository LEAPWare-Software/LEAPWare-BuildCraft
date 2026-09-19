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
field must read `true`, which means it will not satisfy the gate — which
is the correct outcome.

The gate was not bypassed by a bug. It was bypassed by a human-initiated
convenience that the gate had no way to see. Nothing in
`scripts/lwb_lanes.py` can distinguish a cron-dispatched run from a
manually-fired one, because both arrive as a commit on a branch. That is
a real limitation and it is not fixed here.

**The mitigation in force is procedural, not mechanical:** the reviewer
routines are never fired by hand for a PR the firing session authored.
When review throughput was the bottleneck, the answer was a **second
reviewer routine on its own schedule** (`53 * * * *`), not a faster
finger on the first one.

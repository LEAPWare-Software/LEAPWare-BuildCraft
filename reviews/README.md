# reviews/

Adversarial cross-CLI review records for a shared-path change, per owner
directive 5 and `scripts/lwb_lanes.py`.

## When a review is required

Any commit (with an `LWB-Agent: claude` or `LWB-Agent: codex` trailer,
never `human`) that touches a shared path — `core/`, `scripts/`, `.github/`,
`docs/`, `proof/`, `reviews/`, `tests/`, `HANDOFF.md`, `AGENTS.md`,
`CLAUDE.md`, `README.md` — needs
`scripts/lwb_lanes.REQUIRED_INDEPENDENT_REVIEWS` (currently **1**) distinct
independent reviewers recorded under `reviews/<pr>/`, each in a record with
`"verdict": "AGREE"` and a `reviewer_id` differing from the commit's
`commit_author_id`, before `scripts/lwb_lanes.py` (the `lwb-lanes` CI job)
passes. Bootstrap exception: the PRs named in `BOOTSTRAP_EXEMPT_PRS`.

**Changed in PR #6 — this used to demand BOTH `claude-cto.json` AND
`codex-cto.json`.** That coupled independence to a CLI *vendor* when the
property that matters is a distinct reviewer *identity* — which this file
already said, three paragraphs down ("two different sessions, not the same
one reviewing itself"). It was also unsatisfiable: one CLI operates this
repo, so from PR #6 every shared-path change would have been unmergeable,
and an unsatisfiable gate is worse than a strict one because it gets routed
around. The filename no longer matters; the identities do. Raise
`REQUIRED_INDEPENDENT_REVIEWS` when a second reviewer identity is routinely
available. This is a change in directive 5's *enforcement*, recorded here
and carried into the requirements package as an owner decision.

## Record shape (see `schema.json`)

```json
{
  "pr": 20,
  "reviewed_commit": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
  "reviewer_agent": "claude",
  "reviewer_id": "cto-opus-b7e2f9a1-2026-09-20",
  "commit_author_agent": "codex",
  "commit_author_id": "worker-sonnet-1c4d8e60-2026-09-19",
  "verdict": "AGREE",
  "reviewer_was_dispatched_by_author": false,
  "notes": "Checked core/lwb_core/rules/new_rule.py against the schema; agrees with the codex worker's read of directive 15."
}
```

`pr: 20` here is `>= scripts/lwb_lanes.REVIEWER_ID_FORMAT_CUTOFF_PR` (19), so both id fields
must parse as `<role>-<model>-<session-token>-<date>` and
`reviewer_was_dispatched_by_author` is required. A record for a PR below 19
is exempt from both and may keep the free-form style records 7-18 already
used.

- The **filename does not matter** and `reviewer_agent` is informational
  (it names who filed the record, not a gate condition). This file used to
  say `reviewer_agent` must match the filename; that check was removed in
  PR #6 along with the per-vendor requirement. `reviews/schema.json` used
  to be loaded by nothing at all, which meant its `enum` on
  `reviewer_agent` (and every other constraint in it) was a description
  with no enforcement behind it — a claim this file made about itself that
  was not true. As of the PR that added this paragraph,
  `scripts/lwb_lanes.py` loads and enforces `schema.json`'s `required`
  fields and its `enum`/`pattern` constraints by hand (this repo is
  stdlib-only, so this is a purpose-built check of the small slice of JSON
  Schema the file actually uses, not a general validator). Two unenforced
  descriptions of the record shape was worse than one; deleting
  `schema.json` was the other option considered and rejected because the
  shape it describes is real and worth checking mechanically, not just
  in prose.
- **KNOWN WEAKNESS, flagged by the independent review of PR #6, MEASURED by
  the PR that added this section:** `reviewer_id` and `commit_author_id`
  are self-attested strings. An audit wrote `reviews/999999/fake.json`
  with two identity strings it invented in the same breath, in the same
  session, and the gate passed — its entire check was
  `reviewer_id != commit_author_id`. Measuring every record that existed
  at the time (`reviews/7` through `reviews/18`, 10 records): **all 10**
  have a `commit_author_id` naming the same session
  (`claude-code-opus5-session-f8da3f9e-...`). Of those, **3 of 10** (PRs
  15, 16, 17) also have a `reviewer_id` visibly naming that same session
  token — a subagent reviewing its own parent session's work, literally
  self-review, and string inequality alone did not catch it because the
  two id *strings* still differed. **6 of 10** (PRs 7-13) have a
  `reviewer_id` carrying a distinct-looking per-dispatch id (e.g.
  `lw-verifier-sonnet-ac5ffd6d6cde8a968-2026-09-18`) for a reviewer that
  was, in fact, still a subagent dispatched by the author's own session —
  a different string hiding the identical relationship. Only **1 of 10**
  (PR 18, `lw-verifier-state-claim-gate-6ad9151`) embeds no session token
  at all, so its relationship to the author's session cannot be read off
  the string either way. In short: **9 of the 10 records this repo had at
  the time were produced by a subagent of the authoring session**, and a
  rule that only rejects a *shared substring* between the two ids (see
  below) would have caught 3 of those 9 and missed the other 6.
- `reviewer_id` and `commit_author_id` are free-form identity strings (a
  session id, a dispatch id — whatever the CLI in question uses to name a
  specific run) and **must differ from each other**: a reviewer may never
  be the same identity as the commit's own author, even when both happen
  to run under the same CLI brand (e.g. a Claude CTO role reviewing a
  Claude implementer's commit — two different sessions, not the same one
  reviewing itself). `scripts/lwb_lanes.py` enforces this by literal string
  inequality; it is on the reviewer to give the two fields genuinely
  distinct values, not merely different-looking ones.
- **The format, required from `scripts/lwb_lanes.REVIEWER_ID_FORMAT_CUTOFF_PR`
  (PR #19) onward:** `<role>-<model>-<session-token>-<date>`, where `role`,
  `model` and `session-token` are each a single dash-free segment and
  `date` is an ISO `YYYY-MM-DD` tail (e.g.
  `verifier-sonnet-a1b2c3d4-2026-09-20`). `reviews/schema.json` no longer
  describes a format nothing enforces — `scripts/lwb_lanes.py` parses both
  ids against this pattern and rejects a record where either one fails to
  parse. Records 7-18 predate this format and stay valid without being
  rewritten to fit it: retroactively editing a historical record to satisfy
  a new validator is falsifying evidence, not honesty.
- **From PR #19 onward, a record whose `reviewer_id` and `commit_author_id`
  share the same `session-token` field is REJECTED** as a self-review — the
  literal case measured above (3 of 10 records). This is a narrower,
  precise version of "same substring": PR #6's naive attempt (reject any
  shared substring) would have flagged every one of the then-16 records,
  because every id happened to end in the same `-2026-09-18` run — longer
  than the 8-character session token it needed to catch. Comparing a
  parsed FIELD instead of the raw string is why the format above exists.
- **What this gate CANNOT do, said plainly so it is never overclaimed
  again:** it cannot tell a genuinely independent reviewer from one that
  merely uses a different-looking dispatch id for the same underlying
  session — that is exactly the 6-of-10 case above, and nothing about a
  parseable format or a distinct session-token field closes it, because a
  session or dispatch can mint an arbitrary new token for every subagent
  it spawns. Two consequences, from PR #19 onward:
  - Every record must carry a required boolean,
    `"reviewer_was_dispatched_by_author"`, self-attested like every other
    identity field here — **not verified, only recorded and surfaced**.
    `scripts/lwb_lanes.py` prints a `NOTICE:` line whenever it is `true`,
    saying the review is not independent and the record is an audit trail
    only. A `true` value does not fail the gate (there is nothing to
    fail it against — the gate cannot establish independence either way),
    but it can never again pass silently as though it proved something it
    did not.
  - Historically (`reviews/7`-`reviews/18`), every commit author in this
    repo's own history has been the *same* session
    (`...-f8da3f9e-...`) and 9 of 10 reviewers were that session's own
    subagents. Watchtower audit B7's consequence still stands: a fresh
    clone cannot resolve any of these identities against anything outside
    this repo, so treat every record here — before and after PR #19 — as
    an audit trail of who *said* they reviewed what, not as proof that an
    independent party did.
- `verdict` is `"AGREE"` or `"DISAGREE"`; only `"AGREE"` satisfies the gate.
- `reviewed_commit` is the sha of the commit the reviewer actually examined.
  A record whose `reviewed_commit` is not a prefix of the current head of the
  branch under review is **STALE** and fails the gate, even if the record is
  otherwise complete, honest, and `verdict: AGREE`. This exists because it
  nearly went wrong: a `reviews/12/` record was a genuine AGREE, from a real
  reviewer identity, over an earlier round of PR #12 — it named 148 tests and
  two changed files. The branch then grew to 154 tests and six files. Keyed
  only to the PR number, that record would have kept satisfying the gate and
  merged code it had never seen, on a verdict never given for that code. A
  record is bound to the commit it reviewed, not just the PR it reviewed it
  under.

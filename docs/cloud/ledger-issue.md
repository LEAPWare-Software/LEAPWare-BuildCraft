# The ledger issue — specification

**This issue has NOT been opened.** Opening it is the owner's action. This
document specifies it so that opening it is a copy-paste, and so that a routine
reading this file knows the protocol before the issue exists.

The ledger is the **only** shared mutable state in the cloud model. There is no
database, no local file, no session memory. If a fact is not on this issue, in
a proof record, in a review record, or in git, it does not exist.

---

## Why an issue and not a file

A file in the repository would need a pull request per update, and every update
would collide with the work it is tracking. An issue is writable by every
routine at once, it has GitHub's own clock on every comment, and a human can
read it without a checkout. ShellUX's #187 established the shape; this is the
same shape with BuildCraft's vocabulary and gates.

---

## Issue metadata

| field | value |
|---|---|
| title | `Cloud ledger: autonomous run status (read me)` |
| labels | `cloud-ledger` — create it; nothing keys on it, it is for humans |
| assignee | none |
| milestone | none |
| state | open, permanently. **Never close it.** |

Record its number in `docs/cloud/runbook.md` section 4 in the same pull request
that opens it, so a routine can find it without searching.

---

## Body template

The **watchdog rewrites the `## Status` section and nothing else in the body.**
Every other section is written once and left alone.

```markdown
# Cloud ledger: autonomous run status

Shared state for the cloud-only run. **The protocol is `docs/cloud/runbook.md`.**
Cloud routines read and write this issue. People read it. Nothing here is
authoritative about git — re-derive.

## Status (the watchdog rewrites this section every hour; do not hand-edit)

_not yet written_

## Owner commands

Comment, with `OWNER:` as the **first line**:

- `OWNER: PAUSE track A|B|C` / `OWNER: RESUME track A|B|C`
- `OWNER: STOP ALL` / `OWNER: RESUME ALL`
- `OWNER: ARM AUTO-QUEUE` — acknowledgement only; arming is a repository
  variable the owner sets, not something a routine can do
- `OWNER:` followed by an answer to a `needs-owner` issue

The latest command wins. Routines never write a line starting with `OWNER:`.
The hard stop is disabling the routines at claude.ai/code.

## Tracks

A **track** is a parallel work-stream: Track A, Track B, Track C. It is **not**
a lane — a lane in this repository is an agent's file-ownership boundary,
enforced by `scripts/lwb_lanes.py`. See runbook section 0.

Each track conductor owns one comment below, headed `TRACK A`, `TRACK B` or
`TRACK C`, holding its lock, current item, pull request and attempt count.

## Reviewer

The reviewer routine owns one comment headed `REVIEWER`. **No conductor may
dispatch it**; it runs on its own cron entry. See runbook section 6.
```

---

## Comment protocol

State is encoded in **plain-text line prefixes**, read by regex. Deliberately
not JSON: a human has to be able to fix a stuck lock from a phone, and a
malformed JSON block would strand a routine that cannot parse it.

A routine **posts a new comment**; it does not edit an old one. The watchdog is
the only routine that edits the issue *body*, and only its `## Status` section.

### Track lock

First line of a track comment, always:

```
TRACK A
LOCK 2026-09-19T14:30Z run <session id>
Item: 1.2 make deny fail closed
Branch: track-a/deny-fail-closed
PR: #<n>
Attempt: 1
Next item: 1.3
```

Released form: `LOCK` becomes `idle 2026-09-19T15:10Z`.

**A lock is stale after 110 minutes** and any routine may take it, saying so in
its own comment. The watchdog clears locks older than 150 minutes. The two
numbers differ on purpose: a conductor reclaims a lock before the watchdog
declares the run dead, so the normal case never needs the watchdog.

### Local-session lock

A laptop session coordinating with cloud routines posts
`LOCAL LOCK: <what> ... releases when <condition>`. A conductor **skips** the
named work until the lock says `RELEASED`, or until four hours pass with no new
commit on the named branch. This exists because the laptop is not always off.

### Reviewer comment

```
REVIEWER
LOCK 2026-09-19T14:05Z run <session id>
Reviewed: #<n> @ <40-char head sha> -> AGREE|DISAGREE
Reviewed: #<n> @ <40-char head sha> -> AGREE|DISAGREE
```

### Footer

Every routine comment ends with the Claude Code footer. **That footer is what
distinguishes a routine's comment from an owner command** (runbook section 2
rule 5), so it is load-bearing and must never be stripped.

---

## What the watchdog writes into `## Status`

One line each, re-derived every run, never carried over:

- UTC of this rewrite, and the run id
- `main`: its head and whether CI is green, re-derived from the API
- per track: locked-or-idle, current item, pull request, attempt count
- the reviewer: last run, and how many pull requests are awaiting a review
- pull requests open, with for each one the **reason it cannot merge** — red
  check, missing proof record, missing review record. This is the line that
  makes a stall visible.
- open `needs-owner` issues, oldest first, with their age
- anything merged since the last rewrite
- stale locks cleared this run

**The status section is a re-derivation, not a log.** It says what is true now.
History lives in the comments below it and in git.

---

## The trap this design is built around

`scripts/lwb_check_state_claims.py` fails CI when a tracked `.md` file
hand-asserts volatile state — a head sha, a commit count, whether a pull
request is open. The ledger asserts exactly those things, constantly, and **that
is fine, because a GitHub issue is not a tracked file.** The gate does not read
it.

The corollary is the rule: **volatile state goes on the ledger, never into a
document.** A routine that wants to record "where we are" writes a ledger
comment. A routine that writes it into `HANDOFF.md` or a `docs/` page turns a
required check red, and this repository has done exactly that — the handoff
document that warns against pinning a sha had two pinned shas in it.

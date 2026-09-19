# Making proof of completion mechanical

The owner's position, 2026-09-18: *"we cannot move forward without full
proof of completion."* Directive 7a, SACRED, says a claim of completion
must be backed by a command actually run. Directive 7 already governs what
lands in the repo. Nothing governs what is *said* about it.

This document is the plan for closing that, the blockers still open
against it, and — most importantly — the list of what it will still not
cover. It lives in `docs/` rather than a PR body because a PR body is not
in `git ls-files`, no gate reads it, and the next session will not find it.

## Why the first design was abandoned

The first plan was a deny-capable `proof_required` rule on `PreToolUse`
that blocked `git push` unless a proof record existed. Two adversarial
audit rounds killed it. The findings, kept because each is a trap a
successor could walk back into:

1. **The hook cannot see a push.** `plugins/claude/lwb/hooks/hooks.json`
   registers `"matcher": "Agent"`. `git push` is a Bash tool call. The
   rule would have shipped, passed its tests, and fired zero times —
   the sixth "gate that cannot fail".
2. **The trigger breaks an owner-approved non-goal.** `mission.md`: *"It
   inspects no shell command."* Detecting `git push` means parsing shell
   strings. The owner ruled on 2026-09-18 that the non-goal stands.
3. **A hook cannot learn a PR number.** No network (`approach.md` §8), no
   spawning (D17), and nothing on disk maps a branch to a PR. The
   matching branch was unreachable by any legal implementation.
4. **Chicken-and-egg.** A branch is pushed *before* its PR exists, and the
   record naming that PR comes after. Under `deny`, the push carrying the
   record is itself blocked.
5. **Fail-open swallows it.** A missing policy, an unmentioned rule, or a
   `"denny"` typo all resolve to `off`, and the engine skips the rule
   before calling it. A one-character typo disables the enforcement
   silently.

## What replaces it

Enforcement moves to boundaries that can actually hold it: **CI**, which
runs on a machine the author does not control, and the **session
boundary**, which is where left-behinds live.

### The load-bearing idea, and its honest limit

CI re-executes the commands a proof record claims were run, sanitises the
output the same way, and compares the digest. A fabricated record fails
where its author cannot reach.

**It does not cover everything, and the record must say so.** Counted by
script over every `commands[].argv` in `proof/*.json`, normalising numeric
arguments, there are **ten distinct command kinds**: five re-execute
cleanly on a runner, three cannot, and two are conditional.

An earlier draft of this paragraph said "five are re-executable and five
are not." That was wrong, and it was wrong in a document written to end
false claims — caught by an independent review of PR #17. The review's own
correction was also wrong: it counted nine kinds, merging
`lwb_check_proof.py` with its `--pr N` form. Neither of us had run the
count. The numbers above are measured, and the measurement is the only
reason this sentence is trustworthy.

| Command | Re-executable | Why not |
|---|---|---|
| `pytest tests/ -q` | **no** | output carries a wall-clock duration, a progress width that varies with terminal size, and a test count that moves with the PR |
| `lwb_check_env_leak.py --range origin/main..HEAD` | **no** | a `pull_request` checkout's HEAD is a synthetic merge commit, and `origin/main` has moved |
| `lwb_lanes.py --base origin/main --head HEAD` | **no** | same |
| `lwb_check_env_leak.py` | conditional | needs the repo secret; a fork PR has none |
| `lwb_build.py --check` | conditional | `vendor/` is gitignored |
| `lwb_check_proof.py` | yes | must not recurse into re-execution |
| `lwb_check_proof.py --pr N` | yes | same; counted separately, it is a distinct invocation |
| `lwb_handoff.py --check` | yes | |
| `lwb_check_prefix.py` | yes | |
| `lwb_check_no_instruction_dep.py` | yes | |

The five it loses are the full test suite, the branch-history leak scan
and the lane gate — **precisely what a fabricator would lie about**. So:

- Each `commands[]` entry carries `verifiable: true|false` with a reason
  from a closed enum, machine-checked.
- CI re-executes every `true` and fails if any `false` lacks a valid
  reason.
- Every statement about this says **"N of M commands were independently
  re-executed"**, never "records are falsifiable". The coverage gap is a
  number on the record, not a sentence in a PR body.

Claiming more than that would re-create the exact failure this work
exists to remove.

### Delivered as five PRs, not one

A single PR carrying all of this is unreviewable, and rides on one review
record from a gate that verifies nothing. PRs #13 and #14 both died
mid-flight and were unrepairable because force-push is denied here.

- **(a) Docs, privacy and minors** — the live directive-8 defect, the
  false claims in `mission.md` and `README.md`, the stale pointers.
- **(b) The state-claim gate** — built against real stale lines as
  failing fixtures.
- **(c) Review identity** — a defined `reviewer_id` format, then the
  self-review check that depends on it.
- **(d) Falsifiable records** — the sanitiser as committed code, resolved
  shas, `verifiable` flags, CI re-execution.
- **(e) The session-boundary REPORT** — a `SessionEnd` report, not a
  gate, because that event cannot block. Plus installing the plugin in
  this repo so it eats its own cooking, and verifying the matcher
  actually fires.

## Open blockers

Nothing in (d) or (e) is built while these stand.

1. **The sanitiser does not exist as code.** `session-protocol.md` tells
   each session to write a throwaway script and *delete it*. The records
   disagree about what it did: 7-13 say they replaced `<repo>`, `<home>`
   and `<path>`; 15-16 say `<repo>` and `<home>`. Two rule sets, so every
   historical digest is unverifiable by construction. Fix: ship
   `scripts/lwb_sanitise.py`, have the recorder call it, add
   `sanitiser_version` to `commands[]`, and state plainly that records
   7-16 predate the scheme.
2. **Non-deterministic commands cannot be digest-matched.** Either exclude
   them by name or record a normalised form — argv, exit code, and a
   count extracted by regex — instead of a hash of raw output.
3. **Git-range commands need resolved shas.** The record must store the
   base and head it actually ran against, and CI must substitute those
   rather than re-running the symbolic argv.
4. **Re-deriving the generated `HANDOFF.md` block cannot pass.** It
   contains a generation timestamp, a `main` SHA that moves on every
   merge, and a `gh` call that is unauthenticated in CI. Only the
   proof-state lines, derived from `proof/*.json` in-tree, are stable
   enough to compare; the rest must be declared unverifiable out loud.
5. **RESOLVED 2026-09-19, and the answer shrinks (e).** Checked against
   Claude Code's hooks reference:
   - **`Stop` fires after every assistant turn**, not at session end.
     Confirmed across repeated independent fetches. A left-behinds rule
     on `Stop` would block every turn that had an untracked scratch file.
     `Stop` is therefore wrong for this, exactly as the audit suspected.
   - **`SessionEnd` is the right event and it CANNOT BLOCK.** It fires
     once when the session terminates, carries `session_end_reason`, and
     is purely observational: exit code 2 has no effect and its JSON is
     not honoured for control. So session-boundary enforcement is
     **impossible by construction** — the best available is a report.
   - Consequence: the no-left-behinds rule can never be a gate. It is a
     `SessionEnd` REPORT. Anything stronger must move to CI, which sees
     the repository after the fact, or to `PreToolUse`, which sees the
     action before it happens. `docs/handoff-protocol.md` §Traps says
     this "can only be caught at a session boundary — a `Stop`-hook rule
     or an operator-run skill"; the `Stop`-hook half of that sentence is
     now known to be wrong and should be corrected when (e) lands.
   - Still true, and still owed: `render_decision` hardcodes the
     PreToolUse contract in both branches, so any second event is new
     adapter surface, a new manifest entry and a new conformance
     obligation for both adapters.

6. **The shipped hook may match nothing at all — verify before 1.0.**
   `plugins/claude/lwb/hooks/hooks.json` uses `"matcher": "Agent"`. A
   `PreToolUse` matcher filters on the TOOL NAME. The docs check could
   not find a built-in tool documented as `Agent`, and named `Task` as
   the subagent-dispatch tool in the reference. If `Agent` is not a live
   tool name in the installed version, the only hook this product ships
   fires zero times — a seventh gate that cannot fail, and the one that
   would matter most to another repo installing this. It cannot be
   settled by reading, and — measured 2026-09-19 — it cannot be settled
   from inside a running session either.

   **What was tried, and why it proves nothing.** A probe hook was
   registered on `"matcher": "Agent"` mid-session, writing a marker file;
   a subagent was dispatched; no marker appeared. That looks like an
   answer. It is not one. The control settles it: a second probe was
   added to the matcher that HAD been present at session start
   (`Edit|Write|MultiEdit|NotebookEdit`) and a Write was performed — that
   marker did not appear either. So a mid-session edit to
   `.claude/settings.json` is never read, both probes were dead on
   arrival, and the first result carries no information about the matcher.
   Written down because a negative result is tempting to report as a
   finding, and reporting this one would have been precisely the kind of
   false claim directive 7a exists to stop.

   **How to settle it**, at the START of a session so the hook is loaded:
   register a marker hook on `"Agent"` in `.claude/settings.json`, begin a
   NEW session, dispatch any subagent, and check for the marker. Repeat
   for `"Task"`. Whichever fires is the live tool name; if neither does,
   the only hook this product ships has never run anywhere. Revert the
   probe afterwards. This is a hard precondition for tagging 1.0.0 and the
   first thing another repo installing BuildCraft would hit.
   Noted while there: the reference documents an `if` field alongside
   `matcher`, e.g. `"if": "Bash(git *)"`. That would let the HOST filter
   a publishing action without lwb parsing any shell string itself,
   which is a materially different proposition from the trigger the
   owner rejected. It is not being acted on — the non-goal stands — but
   it is recorded so the option is not rediscovered as a novelty.

## What this will still NOT cover

Written plainly, because the owner was told this makes proof of completion
mechanical and is entitled to know the edges.

1. **Three of directive 7's four legs.** Done means committed *and pushed
   and CI green and* recorded. The scheme checks the record, not that CI
   was green or that the work was pushed.
2. **Quality-floor item 1.** `mission.md` already admits it has no
   mechanical check. Nothing here adds one.
3. **Statements, in general.** `lwb_status.py` generates status from
   measurement, but nothing *requires* a session to use it. Directive 7a
   still binds conduct more than code.
4. **The `LWB - Alert: <id> DONE` announcement**, required by `CLAUDE.md`,
   checked nowhere.
5. **`no_unauthorised_destructive_action`** — the other half of the
   deny-capable pair D9 approved, still unbuilt, and "authorised" is
   still undefined (required-work item 10). Shipping half a pair invites
   reading "the deny-capable rules shipped".
6. **Anything outside a cooperating session.** A hook constrains a session
   that has the plugin installed and routes the action through the hooked
   tool. It does not see the GitHub web UI, the merge queue performing a
   merge server-side, a push from another directory, a push inside a
   script file, or any session where the plugin is absent. The
   bypass/threat model `approach.md` §9 reserves is still owed.
7. **Token measurement.** Five slots are readable from a session
   transcript; three have no source on any runtime. Until it is built,
   the mission's efficiency half is decoration.

## Two live defects this plan inherits

- **Fork PRs can never go green.** Secrets do not reach a `pull_request`
  run from a fork, so `lwb-env-leak` fails `UNCONFIGURED` — correctly
  refusing to pass a scan it could not run. Meanwhile `CONTRIBUTING.md`
  documents a contribution path in five numbered steps without mentioning
  this. The repo advertises a road that is closed. Fix: skip loudly on a
  fork, run the real scan on `merge_group` where secrets are available,
  and say so in `CONTRIBUTING.md`.
- **The plugin is not installed in its own repo.** `.claude/settings.json`
  registers only the lane-write hook. BuildCraft does not eat its own
  cooking, and the hook imports from `vendor/`, which is gitignored — so
  on a fresh clone it raises `ImportError` until `scripts/lwb_build.py`
  has run. Installing it here is part of (e), and the degraded case must
  be visible rather than silent.

## How this document should be read

Everything above is a claim. Two audit rounds found thirteen blockers in
this plan and its predecessor; **none was found by the author.** Treat any
statement here as unverified until a command confirms it, which is the
whole content of directive 7a.

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

**MEASURED AGAIN 2026-09-19, TWICE, and the second measurement was itself
false.** A "MEASURED AGAIN" edit at this spot once claimed **5 of 9**,
asserting `lwb_build.py --check` "appears in the table above but no proof
record in this repo has ever actually run it." That claim was not checked
against the records before it was written, and it was wrong: `lwb_build.py
--check` genuinely RUNS as a `commands[]` entry in `proof/7.json` and
`proof/8.json`. Re-derived properly this time: **ten distinct command
kinds, five re-executable** — the original count in the paragraph below,
before that false "correction" briefly overwrote it. This is recorded
rather than quietly restored, because a false correction silently reverted
is itself a small act of the same dishonesty this document exists to
catch — the reader deserves to know the number moved twice, and why the
second move was wrong.

A second, narrower false claim was made correcting the first: a commit
message (`e2859d6`) said `grep -l lwb_build proof/*.json` finds the string
in `proof/7.json`, `proof/8.json` AND `proof/17.json`, and reported all
three as records that RUN the command. That conflated "the string appears
in the file" with "the command was executed" — `proof/17.json` mentions
`scripts/lwb_build.py` only in its `acceptance_criteria` prose (describing
what a *different* deliverable's guard test covers) and in `mutations`
(a file that deliverable touched); it has no `lwb_build.py` entry in its
own `commands[]` array. `grep -l` matches a filename mentioned in prose
exactly as readily as a command actually run, and the difference was not
checked before the commit message asserted it. Only `proof/7.json` and
`proof/8.json` actually run `lwb_build.py --check` as proof.

An earlier draft of the count below said "five are re-executable and five
are not." That was wrong, and it was wrong in a document written to end
false claims — caught by an independent review of PR #17. The review's own
correction was also wrong: it counted nine kinds, merging
`lwb_check_proof.py` with its `--pr N` form. Neither of us had run the
count at that point. The table below is measured, checked against a real
`grep` over `proof/*.json` rather than against the table's own memory of
itself, and that check is the only reason this paragraph is trustworthy
now.

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

## Cross-platform digest evidence — MEASURED 2026-09-19

The re-execution gate landed report-only because the sanitiser's
determinism was verified on Windows only, and a blocking gate would have
failed every PR if a runner disagreed. That condition is now measured
rather than feared.

PR #21's final green CI run, all six `test` jobs, each reporting the same
line:

    TOTAL: 4 of 107 commands re-executed across 13 records
           -- ALL RE-EXECUTED COMMANDS MATCHED

| runner | python | result |
|---|---|---|
| ubuntu-latest | 3.10 | all matched |
| ubuntu-latest | 3.12 | all matched |
| macos-latest | 3.10 | all matched |
| macos-latest | 3.12 | all matched |
| windows-latest | 3.10 | all matched |
| windows-latest | 3.12 | all matched |

**Digests recorded on one machine reproduce on three operating systems
and two Python versions.** That is the evidence the blocking PR needed.
An earlier note in this document said "one ubuntu-3.12 job log"; an
independent reviewer had read exactly one, and the author had written it
up as "Linux" before being corrected. This supersedes it with all six
read directly.

**What this still does NOT license.** Four commands are re-executable, not
107. The 103 that predate the verifiability fields will never be
re-executed and are deliberately not back-filled. And the three defects
the independent review found — UNCOMPARABLE commands counting toward
neither failures nor the total, a recursion guard escaped by an uppercase
filename or a wrapper, and a missing `argv` crashing the run — must be
fixed BEFORE the gate blocks, because each becomes load-bearing the
moment a green result gates a merge. Reproducibility was one
precondition of three.

## Open blockers

Nothing in (d) or (e) is built while these stand.

1. **CLOSED 2026-09-19 — the sanitiser exists as code.**
   `scripts/lwb_sanitise.py` carries a `SANITISER_VERSION`, normalises
   path separators so Windows and ubuntu produce identical bytes, and is
   called by `scripts/lwb_record.py`, which replaces the throwaway
   capture script. Each command entry records the `sanitiser_version`
   that produced its digest. Records 7-19 predate the scheme and are NOT
   back-filled — a back-filled digest is a fabricated receipt — so their
   digests remain unverifiable, which `proof/README.md` now states.
   Originally recorded as: **The sanitiser does not exist as code.** `session-protocol.md` tells
   each session to write a throwaway script and *delete it*. The records
   disagree about what it did: 7-13 say they replaced `<repo>`, `<home>`
   and `<path>`; 15-16 say `<repo>` and `<home>`. Two rule sets, so every
   historical digest is unverifiable by construction. Fix: ship
   `scripts/lwb_sanitise.py`, have the recorder call it, add
   `sanitiser_version` to `commands[]`, and state plainly that records
   7-16 predate the scheme.
2. **CLOSED 2026-09-19 as to recording; PARTIALLY CLOSED as to
   enforcement, REPORT-ONLY, 2026-09-19.** `scripts/lwb_check_proof.py
   --reexecute` now re-runs every `verifiable: true` command, sanitises
   its output through the running `lwb_sanitise.sanitise`, and compares
   sha256 and exit code against the record. `.github/workflows/ci.yml`'s
   `lwb-proof-reexecute` step runs it with `continue-on-error: true` and
   `if: always()` -- it cannot fail a job yet. Measured locally against
   this repo's real `proof/*.json`: 3 of 101 commands across 12 records
   are `verifiable: true`, and one of those three -- `lwb_handoff.py
   --check` in `proof/20.json` -- did NOT reproduce even locally on this
   machine. Root cause confirmed, not a sanitiser defect: `HANDOFF.md`'s
   generated block was regenerated inside the SAME squash-merge commit
   that landed `proof/20.json`, so the record's own commit already
   disagrees with the file it describes (2214 recorded bytes vs 2262 on
   `main`) -- see `docs/maintainers/session-protocol.md`'s new note on
   regenerating `HANDOFF.md` in its own commit before the records commit.
   The other two verifiable commands (`lwb_check_prefix.py`,
   `lwb_check_no_instruction_dep.py`) reproduced cleanly. Whether digests
   reproduce on an actual GitHub-hosted runner (different repo root, home
   directory, checkout layout) is still unmeasured -- that run is the
   next open question, and this gate becomes blocking only in a separate
   PR filed after it is answered.

   **The open hole a blocking PR must close, named plainly rather than
   fixed by a script (found by independent review of this PR):** the
   closed `verifiable_reason` enum constrains the WORDING an author gives
   for declaring a command unverifiable -- `nondeterministic-output`,
   `git-range-not-reproducible`, `needs-repo-secret`, `needs-build-step` --
   it does not and cannot constrain whether that stated reason is actually
   TRUE of the command it labels. Nothing stops an author from marking
   EVERY command in a record `verifiable: false` with a plausible enum
   reason, re-executing nothing, and — once this mode is made blocking —
   getting a green gate for a record that opted out of verification
   entirely. `reexecute_exit_code`'s `REEXECUTE_EXIT_NOTHING_REEXECUTED`
   (distinct from `REEXECUTE_EXIT_ALL_MATCHED`) makes that opt-out visible
   in the exit code and in the `TOTAL` line's wording, so a blocking PR at
   least CANNOT mistake it for a pass -- but visibility is not the same as
   prevention, and no script can judge whether a stated reason is honest.
   That judgement call belongs to review, not to this gate; the blocking
   PR must say, explicitly, what (if anything) closes it, rather than
   silently relying on the enum to have done more than constrain wording.
   Originally recorded as: **Non-deterministic commands cannot be
   digest-matched.** Either exclude
   them by name or record a normalised form — argv, exit code, and a
   count extracted by regex — instead of a hash of raw output.
3. **CLOSED 2026-09-19 — resolved shas are required and enforced.**
   A command whose argv names a git revision range must carry
   `resolved_base` and `resolved_head`, in both the `a..b` and the
   `--base/--head` forms; the validator rejects it otherwise, from PR 20.
   Originally recorded as: **Git-range commands need resolved shas.** The record must store the
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

## A gate that could never pass, shipped by the PR about gates that cannot fail

`lwb_check_state_claims.py` re-derives HANDOFF.md's generated block and
compared its recorded `main SHA:` against live `main` for EQUALITY. That
is correct on a branch, where the block's `main` claim and the live
`main` ref are the same commit. It is not correct after a squash merge:
`main` becomes a brand-new merge commit that, by definition, did not
exist at the moment the block was generated, so the recorded sha can
never equal live `main` again. The check that was supposed to make gates
honest could not itself pass once merged — and this defect was
introduced by the very PR (#18) whose subject was "gates that cannot
fail."

Measured consequence, `main`'s own push-triggered CI run, by merge
commit:

    a65e2ef (PR #17)  success
    39c951b (PR #18)  failure   <- introduced the equality-only check
    a300623 (PR #19)  failure
    f8cb770 (PR #20)  failure
    539ee65 (PR #21)  failure

Four consecutive merges to `main` ran red, unnoticed for the whole
session. The reason it went unnoticed is itself the lesson: **a PR's
`pull_request` check run and `main`'s own `push` check run are different
triggers, on different commits, and a green `pull_request` run says
nothing about whether `main`'s push run is green.** Every one of those
four PRs merged with a green `pull_request` check — the pre-merge diff
really did pass — and every one then turned `main` red the moment the
squash-merge commit landed, because that commit is precisely the one
this gate could never match. Reading only PR checks is reading half the
signal; the other half, `main`'s own push runs, is where this sat
undetected.

First fix (WRONG, superseded below): `main SHA: X` is a timestamped
snapshot, not a live assertion — it means "main was X when this was
generated," which stays true after `main` moves on as long as X is still
an ancestor of live `main` (via `git merge-base --is-ancestor`). Equal →
pass, silently, as before. An ancestor → pass, but reported as an
UNVERIFIABLE info line naming both shas, not hidden. Neither equal nor an
ancestor → FAIL. Cannot determine (the sha doesn't exist in this repo, a
shallow clone truncated it out, or git itself is unavailable) → reported
as undeterminable, never silently passed.

### The first fix introduced a WORSE defect, and an independent reviewer caught it

That "any ancestor, else cannot-determine-is-never-a-fail" design had two
compounding holes, both found by an independent reviewer, not the author,
running direct probes against the shipped gate rather than reading the
diff:

1. **Every unresolvable value passed.** The raw text after `main SHA:`
   went straight to `git merge-base --is-ancestor` with no format check
   first. `git merge-base` cannot resolve a nonexistent object (or `TBD`,
   `--help`, `origin/main~50`, an empty string, or `0`) and exits with a
   third code the old logic mapped to "cannot determine → never a
   FAIL" — which meant it printed `lwb-check-state-claims check passed`
   and exited 0. The reviewer reproduced this against `deadbeef…`×5,
   `TBD`, `0`, and an empty value: every one passed. The commit that
   shipped this ("the state-claim gate could never pass after a merge")
   had turned "a gate that cannot pass" into "a gate that passes on
   garbage" — strictly worse than the bug it fixed, and the commit
   message claimed the opposite.
2. **"Any ancestor" stopped detecting staleness at all.** A repo's root
   commit is an ancestor of every later commit on `main` forever, so a
   `HANDOFF.md` recording the root commit passed no matter how many years
   out of date it was, and the block's own `Generated:` timestamp was
   never checked against anything. The gate that exists to catch a stale
   document could be satisfied once, at the very first commit, and never
   have to be re-derived again.

**The corrected rule, now shipped:**

1. **Validate the recorded value as 7–40 hex characters BEFORE calling
   git at all.** Anything else is a FAILURE, and git is never invoked to
   decide it — closes hole 1, and also closes a pre-existing silent-pass
   bug (an empty value or a 1-character prefix used to match via Python's
   own `"main-sha".startswith("")`/`startswith(short-prefix)` with zero
   output).
2. **Pass ONLY when the recorded value equals live `main`, or equals live
   `main`'s first parent (`live^1`)** — not "any ancestor". A squash
   merge advances `main` by exactly one commit past what was recorded, so
   equal-or-first-parent is the precise rule for that case and needs no
   age bound; it also closes hole 2, since a root commit is an ancestor
   but is not `live^1` once `main` has moved more than one commit past
   it, so it now correctly FAILS. A 7–40 char prefix match against either
   of those two shas is still honoured.
3. **An unresolvable value in a full clone is a FAILURE**, not
   undeterminable — CI checks out with `fetch-depth: 0`, so an object
   that cannot be resolved there cannot be `main` or its first parent.
   Shallowness is detected via `git rev-parse --is-shallow-repository`;
   in a shallow clone, where the answer genuinely cannot be known, the
   gate reports it and still exits non-zero (the one exception: the
   recorded value equal to live `main`'s own sha is always verifiable
   even at depth 1, since that commit is always present).
4. **Labelling fixed**: when git proves the first-parent relationship the
   info line now carries an `INFO (git-verified)` prefix, not
   `UNVERIFIABLE` — git verified it, it did not merely fail to disprove
   it.

See `scripts/lwb_check_state_claims.py` (`_looks_like_sha`,
`_sha_matches`, `_is_shallow_repository`, and the `main SHA:` branch of
`_scan_generated_block`) and `tests/test_lwb_check_state_claims.py` (the
`ancestor` test group, rewritten — `test_ancestor_recorded_sha_does_not_
exist_is_a_failure` used to assert a nonexistent sha was NOT a failure,
which enshrined hole 1 as a passing test; it now asserts the opposite)
for the mechanics. `_merge_base_is_ancestor` remains in the module as a
low-level git wrapper (still covered by its own direct-call tests) but is
no longer used to decide pass/fail on `main SHA:` — that decision is now
a direct comparison against live `main` and live `main^1`.

### The second fix falsely accused a correct file, caught by the same reviewer in a real shallow clone

The corrected rule above tried `main^1` only when the clone was already
known to be shallow-but-otherwise-treated-as-a-blanket-FAIL — in practice
that meant a shallow clone never even attempted the first-parent
resolution, and any non-equal value there was reported as `stale main SHA
in generated block`, regardless of whether it was actually stale.
Measured by the reviewer in a real `git clone --depth 1` of this repo's
own `main`: the recorded value `f8cb7706488feb29cf6cd2a950a4f82f3dd879b7`
genuinely IS `main`'s first parent (a full clone proves it — see `git log
--oneline -3 main`), but `git rev-parse origin/main^1` in the depth-1
clone fails outright (`fatal: ambiguous argument`). The gate called the
correct file "stale main SHA" — an UNPROVEN accusation reported as an
established fact, the mirror image of the `INFO (git-verified)` labelling
fix above (there, a git-PROVEN fact was mislabelled unverifiable; here,
an unproven claim was mislabelled as a proven lie).

**Fix:** the gate now always attempts `main^1` resolution, in a shallow
clone too — some shallow clones (depth > 1, or ones that happen to
include the parent) really can resolve it, and refusing to try would
turn a provable pass into a needless failure. Only when `main^1` fails to
resolve AND the clone is shallow does the gate report `main SHA
undeterminable in a shallow clone` — still exits non-zero (a shallow
clone can never positively confirm the claim either), but the reason
names the truncation, states the recorded value may be correct, and
tells the reader to re-run with `fetch-depth: 0` to actually decide.
`stale main SHA in generated block` is now reserved for cases git has
actually determined: `main^1` resolved and did not match, or `main^1`
does not exist at all in a full clone (e.g. `main` is the repo's root
commit). Verified against a real `git clone --depth 1 --branch main
file://<this repo>` — see
`tests/test_lwb_check_state_claims.py::test_ancestor_shallow_clone_
correct_first_parent_is_undeterminable_not_stale`, which fails against
the second-fix code (asserted, by stashing `scripts/lwb_check_state_
claims.py` and re-running just that test) and passes against the third.

### The record/head circularity has now bitten FOUR PRs in a row

PR #18 predicted it in writing; #19, #20 and now #22 hit it. Adding
`proof/<pr>.json` changes the proof-state lines the HANDOFF block derives,
so the block must be regenerated — and `resolve_reviewable_head` treats
only `reviews/` and `proof/` as record-only, so a commit touching
`HANDOFF.md` **moves the reviewable head and invalidates the review record
in the same act that makes the record fileable.**

Measured here: with `proof/22.json` added and the block stale, the gate
reported `[stale deliverable proof state in generated block]
recorded=['13/13 proven'] re-derived=['14/14 proven']`.

The workaround used again, for the fourth time, is ordering — regenerate
`HANDOFF.md` **together with** `proof/22.json` in one substantive commit,
then file `reviews/22/` in a commit touching nothing outside `reviews/`,
which leaves the reviewable head on the substantive commit. That works but
requires the reviewer to re-bind to a commit created *after* it gave its
verdict, which is itself a small dishonesty pressure every time.

**The structural fix is still not done**, and is named here so it stops
being rediscovered: classify a commit whose only `HANDOFF.md` change is
*inside the generated `lwb-handoff` markers* as record-only, since the
block is machine-written and carries no reviewable intent. That is a
change to `scripts/lwb_lanes.py`, a shared path, so it needs its own PR
and its own independent review. Four occurrences and one documented
prediction are enough evidence that ordering discipline is not holding.

## How this document should be read

Everything above is a claim. Two audit rounds found thirteen blockers in
this plan and its predecessor; **none was found by the author.** Treat any
statement here as unverified until a command confirms it, which is the
whole content of directive 7a.

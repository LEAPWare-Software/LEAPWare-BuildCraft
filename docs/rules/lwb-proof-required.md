# Rule: `lwb_proof_required`

**Status:** shipped, report-only. Source:
`core/lwb_core/rules/lwb_proof_required.py`. Default mode: `warn` (see
`core/policy/default.json`).

This is the first BuildCraft rule that enforces something **where
BuildCraft is used**, not only inside this repository. `lwb_version` is a
declared no-op; this one makes a completion claim checkable in a repo that
is not this one.

## What it checks

A `PreToolUse` event for the **`Bash`** tool whose command publishes:

| Recognized | Not recognized (deliberately) |
|---|---|
| `git push ...` | `git -C <path> push` |
| `gh pr create ...` | `ENVVAR=x git push` |
| `gh pr merge [<n>] ...` | a push inside a script, alias or `xargs` |

…anywhere in an `&&` / `||` / `;` / `\|` / newline chain, with quoted spans
blanked out first so `git commit -m "remember to git push"` is not a push.
`--dry-run`, `-n`, `--help` and `-h` anywhere in a segment make that
segment a non-publish.

Those three commands are the moments a completion claim stops being a
sentence in a transcript and becomes something other people act on.
Everything before them is drafting. That is why the record is asked for
there, and why **every other Bash command is untouched**.

## What counts as a matching proof record

The adapter reports which record identifiers exist (filename stems of
`proof/*.json` and `.lwb/proof/*.json` — `.lwb/proof/` so a consuming repo
need not adopt this repo's top-level layout). The rule passes silently if
**any** of these matches:

1. a PR number named on the command line — `gh pr merge 24` → `24.json`;
2. the branch name itself — branch `ship-the-rule` → `ship-the-rule.json`
   (the layout to use before a PR number exists);
3. a number embedded in the branch name — `pr/24-ship` → `24.json`.

Record *contents* are not read. Whether a record is well-formed,
complete or self-certified is `scripts/lwb_check_proof.py`'s job in CI,
where there is time to do it properly. This rule answers only: does a
record for this claim exist at all.

## What it reports

A `Finding` naming the claim and the record that is missing, e.g.

```
publishing command with no proof record for 'feature-x': 2 record(s) found
under proof/ or .lwb/proof/, none matching. A completion claim becomes
consequential here -- add proof/feature-x.json before publishing.
See docs/rules/lwb-proof-required.md
```

## Options

None. `options` is accepted by the schema and ignored by this rule.

## Modes

| Mode | Behavior |
|---|---|
| `off` | No check runs (the engine skips OFF rules before calling this one). |
| `warn` | **Shipped default.** The finding is recorded (ledger, `permissionDecisionReason`) and the command proceeds. |
| `deny` | The publish is blocked: `permissionDecision: "deny"`. As of build-plan item 1.2, this also blocks when the rule cannot see enough to judge (`event.repo is None` or `event.repo.facts_incomplete`), with an honest "could not verify" reason -- see "DENY is advisory, not a security control" below. |

Unlike `lwb_version`, which hardcodes WARN and can never deny, this rule
uses `config.mode` verbatim — it **is** armable by policy.

It nevertheless ships at `warn`. That is this repository's own discipline
applied to itself: a gate lands report-only first and is armed in a
separate change once there is evidence about what it actually fires on. A
rule shipping at `deny` would break every consuming repo on install — the
first `git push` after installing the plugin would be refused by a gate
whose conventions that repo has not adopted yet. Ship quiet, read the
ledger, then arm.

## Purity, and where the I/O actually happens

`core/lwb_core` does no I/O (`docs/architecture.md`), so this rule does not
touch the filesystem, run `git`, or read `proof/`. The split is:

```
bin/lwb_hook.py  ->  adapters/claude/repo_facts.py   (IMPURE: looks)
                         |  RepoFacts(branch, proof_ids)
                         v
                     Event.repo                       (core/lwb_core/events.py)
                         |
                         v
                     lwb_proof_required.evaluate      (PURE: decides)
```

`RepoFacts` is a **declared field on `Event`**, not a bag inside
`Event.extra`. `extra` is documented as "adapter-native fields no shipped
rule reads"; facts a shipped rule is *required* to read are the opposite of
that, so they get a name and a type where the author of a second adapter
can see what must be populated.

The collector reads `.git/HEAD` directly rather than running `git
rev-parse` — owner directive 8 is that the plugin must not depend on this
machine, and `git` being on the hook process's `PATH` is exactly such a
dependency. It also runs before every Bash call, and two file reads beat a
process spawn. A worktree's `.git` pointer file is followed, so the
*worktree's* branch is reported, not the main checkout's.

## When it says nothing, on purpose

**In `warn` (and `off`), unchanged by build-plan item 1.2:**

- `event.repo is None` — the adapter gathered no facts. **Absence of
  evidence is not evidence of absence.** This is what keeps the rule inert
  under an adapter that has not been taught to collect repo facts.
- The command is not inside a git repository at all (also surfaces as
  `event.repo is None` -- the adapter walked up to the filesystem root and
  found no `.git`).
- `event.repo.facts_incomplete` is True — the adapter looked but could not
  fully read what it found (a proof directory or `.git/HEAD` existed but
  was not READABLE). "Could not check", not "checked, found nothing".
- Detached HEAD with no PR number on the command line: there is no
  identifier for the claim, so there is nothing to ask for. **This one
  stays silent in EVERY mode, including `deny`** — see below.

**In `deny`, as of build-plan item 1.2, the first two of those four are NO
LONGER silent** — see "Now fails closed" below. The third
(`facts_incomplete`) is also no longer silent in `deny`. Only the fourth
(detached HEAD, no PR number) remains silent in every mode; that is a
deliberate, documented scope decision, not an oversight — see "Confirmed
bypasses" below.

## DENY is advisory, not a security control

`deny` mode blocks a publish this rule can SEE and can prove has no
matching record. It is not a security boundary, and must not be relied
on as one. An adversarial user -- or an agent trying to get past it --
can defeat it.

### Now fails closed (build-plan item 1.2)

Until this change, `deny` mode PERMITTED a publishing command whenever it
could not see enough to judge — `event.repo is None`, or
`event.repo.facts_incomplete` — which is exactly the plan item's own
framing: *"today it permits when it cannot read git, advertising
enforcement it cannot deliver."* That gap is now closed, in `deny` only:

- **`event.repo is None`.** A bare repository, a directory with no `.git`
  at all, an adapter that gathers no facts, or a repo-facts collector that
  crashed upstream — every one of these used to mean silent allow under
  `deny`. Now, when the command is a genuine publish, `deny` returns a
  Finding, with a reason that says plainly it could not verify anything —
  never worded as "0 records found, none matching" (that exact false
  framing is "Attack C", below).
- **`event.repo.facts_incomplete` is True.** A proof directory or
  `.git/HEAD` that exists but could not be read (permission denied, an I/O
  error) — previously silent under `deny` for the same reason. Now denies,
  with the same honest "could not verify" wording, carrying
  `facts_incomplete_reason` when the adapter supplied one.

**`warn` (and `off`) are UNCHANGED for both cases, deliberately**, per the
plan item's own text: *"at `warn` a fail-closed default would warn on
every Bash call in every repository with no `.git` or an unreadable one,
which is worse than the blind spots it would close."* Only `deny` gained
this behavior.

This does not turn `deny` into a security control — a rule that fails
closed on facts it cannot see is still trusting the adapter's own
`cwd`-scoped view of the world (see the `cwd` limit below), and every
other confirmed bypass in this section is unaffected. It closes exactly
one documented gap: `deny` no longer silently downgrades itself to
"report only" the moment it cannot read git.

### Confirmed bypasses that remain, from independent review of PR #26 (and
still open after 1.2)

- **Detached HEAD, no PR number, in EVERY mode including `deny` — left
  out of scope for build-plan item 1.2, by deliberate decision.**
  `RepoFacts(branch=None, facts_incomplete=False)` means the adapter read
  git just fine; there is simply no identifier for the claim being made.
  This is a *different* kind of gap from "cannot read git" — the rule CAN
  read git here — so it is not covered by 1.2's "fails closed when it
  cannot read git" framing, and 1.2 does not change it. **Detaching HEAD
  in one call and pushing in the next still defeats `deny` entirely**: the
  first call reports no branch and passes; the second publishes with
  `repo.branch is None` and no PR number, which this rule still treats as
  having no identifier for the claim, and therefore nothing to ask for
  (see "When it says nothing" above). No single Bash call needs to look
  suspicious for either step. Closing this is a candidate for a LATER,
  separate item, not this one.
- **Undetected commands.** The command parser only recognizes a
  publish as the FIRST token of a segment (see "Under-match,
  deliberately"). All of these publish for real and are not seen:
  `git -C . push`, `(git push)`, `command git push`, `FOO=1 git push`,
  `echo $(git push)`, and `git.exe push`.

**KNOWN LIMIT:** facts are gathered from the hook event's `cwd` -- the
session's own working directory at the time of the call -- not from
wherever a command actually runs. `cd ../other-repo && git push` is
judged against the session repo's branch and proof records, not
`../other-repo`'s (reviewer finding 4; plausible, not reproduced in this
fix). This is unaffected by 1.2: fail-closed still only fires when the
SESSION repo's own facts are missing or incomplete, not when a command
`cd`s into a different one that this rule never observes at all.

**What changed, stated exactly so it cannot be overclaimed:** `deny` now
fails CLOSED — blocks, not permits — when a publishing command is seen but
`event.repo is None` or the facts are otherwise incomplete
(`facts_incomplete`). That WAS the deliberate, separate change described
here before item 1.2 shipped; it is now done. It does NOT make `deny` a
security control (see above), it does NOT change `warn`'s behavior for
either case, and it does NOT close the detached-HEAD-no-PR-number gap or
the parser under-match list, both of which remain open by name.

## Parser blind spots, deliberately under-matching

The parser under-matches on purpose: a missed publish is a warning that did
not fire, while a false positive is a warning on innocent work, which trains
people to ignore the tool. These are the known misses.

Two were found by the independent reviewer of PR #26 and are now **fixed**,
listed here because the record of what was wrong is worth more than the
absence of it:

- `echo "a <<EOF" && git push` — a heredoc introducer *inside quotes* was
  taken at face value, so everything after it was discarded and the real
  `git push` was never seen. `_strip_heredocs` runs before `_strip_quoted`
  deliberately (a heredoc body can contain unbalanced quotes), so the fix is
  a quote-aware scan for the introducer rather than a reordering.
- `cat <<<word; git push` — `<<<` is a **herestring**, a single-word stdin
  redirect with no body and no terminator. Treating it as a heredoc swallowed
  the rest of the line. The guard needed BOTH a lookahead and a lookbehind:
  without the lookbehind, `<<<word` still matched starting at the second `<`.

Still not detected, and not fixed:

- `git -C <path> push`
- env-prefixed pushes, e.g. `FOO=1 git push`
- `(git push)`, `command git push`, `echo $(git push)`, `git.exe push`
- a push inside a script that is invoked rather than typed

## Known gap: Codex

`adapters/codex/hook_io.py` does not collect repo facts, so `Event.repo` is
None on every Codex event and **this rule is inert on Codex today**. That
is a deliberate fail-quiet, not an oversight, but it does mean the
protocol is currently enforced on one host only. Teaching the Codex adapter
to populate `RepoFacts` is all that is required; the rule needs no change.

## Under-match, deliberately

The parser and the matcher both resolve every ambiguity toward silence. A
missed publish is one warning that did not fire. A false positive is a
warning on innocent work — and a gate that cries wolf is trained away
within a week, after which it is decorative and the next real violation
passes unremarked too. The asymmetry is not close, so the bias is not
close either. Each accepted blind spot is named in a comment at the
function that has it, rather than left to be found later as a bug.

## Tests

- `tests/core/test_lwb_proof_required.py` — the rule as a pure unit: both
  decisions, every parse case in both directions, mode honouring, and a
  probe asserting the module imports no I/O machinery. No tmpdir, no git,
  no subprocess in that file — which is itself the purity claim.
- `tests/adapters/test_claude_repo_facts.py` — the impure collector
  against real on-disk layouts (plain clone, worktree pointer, detached
  HEAD, both proof directories), the adapter enrichment, the end-to-end
  `(hook JSON) -> Decision -> rendered output` for the pass, warn and
  armed-deny cases, and the vendored `bin/lwb_hook.py` run as a
  subprocess against a fake consuming repo.

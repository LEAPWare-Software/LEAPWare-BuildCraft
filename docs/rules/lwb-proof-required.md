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
| `deny` | The publish is blocked: `permissionDecision: "deny"`. |

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

- `event.repo is None` — the adapter gathered no facts. **Absence of
  evidence is not evidence of absence.** This is what keeps the rule inert
  under an adapter that has not been taught to collect repo facts.
- The command is not inside a git repository at all.
- Detached HEAD with no PR number on the command line: there is no
  identifier for the claim, so there is nothing to ask for.

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

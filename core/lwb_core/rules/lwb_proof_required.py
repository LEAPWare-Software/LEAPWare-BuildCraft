"""lwb_proof_required: a publishing command needs a proof record behind it.

This is BuildCraft's first rule that enforces something WHERE BUILDCRAFT IS
USED rather than only inside this repository. `lwb_version` is a declared
no-op; this rule makes a completion claim checkable in a consuming repo.

## What it gates, and why there

A `PreToolUse` event for the `Bash` tool whose command PUBLISHES: `git
push`, `gh pr create`, `gh pr merge`. Those are the three moments a
completion claim stops being a sentence in a transcript and becomes
something other people act on. Everything before them is still drafting;
after them the claim is load-bearing. So that is where the record is asked
for.

## Purity

`core/lwb_core` does no I/O (docs/architecture.md), so this rule does not
look at the filesystem, does not run git and does not read `proof/`. It
decides from `event.repo` -- the `RepoFacts` an adapter gathered and froze
into data (see `events.RepoFacts`, and `adapters/claude/repo_facts.py` for
the impure half). Every branch of this function is `(data in) -> (data
out)`; it is fully exercised by constructing `Event`s in a test, with no
repository, no subprocess and no tmpdir needed.

`event.repo is None` means the adapter gathered nothing -- NOT that
nothing was found. This rule stays silent in that case. An adapter that
has not been taught to collect repo facts (today: the Codex adapter) must
not cause a warning on every push.

## Mode

Unlike `lwb_version`, which hardcodes WARN and can never deny, this rule
honours `config.mode`: a policy may set it to `deny`, and a publishing
command with no proof record is then blocked.

`core/policy/default.json` nevertheless ships it at `"warn"`. That is this
repository's own discipline applied to itself: a gate lands report-only
first and is made blocking in a SEPARATE change, once there is evidence
about what it actually fires on. A rule that shipped at `deny` would break
every consuming repo the moment it was installed -- the first `git push`
after install would be refused by a gate whose conventions that repo has
not adopted yet. Ship quiet, collect evidence from the ledger, then arm.

## Parsing posture: UNDER-match, deliberately

The command parser and the record matcher both resolve every ambiguity
toward SILENCE. A missed publish is one warning that did not fire. A false
positive is a warning on innocent work, and a gate that cries wolf is
trained away within a week -- after which it is decorative, and the next
real violation passes unremarked too. The asymmetry is not close, so the
bias is not close either. Known, accepted blind spots are named at each
function below rather than left to be discovered later as bugs.

See docs/rules/lwb-proof-required.md for the policy-author-facing
description.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from ..config import RuleConfig
from ..events import Event, RepoFacts

rule_id = "lwb_proof_required"

#: Only the Bash tool carries a shell command. A publish performed through
#: some other tool is out of scope and is not guessed at.
_TOOL_NAME = "Bash"

#: Claude Code's Bash tool puts the command string under this key; the
#: adapter passes `tool_input` through unchanged, so the rule reads it
#: here. Verified against adapters/claude/hook_io.py (which copies
#: `tool_input` verbatim) rather than assumed.
_COMMAND_KEY = "command"

#: Shell operators that end one command and begin another. Splitting on
#: these is what stops `cd x && git push` being read as a single token
#: sequence starting with `cd`.
_SEGMENT_SPLIT = re.compile(r"&&|\|\||[;\n|&]")

#: Any of these anywhere in a segment makes it a non-publish. `--dry-run`
#: and `-n` publish nothing; `--help`/`-h` print text. Treating them as
#: non-publishing can only make this rule quieter, which is the safe
#: direction.
_NON_PUBLISHING_FLAGS = frozenset({"--dry-run", "-n", "--help", "-h"})

_QUOTES = ("'", '"')

#: A heredoc introducer: `<<WORD`, `<<-WORD`, `<<'WORD'` or `<<"WORD"`. The
#: `<<-` form (leading tabs stripped from the body and terminator) is
#: matched the same as plain `<<`; this rule only needs to find where the
#: body ends, not reproduce tab-stripping.
# `<<` but NOT `<<<`. A HERESTRING (`cmd <<<word`) is a single-word stdin
# redirect with no body and no terminator -- treating it as a heredoc made
# the stripper swallow the REST OF THE COMMAND LINE, so `cat <<<word;
# git push` scanned as `(False, [])` and the real publish after the
# semicolon vanished. Found by the independent reviewer of PR #26. The
# guards are BOTH directions: `<<` may not be followed by `<` (which
# would be the herestring itself), and may not be PRECEDED by one --
# without the lookbehind, `<<<word` still matched starting at the
# SECOND character, reading `<<word` as a heredoc introducer.
_HEREDOC_START = re.compile(
    r"(?<!<)<<(?!<)-?\s*(?:'([^'\n]+)'|\"([^\"\n]+)\"|([A-Za-z_][A-Za-z0-9_]*))"
)


def _heredoc_start_outside_quotes(text: str):
    """First `_HEREDOC_START` match that is NOT inside a quoted string.

    `_strip_heredocs` runs BEFORE `_strip_quoted`, which is deliberate --
    a heredoc body can contain quote characters that would otherwise
    unbalance the quote scanner. The cost is that a heredoc introducer
    appearing INSIDE quotes was taken at face value: `echo "a <<EOF" &&
    git push` had everything from `<<EOF` onward discarded, so the real
    `git push` after `&&` was never seen. Reported by the reviewer of
    PR #26 as an under-match.

    This walks the text tracking single- and double-quote state and
    returns only a match that begins outside quotes, so the ordering can
    stay as it is while the introducer is still read honestly.
    """
    in_single = False
    in_double = False
    i = 0
    length = len(text)
    while i < length:
        ch = text[i]
        if ch == "\\" and in_double and i + 1 < length:
            i += 2
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "<" and not in_single and not in_double:
            match = _HEREDOC_START.match(text, i)
            if match is not None:
                return match
        i += 1
    return None


def _strip_heredocs(command: str) -> str:
    """Blank out heredoc BODIES so their lines are never read as new commands.

    `cat > x.sh <<'EOF'` followed by a body line of `git push origin main`
    and a terminator line of `EOF` writes a script; it does not publish.
    Without this, `_SEGMENT_SPLIT` (which splits on newlines among other
    things) reads the body line as its own segment and the rule fires on
    a file it never ran.

    Finds each heredoc introducer, then the next line that is exactly the
    terminator word (its own line, only surrounding whitespace allowed),
    and removes everything from the introducer through that terminator
    line inclusive. An unterminated heredoc -- the terminator never
    appears -- has its body run to the end of the string, matching this
    rule's existing under-match posture for an unterminated quote in
    `_strip_quoted`.
    """
    out = command
    while True:
        match = _heredoc_start_outside_quotes(out)
        if match is None:
            return out
        word = match.group(1) or match.group(2) or match.group(3)
        terminator = re.compile(
            r"^[ \t]*" + re.escape(word) + r"[ \t]*$", re.MULTILINE
        )
        tail = terminator.search(out, match.end())
        if tail is None:
            return out[: match.start()]
        out = out[: match.start()] + " " + out[tail.end() :]


def _strip_quoted(command: str) -> str:
    """Blank out quoted spans so their contents can never look like a command.

    `git commit -m "remember to git push"` must not read as a push. Rather
    than implement shell quoting properly -- backslash escapes, `$'...'`,
    nesting, here-documents -- this replaces each quoted span with a single
    space and moves on.

    Accepted blind spot: an unterminated quote swallows the rest of the
    string, so `echo "oops && git push` is seen as containing no push. That
    is the under-match direction, and is preferred to the alternative,
    which would be guessing where the author meant the quote to close.
    """
    out: List[str] = []
    quote: Optional[str] = None
    for ch in command:
        if quote is None:
            if ch in _QUOTES:
                quote = ch
                out.append(" ")
                continue
            out.append(ch)
        elif ch == quote:
            quote = None
    return "".join(out)


def _scan_command(command: str) -> Tuple[bool, List[str]]:
    """Return (publishes, explicit PR numbers named in the command).

    A segment publishes when its FIRST token is the program itself:
    `git push ...` or `gh pr create|merge ...`. Requiring position 0 is
    what keeps `echo git push`, `grep git-push log.txt` and a trailing
    comment from firing.

    Accepted blind spots, all under-matching:
      - `git -C /some/repo push` is not recognized (token 1 is not
        `push`). Recognizing it would mean modelling git's global options
        and which of them consume the next argument.
      - An env prefix (`GIT_SSH_COMMAND=... git push`) is not recognized.
      - A push performed by a script, a shell alias or `xargs` is not
        recognized. Nothing short of running the command could recognize
        those, and this rule does not run commands.
    """
    publishes = False
    pr_numbers: List[str] = []

    for segment in _SEGMENT_SPLIT.split(_strip_quoted(_strip_heredocs(command))):
        tokens = segment.split()
        if not tokens:
            continue
        if any(token in _NON_PUBLISHING_FLAGS for token in tokens):
            continue

        if tokens[0] == "git" and len(tokens) >= 2 and tokens[1] == "push":
            publishes = True
        elif (
            tokens[0] == "gh"
            and len(tokens) >= 3
            and tokens[1] == "pr"
            and tokens[2] in ("create", "merge")
        ):
            publishes = True
            # `gh pr merge 24` names its own claim. Take the first bare
            # number after the subcommand; flags are skipped, and
            # `gh pr create` normally names none, which is fine -- the
            # branch is then the only identifier available.
            for token in tokens[3:]:
                if token.isdigit():
                    pr_numbers.append(token)
                    break

    return publishes, pr_numbers


def _branch_number_tokens(branch: str) -> List[str]:
    """Numeric parts of a branch name: `pr/24-fix` -> ["24"].

    This WIDENS what counts as a matching record, which makes the rule
    quieter rather than louder -- consistent with the under-match posture.
    A repo whose branches are named after their PR number gets a pass
    without having to name the number on the command line.
    """
    return [part for part in re.split(r"[^0-9A-Za-z]+", branch) if part.isdigit()]


def _matching_record(repo: RepoFacts, pr_numbers: List[str]) -> Optional[str]:
    """The identifier of a proof record backing this publish, or None.

    Checked in order of how explicit the claim is: a PR number named on the
    command line, then the branch name itself (`proof/<branch>.json`, the
    layout a consuming repo can adopt before it has a PR number at all),
    then any number embedded in the branch name.
    """
    known = set(repo.proof_ids)
    if not known:
        return None

    for number in pr_numbers:
        if number in known:
            return number

    branch = repo.branch
    if branch:
        if branch in known:
            return branch
        for number in _branch_number_tokens(branch):
            if number in known:
                return number

    return None


def evaluate(event: Event, config: RuleConfig):
    """Warn (or deny) on a publishing command with no proof record behind it.

    Returns None -- silently, with no opinion -- for every event that is not
    a Bash publish, and for every publish this rule cannot honestly judge.

    `config.mode` is already guaranteed non-OFF by the engine, and is used
    verbatim as the finding's severity: this rule is armable by policy,
    unlike `lwb_version`.
    """
    from ..engine import Finding  # local import: engine imports this module.

    if event.hook_event != "PreToolUse" or event.tool_name != _TOOL_NAME:
        return None

    command = event.tool_input.get(_COMMAND_KEY)
    if not isinstance(command, str) or not command.strip():
        return None

    publishes, pr_numbers = _scan_command(command)
    if not publishes:
        # The overwhelming majority of Bash calls land here. Ordinary work
        # must be untouched by this rule.
        return None

    repo = event.repo
    if repo is None:
        # The adapter gathered no repo facts. Absence of evidence, not
        # evidence of absence -- say nothing.
        return None

    if repo.facts_incomplete:
        # The adapter looked but could not fully read what it found (a
        # proof directory or .git/HEAD existed but was not READABLE) --
        # "could not check", not "checked, found nothing". An independent
        # reviewer's Attack C (`chmod 000 proof/` with a matching record
        # still on disk, deny mode) turned this rule into a FALSE DENY:
        # it reported "0 record(s) found ... none matching" when it had
        # in fact been unable to count anything. Staying silent here
        # keeps this rule's own documented UNDER-match posture -- a
        # missed warning is preferred to a deny built on facts this rule
        # does not actually have. See `RepoFacts.facts_incomplete` and
        # `bin/lwb_hook.py`'s `repo.facts_incomplete` warning, which is
        # what makes "could not check" visible instead of merely quiet.
        return None

    if repo.branch is None and not pr_numbers:
        # Detached HEAD (or an unreadable HEAD) and no PR number on the
        # command line: there is no identifier for the claim being made,
        # so there is nothing this rule could sensibly ask for.
        return None

    if _matching_record(repo, pr_numbers) is not None:
        return None

    claim = pr_numbers[0] if pr_numbers else repo.branch
    return Finding(
        rule_id=rule_id,
        mode=config.mode,
        reason=(
            f"publishing command with no proof record for '{claim}': "
            f"{len(repo.proof_ids)} record(s) found under proof/ or .lwb/proof/, "
            f"none matching. A completion claim becomes consequential here -- "
            f"add proof/{claim}.json before publishing. "
            f"See docs/rules/lwb-proof-required.md"
        ),
    )

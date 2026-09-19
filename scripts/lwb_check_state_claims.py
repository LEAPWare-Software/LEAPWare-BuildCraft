#!/usr/bin/env python3
"""CI check `lwb-check-state-claims`: no tracked document hand-asserts
volatile git/PR state.

Owner directive 7a (SACRED): a claim of completion or of project state
must be backed by a command actually run. `docs/maintainers/session-handoff-
2026-09-18.md` records the failure mode this check exists to close: a
stated branch-tip sha, a stated commit count and a stated "no PR is open"
were all false within minutes of being written down, and it took an
independent reviewer -- not the author -- to catch it. This script scans
every tracked `.md` file for a hand-typed assertion of state that only a
live command can answer correctly, and fails the build if it finds one.

HONEST SCOPE. This gate makes DOCUMENTS honest, not STATEMENTS. It cannot
catch:
  - a claim that is stale but phrased without any of the covered patterns
    (this is pattern matching, not language understanding);
  - a wrong-but-stable claim (a sha that exists and is simply the wrong
    one -- the "main SHA:" field is re-derived and compared, but a
    same-shape sha cited elsewhere in prose, with no comparable ground
    truth, is not);
  - anything outside tracked `.md` files -- NAMED explicitly, because an
    undocumented hole is the thing this gate exists to stop shipping: a
    `.txt` or `.rst` file, a Python (or any other language's) docstring
    or comment, a PR body, a commit message, a Slack message, or anything
    said directly to the owner;
  - anything said out loud rather than written down.
That last one is the biggest gap and must be said out loud: most of the
false claims that motivated this script were made in conversation with
the owner, not in a committed document, and this gate cannot see those at
all. Directive 7a still binds conduct for everything said outside a
tracked file; this script is the mechanizable slice of it.

KNOWN FALSE POSITIVES, left in deliberately rather than "fixed" with a
retrospective-context heuristic that would itself be a new way to misfire
silently:
  - a retrospective/statistical mention of a count in the same shape as a
    live claim ("During Q2 there were three open PRs on average per
    week");
  - a changelog-style historical label ("main SHA: <sha> was tagged as
    the release point").
Neither is disambiguated from a live claim; both are flagged. Mark a
genuine historical mention with `<!-- volatile-ok: historical -->` (or
`example`) ON THE SAME PHYSICAL LINE -- the escape is scoped to the
physical line it appears on, not the paragraph, so it will not also
exempt an unrelated claim two lines later in the same bullet.

KNOWN EVASIONS, found by a second adversarial review and left open on
purpose (each is a decision, not an oversight):
  - Table-row split: a label and its value on two separate table rows,
    e.g.
        | main SHA |
        9463214739b90a6de1ae0b384fdc8ac2b1e6e40c |
    passes clean. A table row is flushed as its own logical line and
    never joined with the row after it (see `_build_logical_lines`), so
    the label and the value land in unrelated logical lines and neither
    alone matches a pattern. NOT fixed: joining a table row with
    whatever follows it would join every ordinary two-row table in this
    repo the same way, producing false positives across all of them, to
    close one adversarially-constructed table.
  - En dash for colon ("main SHA– <sha>", U+2013): NOT fixed. An en
    dash is a genuinely different character, not an NFKC-normalised form
    of a colon -- `unicodedata.normalize("NFKC", ...)` does not touch it,
    and adding a bespoke dash-to-colon substitution would start a list of
    "characters that sort of look like a colon" with no principled end.
  - Cyrillic homoglyph substitution ("mаin SHA: <sha>", U+0430 for
    Latin "a"): NOT fixed. The stdlib has no confusable-folding table
    (that is what Unicode TR39 / a library like `confusable-homoglyphs`
    is for, and this script is stdlib-only by design). Left open
    deliberately, not from lack of effort: this gate exists to catch an
    HONEST author whose true statement rotted, not to catch someone
    smuggling a false claim past it on purpose -- anyone willing to type
    a Cyrillic homoglyph to defeat this check could simply not write the
    sentence. Pretending a partial, unmaintained confusable table closed
    this case would be exactly the false-confidence failure this whole
    gate exists to prevent.

CI NOTE (not this script, but worth recording here since it governs when
this script runs): `.github/workflows/ci.yml`'s `test` job now carries
`if: always()` on nearly every step, so that one failing gate cannot mask
a later one (see the fix history for why). A side effect: a CANCELLED
workflow run will still execute the rest of that job's steps instead of
stopping early, because `always()` does not distinguish "a previous step
failed" from "the run was cancelled". Not a correctness defect -- every
step still reports its own true result -- but it means a cancelled run on
this job costs the full run time rather than stopping partway.

Design decisions (the brief this originally implemented lived in a session
scratchpad and was never committed to this repo -- restated here in full
rather than cited, so a reader never follows a pointer to vapour):
  - Wrapped prose is joined into one logical line per paragraph/bullet/
    heading/blockquote before matching, and a hit is mapped back to the
    FIRST physical line of that logical line for reporting. This repo
    hard-wraps all prose at ~72 columns; a line-anchored scanner (the
    first implementation) is defeated by its own target's formatting.
  - The generated `<!-- lwb-handoff:begin -->` ... `:end -->` block in
    HANDOFF.md is NOT exempt from scanning. Its `Generated:` and
    `main SHA:` fields, and its `Open PRs:` listing, are re-derived
    against live git/gh state where possible and compared; a mismatch is
    a finding, and inability to re-derive (no `gh` auth, e.g. in CI) is
    printed as UNVERIFIABLE rather than silently treated as passing. Its
    `Deliverable proof state (from proof/):` lines -- a summary line plus
    one line per UNPROVEN record, so the section's size tracks problem
    count rather than record count, owner ruling 2026-09-18 -- are
    re-derived by calling `lwb_handoff._proof_state_lines()` directly and
    compared line for line.
  - `main SHA:` (see `_looks_like_sha`/`_sha_matches`/
    `_is_shallow_repository`, and the `main SHA:` branch of
    `_scan_generated_block`): the recorded value must first be a bare
    7-40 character hex string, checked BEFORE git is ever invoked --
    anything else (a revision expression, a flag, a placeholder, empty,
    a bare digit) is a FAILURE with no git subprocess run to decide it.
    A valid value then passes ONLY if it equals live `main` or equals
    live `main`'s FIRST PARENT (`main^1`) -- not "any ancestor". A squash
    merge advances `main` by exactly one commit past what was recorded,
    so equal-or-first-parent is the precise, no-age-bound rule; "any
    ancestor" was tried first and an independent reviewer proved it
    regressed this gate to a silent pass on every unresolvable value
    (`deadbeef...`, `TBD`, `0`, empty all passed) and stopped detecting
    staleness altogether (a repo's root commit is an ancestor of
    everything forever). A short-sha prefix match against either target
    is honoured. An unresolvable value is a FAILURE in a full clone
    (detected via `git rev-parse --is-shallow-repository` returning
    false) and, in a shallow clone, is reported AND still exits non-zero
    -- never a silent pass either way. When git proves the first-parent
    relationship, the info line carries `INFO (git-verified)`, not
    `UNVERIFIABLE` -- see `docs/maintainers/proof-of-completion-plan.md`,
    "The first fix introduced a WORSE defect", for the full incident.
  - The marker is bound to `HANDOFF.md` specifically; the same text in
    any other file grants no exemption. Inside HANDOFF.md, exactly one
    BEGIN and one matching END are required -- a missing/duplicated/
    out-of-order marker is an ERROR, not a silent exemption to EOF.
  - An unclosed ``` fence is an ERROR, not an exemption to EOF.
  - `<!-- volatile-ok: REASON -->` takes REASON from a closed enum
    (`VOLATILE_OK_REASONS`); an unrecognised reason does not exempt the
    line and is itself reported as an error, so a free-text escape can
    never quietly slip past review. The escape is scoped to the PHYSICAL
    line it appears on (via each logical line's parallel char-to-lineno
    map), not to the whole joined paragraph -- an earlier version let one
    legitimately-escaped clause shield an unrelated live claim two lines
    later in the same hard-wrapped bullet, which an adversarial review
    caught by direct probe.
  - A quoted volatile phrase is exempt only when it is preceded (within
    the same logical line) by an attribution verb, or when it sits inside
    a markdown blockquote (`> ...`). A bare quotation with neither is
    still an assertion and is flagged.
  - Counts are matched as digits OR spelled out zero through twenty (plus
    "a"/"an"), case-insensitive, for both commit counts and PR counts;
    "PR(s)" and "pull request(s)" are both covered. A table row (`| ... |
    ... |`) is normalised -- cell separators collapsed to whitespace --
    before matching, so a claim hidden in a table cell is scanned exactly
    like prose. The SHA-label pattern accepts optional backticks around
    the subject and the value, an optional literal "SHA" keyword, and
    either "SHA:" or a bare ":" -- covering "main SHA: <sha>",
    "`main` SHA: `<sha>`", "main: <sha>" (shorthand, no "SHA" word), and
    a normalised table row "main SHA <sha>" (no colon at all) in one
    pattern. A reordered "at <sha> ... on main" is covered in addition to
    the subject-first "main is at <sha>" form.
  - Each physical line is NFKC-normalised and stripped of invisible
    Cf-category "format" characters (word joiner, soft hyphen, zero-width
    space/non-joiner/joiner, the BOM, the Mongolian vowel separator, and
    any other code point Unicode classifies the same way -- matched by
    `unicodedata.category(ch) == "Cf"`, not by enumerating a fixed list;
    an enumerated four-code-point regex here previously missed three more
    Cf characters an adversarial review found) BEFORE classification and
    joining -- closing a fullwidth colon ("main SHA： <sha>", U+FF1A) and
    a zero-width space hidden inside a label ("main​SHA:"). Normalising
    per PHYSICAL line, not on the already-joined paragraph, matters: NFKC
    can change a segment's length, and doing this before the join
    guarantees any length change lands entirely within one physical
    line's own span of `char_linenos`, so the escape's per-physical-line
    binding (above) cannot desync even when an earlier line in the same
    paragraph is the one that gets rewritten. See "KNOWN EVASIONS" above
    for the two Unicode cases this does NOT close.

Scans tracked `.md` files only (via `git ls-files`), so an untracked
scratch file can never fail CI and a file nobody will ship is not policed.

Usage:
    python lwb_check_state_claims.py [--repo PATH]

Stdlib only. Exits 1 and lists every finding/error when it finds one;
exits 0 (after printing any UNVERIFIABLE notes) otherwise.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Markers, escape enum
# ---------------------------------------------------------------------------

BEGIN_MARKER = "<!-- lwb-handoff:begin -->"
END_MARKER = "<!-- lwb-handoff:end -->"
HANDOFF_FILENAME = "HANDOFF.md"

# Closed enum for the `volatile-ok` escape. A human-reviewed free-text
# reason is an advisory rule, and principle 1 of the mission rejects
# advisory rules -- so the reason must be one of these, or it does not
# exempt anything.
VOLATILE_OK_REASONS = frozenset(
    {
        "historical",  # a completed, past-tense state, not a live claim
        "generated-block",  # inside machine-generated text this script
        # already re-derives by other means
        "illustrative",  # names the anti-pattern itself, for a reader
        "example",  # a worked example in documentation, not an assertion
    }
)

ESCAPE_COMMENT = re.compile(r"<!--\s*volatile-ok\s*:\s*([^>]*?)\s*-->")

# Attribution verbs that make a quoted volatile phrase a citation rather
# than an assertion. `stated` is not in the spec's original four-word list
# (said/wrote/claimed/reads) but this repo's own prose
# (docs/maintainers/session-handoff-2026-09-18.md) uses it for exactly
# this pattern, and without it the gate cannot pass against its own
# target repo -- see the report for this PR.
ATTRIBUTION_VERBS = re.compile(
    r"\b(?:said|wrote|claimed|reads|stated|reported)\b", re.IGNORECASE
)

FENCE_MARK = re.compile(r"^\s*```")


# ---------------------------------------------------------------------------
# Volatile patterns -- matched against a JOINED logical line
# ---------------------------------------------------------------------------

_SHA = r"[0-9a-f]{7,40}"
_REF = r"`?[\w][\w./-]*`?"

# Spelled-out counts evade a \d+-only pattern outright ("six commits",
# "zero open pull requests", "Ten open PRs" all used to pass). Cover
# zero through twenty plus the indefinite article, case-insensitive (the
# patterns below all carry re.IGNORECASE).
_NUM = (
    r"(?:\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen"
    r"|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|a|an)"
)
# "PRs" is this repo's habitual abbreviation, but "pull request(s)" is
# plain English for the same claim and passed untouched.
_PR = r"(?:PRs?|pull\s+requests?)"

VOLATILE_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "branch/main described as currently at a sha",
        re.compile(
            r"\b(?:main|master|HEAD|origin/main|" + _REF + r"\s+branch|branch\s+" + _REF + r")\b"
            r"[^.\n`]{0,30}?\b(?:is|sits|stands|remains|currently\s+is|now\s+points?|points?)\b"
            r"[^.\n]{0,20}?\b(?:at|to)\b[^.\n]{0,10}`?\b" + _SHA + r"\b",
            re.IGNORECASE,
        ),
    ),
    (
        "branch/main described as currently at a sha (reordered)",
        # "We are currently at <sha> on main." -- the subject-verb order
        # of the pattern above is not the only order this repo's own
        # prose uses.
        re.compile(
            r"\b(?:currently\s+)?at\s+`?" + _SHA + r"\b[^.\n]{0,30}?\bon\s+"
            r"(?:main|master|HEAD|origin/main|" + _REF + r"\s+branch|branch\s+" + _REF + r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        "tip-of-branch sha claim",
        re.compile(
            r"\bthe\s+tip\s+of\s+" + _REF + r"\s+is\s+`?" + _SHA + r"\b",
            re.IGNORECASE,
        ),
    ),
    (
        "branch/main labelled with a live SHA",
        # Covers "main SHA: <sha>" (the original form), backticks around
        # the subject and/or the value ("`main` SHA: `<sha>`"), the
        # colon-only shorthand with no "SHA" word ("main: <sha>"), and a
        # table row with cell separators already normalised to whitespace
        # ("main SHA <sha>", no colon at all) -- see _normalize_table_row.
        # "SHA" is required when there is no colon, so a bare
        # "main <unrelated-hex-looking-word>" does not match.
        re.compile(
            r"\b`?(?:main|master|HEAD)`?\s*(?:SHA\s*:?|:)\s*`?" + _SHA + r"\b",
            re.IGNORECASE,
        ),
    ),
    (
        "commit count (holds/carries/has N commits)",
        re.compile(
            r"\b(?:holds?|carries?|has|contains?)\s+" + _NUM + r"\s+commits?\b", re.IGNORECASE
        ),
    ),
    (
        "commit count (N unmerged/open commits)",
        re.compile(r"\b" + _NUM + r"\s+(?:unmerged|open)\s+commits?\b", re.IGNORECASE),
    ),
    (
        "commit count (N commits ahead/behind)",
        re.compile(r"\b" + _NUM + r"\s+commits?\s+(?:ahead|behind)\b", re.IGNORECASE),
    ),
    (
        "commit count (is N ahead/behind of)",
        re.compile(r"\bis\s+" + _NUM + r"\s+(?:ahead|behind)\s+of\b", re.IGNORECASE),
    ),
    (
        "open-PR assertion (no PR is open / no open PRs)",
        re.compile(
            r"\bno\s+(?:open\s+)?" + _PR + r"\s+(?:is|are)\s+open\b|\bno\s+open\s+" + _PR + r"\b",
            re.IGNORECASE,
        ),
    ),
    (
        "open-PR assertion (N open PRs)",
        re.compile(r"\b" + _NUM + r"\s+open\s+" + _PR + r"\b", re.IGNORECASE),
    ),
    (
        "open-PR assertion (there is/are ... open PR(s))",
        re.compile(r"\bthere\s+(?:is|are)\b[^.\n]{0,20}?\bopen\s+" + _PR + r"\b", re.IGNORECASE),
    ),
    (
        "open-PR assertion (a/the PR is open)",
        re.compile(r"\b(?:a|the)\s+PR\s+is\s+open\b", re.IGNORECASE),
    ),
    (
        "open-PR assertion (PR #N is (still) open)",
        re.compile(r"\bPR\s*#?\d+\s+is\s+(?:still\s+)?open\b", re.IGNORECASE),
    ),
    (
        "branch existence assertion",
        re.compile(
            r"\bbranch\s+" + _REF + r"\s+(?:still\s+)?(?:exists|does\s+not\s+exist|no\s+longer\s+exists)\b"
            r"|\bno\s+branch\s+(?:named|called)\s+" + _REF + r"\s+exists\b"
            r"|`[\w./-]+`\s+still\s+exists\b(?:\s+on\s+(?:the\s+)?(?:remote|origin))?",
            re.IGNORECASE,
        ),
    ),
    (
        "branch carries unmerged work",
        re.compile(r"\bbranch\s+" + _REF + r"\s+carries\s+the\s+unmerged\s+deliverable\b", re.IGNORECASE),
    ),
    (
        "branch described as a leftover awaiting cleanup",
        re.compile(r"\bbranch\s+" + _REF + r"\s+is\s+a\s+leftover\b", re.IGNORECASE),
    ),
    (
        "landing-from claim (work presented as still unlanded)",
        re.compile(r"\blanding\s+from\s+" + _REF, re.IGNORECASE),
    ),
]


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    path: str
    lineno: int
    label: str
    text: str

    def render(self) -> str:
        return f"{self.path}:{self.lineno}: [{self.label}] {self.text.strip()}"


@dataclass
class Info:
    path: str
    lineno: int
    text: str
    # Default "UNVERIFIABLE": this session could not determine an answer.
    # A distinct prefix ("INFO (git-verified)") is used when git actually
    # PROVED the claim (e.g. the recorded sha is live main's first
    # parent) -- that must never be printed as if it were merely
    # unresolved, which is the mislabelling an independent reviewer
    # flagged in this gate's own PR history.
    prefix: str = "UNVERIFIABLE"

    def render(self) -> str:
        return f"{self.path}:{self.lineno}: {self.prefix}: {self.text}"


# ---------------------------------------------------------------------------
# git/gh helpers
# ---------------------------------------------------------------------------


def _tracked_md_files(repo: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return [repo / line for line in result.stdout.splitlines() if line]


def _rev_parse(repo: Path, ref: str) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", ref],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _live_main_sha(repo: Path) -> str | None:
    return _rev_parse(repo, "origin/main") or _rev_parse(repo, "main")


def _merge_base_is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool | None:
    """True if `ancestor` is an ancestor of (or equal to) `descendant`,
    False if it definitely is not, None if it cannot be determined (the
    sha does not exist in this repo -- a shallow clone truncated it out,
    or it was never a real object at all -- or git itself is
    unavailable). `git merge-base --is-ancestor` exits 0/1 for a real
    yes/no answer and a non-0/1 code (128 in practice) when it cannot
    even resolve one of the two commits -- that third outcome must never
    be folded into either a pass or a fail, per the module's degraded-path
    convention (see `_pr_state`): "cannot tell" is its own outcome, not a
    quiet "yes"."""
    try:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    return None


_SHA_STRICT = re.compile(r"^[0-9a-fA-F]{7,40}$")


def _looks_like_sha(value: str) -> bool:
    """True only for a bare 7-40 char hex string -- nothing else. This is
    the gate an independent reviewer's finding #1 demanded: validated
    BEFORE git is ever consulted, so a revision expression ("origin/
    main~50"), a flag ("--help"), a placeholder ("TBD"), an empty string,
    or a single digit ("0") can never reach `git merge-base` or `git
    rev-parse` as if it were a commit-ish. Any of those used to be handed
    to git directly; several (a 1-char prefix, empty) even matched via
    Python's own `str.startswith("")`, a silent pass with no output at
    all (finding #5)."""
    return bool(_SHA_STRICT.match(value))


def _sha_matches(recorded: str, target: str | None) -> bool:
    """True if `recorded` (already validated by `_looks_like_sha`) equals
    live `target`, or is a short-sha prefix of it. `recorded` is never
    longer than a full 40-char sha, so checking `target.startswith
    (recorded)` alone covers both the short-prefix case and the
    full-length-equal case -- no second, reversed comparison is needed."""
    return target is not None and target.lower().startswith(recorded.lower())


def _is_shallow_repository(repo: Path) -> bool:
    """True if `repo` is a shallow clone. CI runs with `fetch-depth: 0`
    (a full clone) precisely so this gate can trust its own answers; a
    shallow clone is missing history a full clone would have, so an
    "unresolvable" recorded sha there is not necessarily a lie -- it may
    just be truncated out of the visible history. Per the reviewer's
    prescription, that must be reported AND treated as a failure, never
    silently passed, and never silently treated the same as a resolvable
    non-ancestor."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-shallow-repository"],
            cwd=repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0:
        return False
    return result.stdout.strip() == "true"


def _pr_state(repo: Path, pr_number: int) -> str | None:
    """Live PR state via `gh`, or None if it cannot be determined (no
    `gh`, no auth, no network, timeout, or the PR doesn't exist). None
    means UNVERIFIABLE, never a finding -- see the module docstring:
    `Open PRs:` needs `gh` auth that CI does not have. Run with cwd=repo
    so `gh` resolves the GitHub repository from that checkout's own
    remote, not whatever repo this process happens to be started in."""
    try:
        result = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--json", "state", "--jq", ".state"],
            cwd=repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=20,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    state = result.stdout.strip()
    return state or None


def _derive_proof_state_lines(repo: Path) -> list[str]:
    """Re-derive the "Deliverable proof state" content lines by calling
    scripts/lwb_handoff.py's OWN `_proof_state_lines()` directly, rather
    than maintaining a second copy of that logic here. Two independent
    implementations of the same derivation is exactly how this coupling
    broke before (see the module docstring): they drift, and then either
    a correct file fails forever or the gate silently stops checking. One
    function, called from both scripts, cannot drift from itself."""
    import lwb_handoff  # local import: only needed when a HANDOFF.md exists

    return lwb_handoff._proof_state_lines(repo / "proof")


# ---------------------------------------------------------------------------
# Logical-line joining
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^\s*#{1,6}\s")
_BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_BLOCKQUOTE_RE = re.compile(r"^\s*>")
_TABLE_RE = re.compile(r"^\s*\|")

# Invisible "format" characters (Unicode general category Cf) that can sit
# inside a label with no visible trace -- ZERO WIDTH SPACE, ZERO WIDTH
# NON-JOINER, ZERO WIDTH JOINER, the BOM / ZERO WIDTH NO-BREAK SPACE, WORD
# JOINER, SOFT HYPHEN and MONGOLIAN VOWEL SEPARATOR among them. This used to
# be a hand-enumerated regex naming exactly four code points
# (U+200B/200C/200D/FEFF); an adversarial review found three more members of
# the same class -- U+2060, U+00AD, U+180E -- that the enumeration simply
# never named and which therefore evaded it. Stripping by CATEGORY rather
# than by an enumerated list closes the whole class at once: any Cf
# character is by definition intended to be invisible formatting, not
# content, so removing all of them (not just the four originally spotted)
# cannot lose real text. Stripped alongside NFKC below.
def _strip_format_chars(s: str) -> str:
    return "".join(ch for ch in s if unicodedata.category(ch) != "Cf")


def _normalize_segment(s: str) -> str:
    """NFKC-normalise a single physical line's text and strip invisible
    Cf-category characters, closing a fullwidth colon (U+FF1A -> ':') and
    a zero-width space (or any other Cf character) hidden inside a label.
    Applied per PHYSICAL line, before joining, so the length change NFKC
    can introduce never crosses a physical-line boundary and the
    char-to-lineno offset map built during joining stays correct -- see
    `_build_logical_lines`.

    Deliberately does NOT close every Unicode evasion: an en dash is a
    genuinely different character, not an NFKC equivalent of a colon, and
    a Cyrillic homoglyph substitution (e.g. U+0430 for Latin "a") needs
    confusable folding, which the stdlib does not provide. See the module
    docstring, "KNOWN EVASIONS", for why those are left open by design.
    """
    return _strip_format_chars(unicodedata.normalize("NFKC", s))


def _line_kind(line: str) -> str:
    if not line.strip():
        return "blank"
    if _HEADING_RE.match(line):
        return "heading"
    if _BULLET_RE.match(line):
        return "bullet"
    if _BLOCKQUOTE_RE.match(line):
        return "blockquote"
    if _TABLE_RE.match(line):
        return "table"
    return "text"


def _normalize_table_row(text: str) -> str:
    """`| main SHA | <sha> |` -> `main SHA <sha>`. Cell separators are
    normalised to whitespace so every ordinary volatile pattern -- built
    on whitespace adjacency -- can see across what used to be a `|`
    boundary, instead of a table row silently defeating every pattern at
    once."""
    inner = text.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    cells = [c.strip() for c in inner.split("|")]
    return " ".join(c for c in cells if c)


@dataclass
class LogicalLine:
    text: str
    first_lineno: int
    kind: str
    # Parallel to `text`: char_linenos[i] is the physical line that
    # produced text[i]. Lets a match be mapped back to the physical
    # line(s) it actually came from, so an escape comment on ONE
    # physical line of a joined paragraph cannot exempt a claim that
    # lives on a different physical line of the same paragraph.
    char_linenos: list[int]


def _build_logical_lines(physical: list[tuple[int, str, bool]]) -> list[LogicalLine]:
    """`physical` is a list of (1-based lineno, raw line text, skip) --
    `skip` marks lines inside a fence or inside the HANDOFF generated
    block, which are never joined into ordinary prose logical lines."""
    result: list[LogicalLine] = []
    parts: list[tuple[int, str]] = []  # (physical lineno, stripped segment)
    kind = ""
    prev_kind = None

    def flush() -> None:
        nonlocal parts, kind
        if parts:
            if kind == "table":
                # A table row is never joined with a neighbour (see
                # starts_new below), so `parts` holds exactly one segment.
                row_lineno = parts[0][0]
                normalized = _normalize_table_row(parts[0][1])
                result.append(
                    LogicalLine(normalized, row_lineno, kind, [row_lineno] * len(normalized))
                )
            else:
                chars: list[str] = []
                linenos: list[int] = []
                for i, (lineno, seg) in enumerate(parts):
                    if i > 0:
                        chars.append(" ")
                        linenos.append(parts[i - 1][0])
                    chars.append(seg)
                    linenos.extend([lineno] * len(seg))
                result.append(LogicalLine("".join(chars), parts[0][0], kind, linenos))
        parts = []

    for lineno, raw_line, skip in physical:
        if skip or not raw_line.strip():
            flush()
            prev_kind = None
            continue
        # Normalise PER PHYSICAL LINE, before classification and before
        # joining: NFKC can change a segment's length (a fullwidth colon
        # is 1 char, ':' is 1 char, but that is not true of every NFKC
        # rewrite in general), and doing this per-line -- rather than on
        # the already-joined paragraph -- guarantees the length change
        # never crosses a physical-line boundary, so char_linenos below
        # stays correctly aligned to physical lines.
        line = _normalize_segment(raw_line)
        this_kind = _line_kind(line)
        starts_new = (
            this_kind in ("heading", "bullet", "table")
            or not parts
            or (this_kind == "blockquote" and prev_kind != "blockquote")
            or (this_kind == "text" and prev_kind == "blockquote")
        )
        if starts_new:
            flush()
            parts = [(lineno, line.strip())]
            kind = this_kind
        else:
            parts.append((lineno, line.strip()))
        prev_kind = this_kind
    flush()
    return result


# ---------------------------------------------------------------------------
# Quote / blockquote exemption
# ---------------------------------------------------------------------------

_OPEN_QUOTES = {'"', "“", "'", "‘"}
_CLOSE_QUOTES = {'"', "”", "'", "’"}


def _is_quote_exempt(text: str, start: int, end: int, kind: str) -> bool:
    if kind == "blockquote":
        return True
    before = text[:start].rstrip()
    after = text[end:].lstrip()
    if not before or not after:
        return False
    if before[-1] not in _OPEN_QUOTES or after[0] not in _CLOSE_QUOTES:
        return False
    window = before[:-1][-80:]
    return bool(ATTRIBUTION_VERBS.search(window))


# ---------------------------------------------------------------------------
# Per-file scan
# ---------------------------------------------------------------------------


def _escaped_linenos(ll: "LogicalLine") -> dict[int, bool]:
    """Physical linenos, within this logical line, that carry a
    `volatile-ok` comment -> whether that comment's reason is valid. The
    escape is scoped to the PHYSICAL line the comment sits on (found via
    char_linenos), not the whole joined paragraph -- see the module
    docstring: one legitimately-escaped clause must not shield an
    unrelated claim elsewhere in the same hard-wrapped paragraph."""
    escaped: dict[int, bool] = {}
    for m in ESCAPE_COMMENT.finditer(ll.text):
        reason = m.group(1).strip().lower()
        valid = reason in VOLATILE_OK_REASONS
        for lineno in set(ll.char_linenos[m.start() : m.end()]):
            escaped[lineno] = escaped.get(lineno, False) or valid
    return escaped


def _scan_generic(logical_lines: list[LogicalLine], rel_path: str) -> list[Finding]:
    findings: list[Finding] = []
    for ll in logical_lines:
        escaped = _escaped_linenos(ll)
        # Strip escape comments from the text before matching, so their
        # own text (e.g. the word "generated-block") cannot accidentally
        # match a volatile pattern.
        scan_text = ESCAPE_COMMENT.sub(lambda m: " " * len(m.group(0)), ll.text)
        raw_hits: list[tuple[int, int, str, str]] = []  # (start, end, label, matched text)
        for label, pattern in VOLATILE_PATTERNS:
            for pm in pattern.finditer(scan_text):
                if _is_quote_exempt(scan_text, pm.start(), pm.end(), ll.kind):
                    continue
                match_linenos = set(ll.char_linenos[pm.start() : pm.end()])
                if match_linenos and all(escaped.get(ln) for ln in match_linenos):
                    continue
                raw_hits.append((pm.start(), pm.end(), label, pm.group(0)))
        # Several patterns can fire on the same phrase (e.g. "N open PRs"
        # and "there is/are ... open PR(s)" both matching "one open PR").
        # Keep the first (by pattern-list order, i.e. most specific-first)
        # non-overlapping hit per span rather than reporting the same
        # claim twice.
        raw_hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
        taken: list[tuple[int, int]] = []
        for start, end, label, matched in raw_hits:
            if any(start < t_end and end > t_start for t_start, t_end in taken):
                continue
            taken.append((start, end))
            findings.append(Finding(rel_path, ll.first_lineno, label, matched))
    return findings


def _scan_escape_errors(logical_lines: list[LogicalLine], rel_path: str) -> list[str]:
    errors: list[str] = []
    for ll in logical_lines:
        for m in ESCAPE_COMMENT.finditer(ll.text):
            reason = m.group(1).strip().lower()
            if reason in VOLATILE_OK_REASONS:
                continue
            linenos = sorted(set(ll.char_linenos[m.start() : m.end()])) or [ll.first_lineno]
            allowed = ", ".join(sorted(VOLATILE_OK_REASONS))
            errors.append(
                f"{rel_path}:{linenos[0]}: volatile-ok reason {reason!r} is not in the "
                f"closed enum ({allowed})"
            )
    return errors


def _scan_generated_block(
    repo: Path, rel_path: str, block_lines: list[tuple[int, str]]
) -> tuple[list[Finding], list[Info]]:
    """block_lines: (lineno, raw text) for every physical line strictly
    between BEGIN_MARKER and END_MARKER (exclusive of the markers)."""
    findings: list[Finding] = []
    infos: list[Info] = []

    i = 0
    n = len(block_lines)
    while i < n:
        lineno, line = block_lines[i]
        stripped = line.strip()

        if stripped.startswith("Generated:"):
            infos.append(Info(rel_path, lineno, f"timestamp field, not checked: {stripped}"))
            i += 1
            continue

        if re.match(r"^main SHA:", stripped, re.IGNORECASE):
            recorded = stripped.split(":", 1)[1].strip()

            # Reviewer finding #1: validate BEFORE calling git at all. A
            # revision expression, a flag, a placeholder, an empty string
            # or a bare digit must never reach a git subprocess as if it
            # were a commit-ish -- and must FAIL, not pass or "info".
            if not _looks_like_sha(recorded):
                findings.append(
                    Finding(
                        rel_path,
                        lineno,
                        "invalid main SHA value in generated block",
                        f"{stripped} (not a 7-40 character hex commit sha)",
                    )
                )
                i += 1
                continue

            live = _live_main_sha(repo)
            if live is None:
                infos.append(
                    Info(rel_path, lineno, f"main SHA could not be re-derived here: {stripped}")
                )
                i += 1
                continue

            if _sha_matches(recorded, live):
                # Equal (mod short-sha prefix matching): the block's claim
                # is true right now, and live main (HEAD) is always
                # resolvable regardless of clone depth. No info line, a
                # plain pass.
                pass
            else:
                # Reviewer finding #2: pass ONLY on equal-or-first-parent,
                # not "any ancestor". A squash merge advances main by
                # exactly one commit past what was recorded, so live
                # main's first parent is the precise, no-age-bound rule --
                # not "the root commit still counts forever". Always
                # attempt the resolution, even in a shallow clone: a
                # shallow clone deeper than 1, or one that happens to
                # include the parent, CAN resolve it, and refusing to try
                # would turn a provable pass into a needless failure.
                live_parent = _rev_parse(repo, live + "^1")
                if live_parent is not None and _sha_matches(recorded, live_parent):
                    # Reviewer finding #4: git PROVED this relationship --
                    # it must not carry the UNVERIFIABLE prefix, which
                    # would mislabel a git-verified fact as an unresolved
                    # question.
                    infos.append(
                        Info(
                            rel_path,
                            lineno,
                            f"recorded main SHA {recorded} is live main's first parent "
                            f"{live_parent} (live main is now {live}) -- verified by git",
                            prefix="INFO (git-verified)",
                        )
                    )
                elif live_parent is None and _is_shallow_repository(repo):
                    # THE FIX TO THE SECOND FIX: `main^1` failing to
                    # resolve in a shallow clone means "this clone's depth
                    # truncated the parent out", NOT "the parent is
                    # provably something else". Calling this "stale" is a
                    # false accusation -- the recorded value may well be
                    # correct, this clone just cannot prove it, which is
                    # the mirror image of finding #4 (a git-PROVEN fact
                    # mislabelled UNVERIFIABLE; here an UNPROVEN
                    # accusation was mislabelled as a proven fact). Still
                    # exits non-zero -- per the reviewer, a shallow clone
                    # must never silently pass -- but under a DISTINCT
                    # reason that does not accuse the file of being wrong.
                    findings.append(
                        Finding(
                            rel_path,
                            lineno,
                            "main SHA undeterminable in a shallow clone",
                            f"{stripped} (live: {live}; main^1 is not present at this clone's "
                            "depth, so this cannot be proven equal to live main's first "
                            "parent -- the recorded value may be correct; re-run with "
                            "fetch-depth: 0 to decide)",
                        )
                    )
                else:
                    # Either a full clone (main^1 resolves but does not
                    # match, or main has no parent at all -- e.g. it IS
                    # the root commit), or a shallow clone where main^1
                    # resolved anyway and simply did not match. Either
                    # way git has actually determined the value is wrong.
                    findings.append(
                        Finding(
                            rel_path,
                            lineno,
                            "stale main SHA in generated block",
                            f"{stripped} (live: {live}, live main's first parent: "
                            f"{live_parent!r})",
                        )
                    )
            i += 1
            continue

        if stripped == "Open PRs:":
            i += 1
            any_unverifiable = False
            while i < n and block_lines[i][1].strip():
                pr_lineno, pr_line = block_lines[i]
                pr_text = pr_line.strip()
                pr_match = re.match(r"^#(\d+)\s", pr_text)
                if pr_match:
                    number = int(pr_match.group(1))
                    state = _pr_state(repo, number)
                    if state is None:
                        any_unverifiable = True
                    elif state != "OPEN":
                        findings.append(
                            Finding(
                                rel_path,
                                pr_lineno,
                                "stale open-PR listing in generated block",
                                f"#{number} listed as open but gh reports {state}: {pr_text}",
                            )
                        )
                i += 1
            if any_unverifiable:
                infos.append(
                    Info(rel_path, lineno, "Open PRs listing could not be fully re-derived (no gh auth here)")
                )
            continue

        if stripped == "Deliverable proof state (from proof/):":
            i += 1
            recorded_lines: list[str] = []
            while i < n and block_lines[i][1].strip():
                recorded_lines.append(block_lines[i][1].strip())
                i += 1
            derived_lines = _derive_proof_state_lines(repo)
            if sorted(recorded_lines) != sorted(derived_lines):
                findings.append(
                    Finding(
                        rel_path,
                        lineno,
                        "stale deliverable proof state in generated block",
                        f"recorded={recorded_lines!r} re-derived={derived_lines!r}",
                    )
                )
            continue

        i += 1

    return findings, infos


def _scan_text(repo: Path, rel_path: str, text: str) -> tuple[list[Finding], list[Info], list[str]]:
    errors: list[str] = []
    lines = text.splitlines()
    is_handoff = rel_path == HANDOFF_FILENAME or rel_path.endswith("/" + HANDOFF_FILENAME)

    # Pass 1: fences and (if HANDOFF.md) markers.
    fence_open = False
    begin_positions: list[int] = []
    end_positions: list[int] = []
    skip = [False] * len(lines)

    for idx, line in enumerate(lines):
        if FENCE_MARK.match(line):
            fence_open = not fence_open
            skip[idx] = True
            continue
        if fence_open:
            skip[idx] = True
            continue
        if is_handoff and BEGIN_MARKER in line:
            begin_positions.append(idx)
        if is_handoff and END_MARKER in line:
            end_positions.append(idx)

    if fence_open:
        errors.append(f"{rel_path}: unclosed code fence (``` opened but never closed)")

    handoff_ok = False
    if is_handoff:
        if len(begin_positions) != 1 or len(end_positions) != 1:
            errors.append(
                f"{rel_path}: HANDOFF generated-block marker mismatch -- expected exactly one "
                f"{BEGIN_MARKER!r} and one {END_MARKER!r}, found {len(begin_positions)} begin "
                f"marker(s) / {len(end_positions)} end marker(s)"
            )
        elif begin_positions[0] >= end_positions[0]:
            errors.append(
                f"{rel_path}: HANDOFF generated-block marker mismatch -- {END_MARKER!r} "
                f"appears before {BEGIN_MARKER!r}"
            )
        else:
            handoff_ok = True

    findings: list[Finding] = []
    infos: list[Info] = []

    if handoff_ok:
        begin_idx = begin_positions[0]
        end_idx = end_positions[0]
        for idx in range(begin_idx, end_idx + 1):
            skip[idx] = True
        block_lines = [(idx + 1, lines[idx]) for idx in range(begin_idx + 1, end_idx)]
        gen_findings, gen_infos = _scan_generated_block(repo, rel_path, block_lines)
        findings.extend(gen_findings)
        infos.extend(gen_infos)

    physical = [(idx + 1, lines[idx], skip[idx]) for idx in range(len(lines))]
    logical_lines = _build_logical_lines(physical)
    findings.extend(_scan_generic(logical_lines, rel_path))
    errors.extend(_scan_escape_errors(logical_lines, rel_path))

    return findings, infos, errors


def check(repo: Path) -> list[Finding]:
    findings, _infos, _errors = _check_all(repo)
    return findings


def check_errors(repo: Path) -> list[str]:
    _findings, _infos, errors = _check_all(repo)
    return errors


def _check_all(repo: Path) -> tuple[list[Finding], list[Info], list[str]]:
    findings: list[Finding] = []
    infos: list[Info] = []
    errors: list[str] = []
    for path in _tracked_md_files(repo):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = path.relative_to(repo).as_posix()
        f, i, e = _scan_text(repo, rel, text)
        findings.extend(f)
        infos.extend(i)
        errors.extend(e)
    return findings, infos, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=".", help="repo root (default: current directory)")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    findings, infos, errors = _check_all(repo)

    for i in infos:
        print(i.render())

    if findings or errors:
        for f in findings:
            print(f"FAIL: {f.render()}")
        for e in errors:
            print(f"ERROR: {e}")
        print(
            f"\n{len(findings)} volatile state claim(s), {len(errors)} structural error(s) "
            "found in tracked .md files. Replace a claim with a live command (see "
            "lwb_status.py), or if it is genuinely historical/generated/illustrative, add "
            "'<!-- volatile-ok: REASON -->' with REASON from the closed enum."
        )
        return 1

    print("lwb-check-state-claims check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

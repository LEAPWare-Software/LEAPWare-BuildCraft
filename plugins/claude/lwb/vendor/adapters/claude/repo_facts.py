"""Claude adapter, IMPURE half: observe the repository, freeze it into data.

`core/lwb_core` does no I/O (docs/architecture.md), so a rule that needs to
know which branch is checked out, or which proof records exist, cannot go
and look. This module looks, and returns a `lwb_core.events.RepoFacts` the
engine can hand to pure rules. It is the only place in the Claude adapter
that touches the filesystem; `hook_io.py` stays a pure dict-to-dataclass
translator, and this module is called from `bin/lwb_hook.py` alongside the
other I/O that script already does.

## No subprocess, on purpose

The branch name is read out of `.git/HEAD`, NOT by running `git
rev-parse`. Owner directive 8 (docs/architecture.md#the-hook-launch-method)
is that the plugin must not depend on this machine -- and `git` being on
`PATH`, in the environment Claude Code hands a hook, is exactly such a
dependency. It is also a per-tool-call cost: this runs before every Bash
call, and spawning a process on Windows to learn something two file reads
already tell us is not a trade worth making. `.git/HEAD`'s format is part
of git's on-disk repository layout, which is stable and documented
(gitrepository-layout(5)).

## Fail-quiet

Every failure here returns None or an empty result rather than raising.
A hook that cannot read a directory must not block a tool call, and the
rule that consumes this treats "no facts" as "no opinion" -- see
`lwb_core/rules/lwb_proof_required.py`. Stdlib only.
"""

from __future__ import annotations

import json
import os
import re
import zlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from lwb_core.events import RepoFacts

#: Where proof records live, relative to the repository root, in priority
#: order. `proof/` is this repository's own layout; `.lwb/proof/` is
#: offered so a CONSUMING repo can adopt the protocol without taking a
#: top-level directory name it may already use for something else.
PROOF_DIRS = ("proof", ".lwb/proof")

#: Stop walking up after this many parents. A hook must not spend
#: unbounded time on a path that is not in a repository at all.
_MAX_PARENTS = 40

#: A repository with more records than this is not a layout this rule was
#: designed for; read a bounded number so one pathological directory
#: cannot stall every Bash call.
_MAX_RECORDS = 5000

#: A full git object id, sha1 (40 hex) or sha256 (64 hex). Used to reject
#: anything read out of a ref file or `.git/HEAD` that is not actually a
#: resolved object id -- an abbreviated or symbolic value must never be
#: mistaken for one, since it would then be fed straight into a loose
#: object path.
_FULL_SHA_RE = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")

#: Same convention `scripts/lwb_check_proof.py::SQUASH_SUBJECT_RE` uses: a
#: GitHub squash-merge commit's subject ends with `(#N)`. Kept as a
#: separate constant (not imported from that script, which is a CI tool
#: this fast, per-hook module must not depend on) -- see
#: `collect_landed_unproven`.
SQUASH_SUBJECT_RE = re.compile(r"\(#(\d+)\)\s*$")

#: Bound on how many commits `collect_landed_unproven` will walk
#: (first-parent only) from HEAD. Matches `_MAX_PARENTS`'s reasoning: this
#: runs on every hook event (see `collect_repo_facts`), so it must stay
#: cheap even on a long-lived branch.
_MAX_LANDED_WALK = 40

#: Cap on how many unproven landed commits are reported. A rule's Finding
#: reason is meant to be read, not paged through.
_MAX_LANDED_UNPROVEN = 20

#: `proof/exempt.json` (or `.lwb/proof/exempt.json`) is a small, hand-
#: maintained carve-out list, never a bulk data file; refuse to parse one
#: larger than this rather than spend the read on something that is not
#: the file this convention describes.
_MAX_EXEMPT_BYTES = 1_000_000

#: Same reasoning, for the single proof record `collect_matched_proof_facts`
#: reads (the one named for the current branch). Proof records in this
#: repository run a few KB; refuse anything wildly larger rather than read
#: it whole before every Bash call.
_MAX_PROOF_RECORD_BYTES = 2_000_000


def find_repo_root(start: Optional[str]) -> Optional[Path]:
    """The nearest ancestor of `start` containing a `.git` entry, or None.

    `.git` may be a directory (ordinary clone) or a FILE (a worktree or a
    submodule, where it holds a `gitdir:` pointer). Both count as a
    repository root, which matters here because this repo's own work
    happens in worktrees under `.worktrees/`.
    """
    if not start:
        return None
    try:
        current = Path(start).resolve()
    except (OSError, ValueError):
        return None

    for _ in range(_MAX_PARENTS):
        try:
            if (current / ".git").exists():
                return current
        except OSError:
            return None
        if current.parent == current:
            return None
        current = current.parent
    return None


def _git_dir(repo_root: Path) -> Optional[Path]:
    """Resolve `<root>/.git` to the directory that actually holds HEAD.

    A plain clone: `.git` is that directory. A worktree: `.git` is a file
    reading `gitdir: <path>`, and HEAD lives at `<path>/HEAD` -- the
    worktree's own HEAD, which is what makes the branch name correct
    inside a worktree rather than the main checkout's branch.
    """
    dot_git = repo_root / ".git"
    try:
        if dot_git.is_dir():
            return dot_git
        if not dot_git.is_file():
            return None
        text = dot_git.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None

    prefix = "gitdir:"
    if not text.startswith(prefix):
        return None
    pointer = text[len(prefix) :].strip()
    if not pointer:
        return None
    candidate = Path(pointer)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    try:
        return candidate if candidate.is_dir() else None
    except OSError:
        return None


def read_branch_ex(repo_root: Path) -> "Tuple[Optional[str], Optional[str]]":
    """`(branch, incomplete_reason)`.

    `branch` is None for a detached HEAD (HEAD holds a raw object id, not
    a ref), for a symbolic ref outside `refs/heads/`, for a repo with no
    `.git` this function could locate, AND for `.git/HEAD` legitimately
    not existing (`FileNotFoundError`) -- all of those are "there is
    nothing to report", the safe, ordinary None this module has always
    returned.

    `incomplete_reason` is set ONLY when `.git/HEAD` exists but a read of
    it failed for some OTHER reason (permission denied, an I/O error) --
    "could not check", not "checked, nothing there". An independent
    reviewer measured this conflation directly: `chmod 000 .git/HEAD` on a
    branch WITH a real proof-required violation still produced a bare
    `{"permissionDecision":"allow"}`, byte for byte the same shape as a
    clean, quiet pass -- reached without ever touching either of the two
    silent-failure markers this PR already fixed. See `RepoFacts.facts_incomplete`.
    """
    git_dir = _git_dir(repo_root)
    if git_dir is None:
        return None, None
    head_path = git_dir / "HEAD"
    try:
        head = head_path.read_text(encoding="utf-8", errors="replace").strip()
    except FileNotFoundError:
        return None, None
    except OSError as exc:
        return None, f"could not read {head_path}: {exc.__class__.__name__}: {exc}"

    marker = "ref: refs/heads/"
    if not head.startswith(marker):
        return None, None
    branch = head[len(marker) :].strip()
    return branch or None, None


def read_branch(repo_root: Path) -> Optional[str]:
    """The checked-out branch name, or None. See `read_branch_ex` for the
    version that also reports WHY, when the None is because a read
    failed rather than because there is nothing to report.
    """
    branch, _ = read_branch_ex(repo_root)
    return branch


def collect_proof_ids(repo_root: Path) -> List[str]:
    """Ids of every `*.json` record under the known proof directories, RECURSIVE.

    An id is the record's path RELATIVE TO the proof directory, with the
    `.json` suffix removed, joined with forward slashes regardless of
    platform. `proof/24.json` -> `"24"` (unchanged -- a flat id is just the
    one-segment case of this). `proof/feat/x-12.json` -> `"feat/x-12"`.

    This is `directory.glob("*.json")` widened to `directory.rglob(...)`,
    which matters because a branch name containing a slash (`feat/x-12`,
    the common case) names a nested path when read literally as
    `proof/<branch>.json` -- see `lwb_proof_required._matching_record` and
    its message. Before this walked recursively, that path was invisible
    to a flat glob, so the rule's own "add proof/<claim>.json" instruction
    could never be satisfied for such a branch. `_matching_record` compares
    `repo.branch` against these ids VERBATIM, so producing a native-separator
    id on Windows (`os.sep` is a backslash) would reproduce the same bug
    platform-specifically -- hence the explicit forward-slash join below
    rather than `str(path)` or a Windows-native `PurePath`'s own separator.

    Contents are NOT read or validated: whether a record is well-formed,
    self-certified or complete is `scripts/lwb_check_proof.py`'s job in
    CI, where there is time to do it properly. This runs before a tool
    call, so it does the cheapest thing that answers the rule's question
    -- does a record for this claim exist at all.
    """
    ids, _ = collect_proof_ids_ex(repo_root)
    return ids


def collect_proof_ids_ex(repo_root: Path) -> "Tuple[List[str], Optional[str]]":
    """`(ids, incomplete_reason)` -- see `collect_proof_ids` for `ids`.

    `directory.rglob(...)` does not raise for a directory that simply does
    not exist (the ordinary case for a repo that has adopted only one of
    the two `PROOF_DIRS`): it yields nothing, which is legitimately "no
    records here", not an incompleteness. It DOES raise when the
    directory exists but iterating it fails -- permission denied being
    the case an independent reviewer measured: `chmod 000 proof/` with
    the SAME record still on disk produced `"0 record(s) found ... none
    matching"`, a false claim of a count this function never actually
    obtained. `incomplete_reason` carries that distinction forward so the
    rule can refuse to treat "could not read the directory" as "read it,
    it was empty". See `RepoFacts.facts_incomplete`.
    """
    ids: List[str] = []
    seen = set()
    incomplete_reason: Optional[str] = None
    for relative in PROOF_DIRS:
        directory = repo_root.joinpath(*relative.split("/"))
        try:
            entries = sorted(directory.rglob("*.json"))
        except OSError as exc:
            incomplete_reason = incomplete_reason or (
                f"could not read {directory}: {exc.__class__.__name__}: {exc}"
            )
            continue
        for entry in entries:
            if len(ids) >= _MAX_RECORDS:
                return ids, incomplete_reason
            try:
                if not entry.is_file():
                    continue
            except OSError:
                continue
            relative_parts = entry.relative_to(directory).parts
            stem_parts = relative_parts[:-1] + (entry.stem,)
            record_id = "/".join(stem_parts)
            if record_id not in seen:
                seen.add(record_id)
                ids.append(record_id)
    return ids, incomplete_reason


def _resolve_ref_sha(git_dir: Path, ref: str) -> Optional[str]:
    """The object id `ref` (e.g. `refs/heads/main`) currently points at.

    Tries the loose ref file first (the ordinary case), then falls back to
    `packed-refs` (written when refs are packed, e.g. after `git gc` or a
    fresh clone that packed its refs). Returns None -- never raises -- for
    every failure mode: missing file, unreadable file, or content that
    does not look like a full object id (a corrupt or truncated ref).
    """
    ref_path = git_dir.joinpath(*ref.split("/")) if ref else git_dir
    try:
        text = ref_path.read_text(encoding="utf-8", errors="replace").strip()
        if _FULL_SHA_RE.match(text):
            return text
    except OSError:
        pass

    packed = git_dir / "packed-refs"
    try:
        content = packed.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in content.splitlines():
        if not line or line[0] in "#^":
            continue
        sha, _, name = line.partition(" ")
        if name.strip() == ref and _FULL_SHA_RE.match(sha):
            return sha
    return None


def resolve_head_commit(repo_root: Path) -> Optional[str]:
    """The object id HEAD currently resolves to, or None.

    Companion to `read_branch_ex`: that function reports the branch NAME
    a symbolic HEAD points at; this reports the commit id, following the
    ref when HEAD is symbolic and reading HEAD's own content directly
    when it is detached (a raw object id). Used by
    `collect_landed_unproven`, which needs somewhere to start walking.

    Returns None for every case that function's `branch is None` already
    covers when there is genuinely nothing to resolve (no `.git`, no
    `HEAD`, an unreadable ref) -- this is deliberately as quiet as the
    rest of this module: a failure here means the coverage walk below
    simply does not run, never that it raises.
    """
    git_dir = _git_dir(repo_root)
    if git_dir is None:
        return None
    try:
        head = (git_dir / "HEAD").read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None

    marker = "ref: "
    if head.startswith(marker):
        return _resolve_ref_sha(git_dir, head[len(marker):].strip())
    if _FULL_SHA_RE.match(head):
        return head
    return None


def _read_loose_commit(git_dir: Path, sha: str) -> Optional[bytes]:
    """The raw body of loose commit object `sha`, or None.

    None covers every reason this could fail to produce a commit body:
    the object is packed rather than loose (the ORDINARY case for any
    history older than the working set -- a fresh clone transfers a
    packfile, not loose objects, and `git gc` packs everything), it does
    not exist, it is not readable, it does not decompress, or it
    decompresses to something that is not a commit object at all. Every
    one of these is a legitimate reason for `collect_landed_unproven` to
    stop walking rather than a fault to raise -- see that function's
    docstring for why a stop here is an accepted, named limit rather
    than an error.
    """
    sha = sha.lower()
    path = git_dir / "objects" / sha[:2] / sha[2:]
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    try:
        decompressed = zlib.decompress(raw)
    except zlib.error:
        return None
    nul = decompressed.find(b"\0")
    if nul < 0 or not decompressed[:nul].startswith(b"commit"):
        return None
    return decompressed[nul + 1:]


def _parse_commit_body(body: bytes) -> "Tuple[List[str], str]":
    """`(parent object ids, subject line)` from a raw commit object body.

    A commit object is a block of `key value` header lines (`tree`,
    `parent` -- zero or more, in birth order -- `author`, `committer`,
    optionally a multi-line `gpgsig`, ...), a single blank line, then the
    commit message. A `gpgsig` block's continuation lines are each
    prefixed with one space, which is what makes a plain blank-line scan
    safe here: no legitimate header continuation line is ever actually
    empty, so the first zero-length line really is the separator, and
    every other header this function does not care about (`tree`,
    `author`, `gpgsig` and its continuations, ...) is simply skipped
    rather than parsed.
    """
    lines = body.split(b"\n")
    parents: List[str] = []
    i = 0
    for i, line in enumerate(lines):
        if line == b"":
            break
        if line.startswith(b"parent "):
            parent = line[len(b"parent "):].decode("ascii", errors="replace").strip()
            if _FULL_SHA_RE.match(parent):
                parents.append(parent)
    else:
        i = len(lines)
    message_lines = lines[i + 1:]
    subject = message_lines[0].decode("utf-8", errors="replace") if message_lines else ""
    return parents, subject


def _read_exempt_shas(repo_root: Path) -> Dict[str, str]:
    """`proof/exempt.json`'s (or `.lwb/proof/exempt.json`'s) `"merges"` map,
    or `{}` for every failure mode -- missing file, oversized, unreadable,
    not valid JSON, or not shaped as documented. Mirrors
    `scripts/lwb_check_proof.py::_exempt_shas`, re-implemented here rather
    than imported so this fast, per-hook module stays independent of that
    CI script. Consulted by `collect_landed_unproven` so a merge this
    repository has already named as a historical, deliberately-unproven
    gap is not reported as a fresh one.
    """
    for relative in PROOF_DIRS:
        path = repo_root.joinpath(*relative.split("/"), "exempt.json")
        try:
            if not path.is_file() or path.stat().st_size > _MAX_EXEMPT_BYTES:
                continue
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            merges = data.get("merges")
            if isinstance(merges, dict):
                return {k: v for k, v in merges.items() if isinstance(k, str)}
    return {}


def collect_landed_unproven(repo_root: Path) -> Tuple[str, ...]:
    """Best-effort, bounded, LOCAL scan for landed deliverables with no record.

    Adapts `scripts/lwb_check_proof.py::check_coverage`'s logic -- a
    squash-merge commit (subject ending `(#N)`) whose PR number has no
    matching `proof/*.json` record, with `proof/exempt.json`'s carve-out
    honoured -- to a form this I/O-bounded, subprocess-free, per-hook
    module can run: rather than `git log` over a range, it walks loose
    commit objects directly (see `_read_loose_commit`), first-parent
    only, from HEAD, up to `_MAX_LANDED_WALK` commits, stopping the
    moment it reaches one that is not a loose object.

    That stopping point is an ACCEPTED, NAMED limit, not a bug: a fresh
    clone transfers its history as a packfile, and `git gc` packs loose
    objects once there are enough of them, so a repository that has not
    seen fresh local commits recently may yield nothing here at all, or
    stop after only a few. This under-matches on purpose, the same
    posture `lwb_proof_required` documents -- a merge this scan cannot
    see is a missed warning, not a false one, and CI's own
    `lwb-proof-coverage` job (`scripts/lwb_check_proof.py --coverage`,
    running `git log` with a real subprocess and full history) remains
    the authoritative check for THIS repository. This is the version a
    consuming repo gets inside its `PreToolUse` hook, where neither a
    subprocess nor unbounded history access is available -- see this
    module's own "No subprocess, on purpose" section.

    Returns a tuple of `"<sha prefix> (#<N>)"` strings, most recent
    first, capped at `_MAX_LANDED_UNPROVEN`. An empty tuple means
    "found none within what was walkable", not "confirmed fully
    covered" -- see `RepoFacts.landed_unproven`.
    """
    git_dir = _git_dir(repo_root)
    if git_dir is None:
        return ()
    head_sha = resolve_head_commit(repo_root)
    if head_sha is None:
        return ()

    try:
        known_ids, _ = collect_proof_ids_ex(repo_root)
    except OSError:
        return ()
    known = set(known_ids)
    exempt = _read_exempt_shas(repo_root)

    found: List[str] = []
    sha: Optional[str] = head_sha
    seen = set()
    try:
        for _ in range(_MAX_LANDED_WALK):
            if sha is None or sha in seen:
                break
            seen.add(sha)
            body = _read_loose_commit(git_dir, sha)
            if body is None:
                break  # packed, missing, or unreadable -- accepted stop
            parents, subject = _parse_commit_body(body)
            match = SQUASH_SUBJECT_RE.search(subject)
            if match:
                pr = match.group(1)
                if pr not in known and sha not in exempt and sha[:12] not in exempt:
                    found.append(f"{sha[:12]} (#{pr})")
                    if len(found) >= _MAX_LANDED_UNPROVEN:
                        break
            sha = parents[0] if parents else None
        return tuple(found)
    except Exception:  # noqa: BLE001 - fail-quiet, same contract as the rest of this module
        return tuple(found)


def _branch_proof_path(proof_dir: Path, branch: str) -> Optional[Path]:
    """`<proof_dir>/<branch>.json` as a `Path`, or None for a `branch` this
    must refuse to turn into one: empty, or containing an empty, `.` or
    `..` segment (which would otherwise let a crafted branch name walk a
    read outside `proof_dir`). Mirrors the id convention
    `collect_proof_ids_ex` already produces (forward-slash segments,
    `.json` appended to the last one), so `branch in proof_ids` and "the
    file this function points at exists" agree for every ordinary branch.
    """
    parts = branch.split("/")
    if not parts or any(p in ("", ".", "..") for p in parts):
        return None
    parts[-1] = parts[-1] + ".json"
    return proof_dir.joinpath(*parts)


def collect_matched_proof_facts(
    repo_root: Path, branch: Optional[str]
) -> "Tuple[Optional[bool], Optional[bool]]":
    """`(self_certified, has_failed_command)` for the proof record named
    for `branch`, or `(None, None)` when there is no such record, it is
    oversized, or it could not be read or parsed as a JSON object.

    Reads the CONTENT of exactly one file (bounded by
    `_MAX_PROOF_RECORD_BYTES`) -- unlike every other function in this
    module, which only ever looks at filenames. That is deliberate and
    scoped as narrowly as possible: `rules/lwb_proof_integrity.py` needs
    a cheap, execution-free signal about the ONE record a branch-name
    match makes unambiguous, not a full parse of every record in
    `proof/` on every hook call (see `_MAX_RECORDS`'s reasoning for why
    that would not be cheap).

    `self_certified` is True when the record's own `checked_by` equals
    its own `author`, both non-empty strings -- the record certifying
    itself, the same signal `scripts/lwb_check_proof.py` rejects a
    record for. `has_failed_command` is True when any `commands[]` entry
    records an `exit` that differs from its own `expect_exit` -- a
    command the record itself admits did not pass. Neither re-executes
    anything; both are read straight off the record's own claims.
    """
    if not branch:
        return None, None
    for relative in PROOF_DIRS:
        proof_dir = repo_root.joinpath(*relative.split("/"))
        path = _branch_proof_path(proof_dir, branch)
        if path is None:
            continue
        try:
            if not path.is_file() or path.stat().st_size > _MAX_PROOF_RECORD_BYTES:
                continue
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue

        author = data.get("author")
        checked_by = data.get("checked_by")
        self_certified = (
            isinstance(author, str)
            and isinstance(checked_by, str)
            and bool(author)
            and author == checked_by
        )

        has_failed = False
        commands = data.get("commands")
        if isinstance(commands, list):
            for cmd in commands:
                if not isinstance(cmd, dict):
                    continue
                exit_code = cmd.get("exit")
                expect_exit = cmd.get("expect_exit")
                if (
                    isinstance(exit_code, int)
                    and isinstance(expect_exit, int)
                    and exit_code != expect_exit
                ):
                    has_failed = True
                    break

        return bool(self_certified), has_failed
    return None, None


def collect_repo_facts(cwd: Optional[str] = None) -> Optional[RepoFacts]:
    """Gather the repo facts `lwb_proof_required` needs, or None.

    Returns None when `cwd` is not inside a git repository at all, which
    the rule reads as "no facts gathered" and answers with silence. That
    is the right answer: a Bash call made outside any repository is not a
    publish this protocol has anything to say about.

    When the repo WAS found but a piece of it could not be fully read
    (`.git/HEAD` or a proof directory existing but not readable), the
    returned `RepoFacts.facts_incomplete` is True and `branch` /
    `proof_ids` carry whatever partial answer was still obtained -- never
    silently promoted to "gathered facts, found nothing". See
    `RepoFacts` and `read_branch_ex` / `collect_proof_ids_ex`.

    `landed_unproven` and the `matched_proof_*` fields (feeding
    `rules/lwb_proof_coverage.py` and `rules/lwb_proof_integrity.py`) are
    gathered here too, but neither one can mark `facts_incomplete`: both
    are already-bounded, best-effort scans (see `collect_landed_unproven`
    and `collect_matched_proof_facts`) whose empty/None results are a
    legitimate outcome, not a read failure -- `facts_incomplete` is
    reserved for "something that should have been readable was not".
    """
    root = find_repo_root(cwd if cwd else os.getcwd())
    if root is None:
        return None
    branch, branch_incomplete = read_branch_ex(root)
    proof_ids, proof_incomplete = collect_proof_ids_ex(root)
    reasons = [r for r in (branch_incomplete, proof_incomplete) if r]

    # Both wrapped independently, and separately from the two calls above:
    # an unexpected failure in either of these newer, best-effort scans
    # must degrade only ITS OWN fields, never take down `branch` /
    # `proof_ids` (which lwb_proof_required already depends on) by
    # raising out of this function and turning the whole result into the
    # caller's "repo facts unavailable" case. See these functions' own
    # docstrings for why an empty/None result is already their ordinary,
    # expected outcome; this is one layer more paranoid than that, for a
    # bug neither anticipated.
    try:
        landed_unproven = collect_landed_unproven(root)
    except Exception:  # noqa: BLE001 - fail-quiet, see comment above
        landed_unproven = ()
    try:
        self_certified, has_failed_command = collect_matched_proof_facts(root, branch)
    except Exception:  # noqa: BLE001 - fail-quiet, see comment above
        self_certified, has_failed_command = None, None

    return RepoFacts(
        branch=branch,
        proof_ids=tuple(proof_ids),
        facts_incomplete=bool(reasons),
        facts_incomplete_reason="; ".join(reasons) if reasons else None,
        landed_unproven=landed_unproven,
        matched_proof_self_certified=self_certified,
        matched_proof_has_failed_command=has_failed_command,
    )

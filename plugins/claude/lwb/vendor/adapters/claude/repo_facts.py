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

import os
from pathlib import Path
from typing import List, Optional, Tuple

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
    """
    root = find_repo_root(cwd if cwd else os.getcwd())
    if root is None:
        return None
    branch, branch_incomplete = read_branch_ex(root)
    proof_ids, proof_incomplete = collect_proof_ids_ex(root)
    reasons = [r for r in (branch_incomplete, proof_incomplete) if r]
    return RepoFacts(
        branch=branch,
        proof_ids=tuple(proof_ids),
        facts_incomplete=bool(reasons),
        facts_incomplete_reason="; ".join(reasons) if reasons else None,
    )

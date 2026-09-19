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
from typing import List, Optional

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


def read_branch(repo_root: Path) -> Optional[str]:
    """The checked-out branch name, or None.

    None for a detached HEAD (HEAD holds a raw object id, not a ref), for
    a symbolic ref outside `refs/heads/`, and for any read failure. The
    rule treats None as "cannot identify the claim" and stays silent, so
    None is always a safe answer here.
    """
    git_dir = _git_dir(repo_root)
    if git_dir is None:
        return None
    try:
        head = (git_dir / "HEAD").read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None

    marker = "ref: refs/heads/"
    if not head.startswith(marker):
        return None
    branch = head[len(marker) :].strip()
    return branch or None


def collect_proof_ids(repo_root: Path) -> List[str]:
    """Filename stems of every `*.json` under the known proof directories.

    `proof/24.json` -> `"24"`. Contents are NOT read or validated: whether
    a record is well-formed, self-certified or complete is
    `scripts/lwb_check_proof.py`'s job in CI, where there is time to do it
    properly. This runs before a tool call, so it does the cheapest thing
    that answers the rule's question -- does a record for this claim exist
    at all.
    """
    ids: List[str] = []
    seen = set()
    for relative in PROOF_DIRS:
        directory = repo_root.joinpath(*relative.split("/"))
        try:
            entries = sorted(directory.glob("*.json"))
        except OSError:
            continue
        for entry in entries:
            if len(ids) >= _MAX_RECORDS:
                return ids
            try:
                if not entry.is_file():
                    continue
            except OSError:
                continue
            stem = entry.stem
            if stem not in seen:
                seen.add(stem)
                ids.append(stem)
    return ids


def collect_repo_facts(cwd: Optional[str] = None) -> Optional[RepoFacts]:
    """Gather the repo facts `lwb_proof_required` needs, or None.

    Returns None when `cwd` is not inside a git repository at all, which
    the rule reads as "no facts gathered" and answers with silence. That
    is the right answer: a Bash call made outside any repository is not a
    publish this protocol has anything to say about.
    """
    root = find_repo_root(cwd if cwd else os.getcwd())
    if root is None:
        return None
    return RepoFacts(branch=read_branch(root), proof_ids=tuple(collect_proof_ids(root)))

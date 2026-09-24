"""adapters/claude/repo_facts.collect_landed_unproven, and its plumbing
(`resolve_head_commit`, `_read_loose_commit`, `_parse_commit_body`,
`_read_exempt_shas`), against REAL git repositories -- built with real
`git` subprocess calls IN THE TEST (the module under test must never do
this itself; see `repo_facts.py`'s "No subprocess, on purpose"), so the
loose-object format being read is the real one, not a guess at it.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from adapters.claude.repo_facts import (
    _MAX_LANDED_WALK,
    collect_landed_unproven,
    resolve_head_commit,
)


def _git(args, cwd: Path):
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env={
            "GIT_AUTHOR_NAME": "lwb-test",
            "GIT_AUTHOR_EMAIL": "lwb-test@example.invalid",
            "GIT_COMMITTER_NAME": "lwb-test",
            "GIT_COMMITTER_EMAIL": "lwb-test@example.invalid",
            "PATH": "/usr/bin:/bin:/usr/local/bin",
        },
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def _init_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q", "-b", "main"], root)


def _commit(root: Path, message: str, filename: str = "f.txt") -> str:
    (root / filename).write_text(message, encoding="utf-8")
    _git(["add", filename], root)
    _git(["commit", "-q", "-m", message], root)
    return _git(["rev-parse", "HEAD"], root).strip()


# --------------------------------------------------------------------
# resolve_head_commit
# --------------------------------------------------------------------


def test_resolve_head_commit_follows_a_symbolic_ref(tmp_path):
    _init_repo(tmp_path)
    sha = _commit(tmp_path, "initial")
    assert resolve_head_commit(tmp_path) == sha


def test_resolve_head_commit_reads_a_detached_head_directly(tmp_path):
    _init_repo(tmp_path)
    sha = _commit(tmp_path, "initial")
    _git(["checkout", "-q", "--detach", sha], tmp_path)
    assert resolve_head_commit(tmp_path) == sha


def test_resolve_head_commit_falls_back_to_packed_refs(tmp_path):
    _init_repo(tmp_path)
    sha = _commit(tmp_path, "initial")
    _git(["pack-refs", "--all"], tmp_path)
    assert not (tmp_path / ".git" / "refs" / "heads" / "main").exists()
    assert resolve_head_commit(tmp_path) == sha


def test_resolve_head_commit_is_none_outside_a_repository(tmp_path):
    assert resolve_head_commit(tmp_path) is None


# --------------------------------------------------------------------
# collect_landed_unproven: the ordinary cases
# --------------------------------------------------------------------


def test_an_ordinary_commit_subject_is_not_a_squash_merge(tmp_path):
    _init_repo(tmp_path)
    _commit(tmp_path, "an ordinary commit, not a squash merge")
    assert collect_landed_unproven(tmp_path) == ()


def test_a_squash_merge_subject_with_no_record_is_reported(tmp_path):
    _init_repo(tmp_path)
    sha = _commit(tmp_path, "Ship the thing (#41)")
    gaps = collect_landed_unproven(tmp_path)
    assert len(gaps) == 1
    assert sha[:12] in gaps[0]
    assert "#41" in gaps[0]


def test_a_squash_merge_subject_with_a_matching_record_is_silent(tmp_path):
    _init_repo(tmp_path)
    _commit(tmp_path, "Ship the thing (#41)")
    (tmp_path / "proof").mkdir()
    (tmp_path / "proof" / "41.json").write_text("{}", encoding="utf-8")
    assert collect_landed_unproven(tmp_path) == ()


def test_a_squash_merge_subject_exempted_by_sha_is_silent(tmp_path):
    _init_repo(tmp_path)
    sha = _commit(tmp_path, "Ship the thing (#41)")
    (tmp_path / "proof").mkdir()
    (tmp_path / "proof" / "exempt.json").write_text(
        json.dumps({"merges": {sha: "historical, pre-protocol"}}), encoding="utf-8"
    )
    assert collect_landed_unproven(tmp_path) == ()


def test_a_squash_merge_subject_exempted_by_short_sha_is_silent(tmp_path):
    _init_repo(tmp_path)
    sha = _commit(tmp_path, "Ship the thing (#41)")
    (tmp_path / "proof").mkdir()
    (tmp_path / "proof" / "exempt.json").write_text(
        json.dumps({"merges": {sha[:12]: "historical"}}), encoding="utf-8"
    )
    assert collect_landed_unproven(tmp_path) == ()


def test_several_squash_merges_walked_first_parent_are_all_reported(tmp_path):
    _init_repo(tmp_path)
    _commit(tmp_path, "Ship one (#1)")
    _commit(tmp_path, "Ship two (#2)")
    gaps = collect_landed_unproven(tmp_path)
    assert len(gaps) == 2
    assert any("#1" in g for g in gaps)
    assert any("#2" in g for g in gaps)


def test_no_repository_is_an_empty_tuple_not_an_error(tmp_path):
    assert collect_landed_unproven(tmp_path) == ()


def test_an_empty_repository_with_no_commits_is_an_empty_tuple(tmp_path):
    _init_repo(tmp_path)
    assert collect_landed_unproven(tmp_path) == ()


# --------------------------------------------------------------------
# The accepted, named limit: a packed object stops the walk
# --------------------------------------------------------------------


def test_a_packed_commit_stops_the_walk_rather_than_erroring(tmp_path):
    """A fresh clone transfers history as a packfile, not loose objects --
    this is the ORDINARY case the walk must degrade quietly against, not
    a fault. Repacking is the cheapest way to reproduce it locally."""
    _init_repo(tmp_path)
    _commit(tmp_path, "Ship the thing (#41)")
    _git(["repack", "-ad"], tmp_path)
    assert collect_landed_unproven(tmp_path) == ()


def test_a_loose_head_past_a_packed_history_still_finds_the_loose_part(tmp_path):
    _init_repo(tmp_path)
    _commit(tmp_path, "Ship the old thing (#1)")
    _git(["repack", "-ad"], tmp_path)
    sha = _commit(tmp_path, "Ship the new thing (#2)")
    gaps = collect_landed_unproven(tmp_path)
    assert len(gaps) == 1
    assert sha[:12] in gaps[0]
    assert "#2" in gaps[0]


# --------------------------------------------------------------------
# The bound
# --------------------------------------------------------------------


def test_the_walk_is_bounded(tmp_path):
    """A squash-merge subject past `_MAX_LANDED_WALK` commits back from HEAD
    must NOT be found -- the walk has to stop at its bound rather than
    reading unbounded history on every hook call. Only the OLDEST commit
    matches the squash pattern; everything walked from HEAD backward
    before reaching it is ordinary, so finding nothing here is the
    bound actually doing its job, not a coincidence of no matches
    existing."""
    _init_repo(tmp_path)
    _commit(tmp_path, "Ship the old thing (#1)", filename="f0.txt")
    for i in range(1, _MAX_LANDED_WALK + 5):
        _commit(tmp_path, f"an ordinary commit {i}", filename=f"f{i}.txt")
    assert collect_landed_unproven(tmp_path) == ()

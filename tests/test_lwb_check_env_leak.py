"""Tests for scripts/lwb_check_env_leak.py, working tree AND `--range` history scan.

A working-tree-only scan misses a leak that was committed and then removed
again within the same PR -- it is still sitting in the branch's history,
which a clone or marketplace pull carries in full. These tests build a
throwaway fixture git repo (never this repo's own history) to prove the
`--range` scan catches exactly that case.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lwb_check_env_leak as check_mod  # noqa: E402


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, check=True)


def _init_repo(cwd: Path) -> None:
    _run(["git", "init", "-q"], cwd)
    _run(["git", "config", "user.name", "Fixture"], cwd)
    _run(["git", "config", "user.email", "fixture@example.com"], cwd)


def test_findings_for_line_catches_drive_letter_and_private_name():
    findings = check_mod._findings_for_line("some/file.py", 3, r'path = "C:\Users\example-private-project\thing"')
    assert any("Windows drive letter" in f for f in findings)
    assert any("private-project name leak" in f and "example-private-project" in f for f in findings)


def test_findings_for_line_clean_line_has_no_findings():
    assert check_mod._findings_for_line("some/file.py", 1, "print('hello world')") == []


def test_range_scan_catches_leak_committed_then_reverted(tmp_path):
    repo = tmp_path / "fixture-repo"
    repo.mkdir()
    _init_repo(repo)

    target = repo / "notes.md"
    target.write_text("nothing interesting here\n", encoding="utf-8")
    _run(["git", "add", "notes.md"], repo)
    _run(["git", "commit", "-q", "-m", "base"], repo)
    base_sha = _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()

    # Commit 1: add a leak.
    target.write_text("nothing interesting here\nsee C:\\Users\\example-private-project\\notes\n", encoding="utf-8")
    _run(["git", "add", "notes.md"], repo)
    _run(["git", "commit", "-q", "-m", "add a note"], repo)

    # Commit 2: remove it again -- gone from the working tree and from the
    # base..head net diff of an unrelated line-count check, but NOT gone
    # from the range's own commit history.
    target.write_text("nothing interesting here\n", encoding="utf-8")
    _run(["git", "add", "notes.md"], repo)
    _run(["git", "commit", "-q", "-m", "revert the note"], repo)
    head_sha = _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()

    original_root = check_mod.REPO_ROOT
    try:
        check_mod.REPO_ROOT = repo
        # Working tree is clean: the leak was reverted before HEAD.
        assert check_mod.check() == []
        # But the range scan still finds it in the intermediate commit.
        findings = check_mod.check_range(f"{base_sha}..{head_sha}")
    finally:
        check_mod.REPO_ROOT = original_root

    assert any("private-project name leak" in f and "example-private-project" in f for f in findings)
    assert any("Windows drive letter" in f for f in findings)


def test_range_scan_clean_history_has_no_findings(tmp_path):
    repo = tmp_path / "fixture-repo-clean"
    repo.mkdir()
    _init_repo(repo)

    target = repo / "notes.md"
    target.write_text("first\n", encoding="utf-8")
    _run(["git", "add", "notes.md"], repo)
    _run(["git", "commit", "-q", "-m", "base"], repo)
    base_sha = _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()

    target.write_text("first\nsecond, nothing sensitive\n", encoding="utf-8")
    _run(["git", "add", "notes.md"], repo)
    _run(["git", "commit", "-q", "-m", "add a clean line"], repo)
    head_sha = _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()

    original_root = check_mod.REPO_ROOT
    try:
        check_mod.REPO_ROOT = repo
        findings = check_mod.check_range(f"{base_sha}..{head_sha}")
    finally:
        check_mod.REPO_ROOT = original_root

    assert findings == []


def test_range_scan_skips_exempt_fixture_paths(tmp_path):
    repo = tmp_path / "fixture-repo-exempt"
    repo.mkdir()
    _init_repo(repo)

    fixture_dir = repo / "tests" / "fixtures"
    fixture_dir.mkdir(parents=True)
    target = fixture_dir / "sample.json"
    target.write_text("{}\n", encoding="utf-8")
    _run(["git", "add", "."], repo)
    _run(["git", "commit", "-q", "-m", "base"], repo)
    base_sha = _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()

    target.write_text('{"path": "C:\\\\Users\\\\example-private-project"}\n', encoding="utf-8")
    _run(["git", "add", "."], repo)
    _run(["git", "commit", "-q", "-m", "edit fixture"], repo)
    head_sha = _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()

    original_root = check_mod.REPO_ROOT
    try:
        check_mod.REPO_ROOT = repo
        findings = check_mod.check_range(f"{base_sha}..{head_sha}")
    finally:
        check_mod.REPO_ROOT = original_root

    assert findings == []

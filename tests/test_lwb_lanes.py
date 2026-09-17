"""Tests for scripts/lwb_lanes.py: path classification, trailer parsing,
the bootstrap exception, and the review-record cross-check."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lwb_lanes  # noqa: E402


def test_classify_claude_prefixes():
    assert lwb_lanes.classify_path("plugins/claude/lwb/bin/lwb_hook.py") == "claude"
    assert lwb_lanes.classify_path("adapters/claude/hook_io.py") == "claude"


def test_classify_codex_prefixes():
    assert lwb_lanes.classify_path("plugins/codex/lwb/bin/lwb_hook.py") == "codex"
    assert lwb_lanes.classify_path("adapters/codex/hook_io.py") == "codex"


def test_classify_shared_prefixes_and_files():
    for path in ("core/lwb_core/engine.py", "scripts/lwb_lanes.py", ".github/workflows/ci.yml",
                 "docs/architecture.md", "proof/schema.json", "reviews/README.md",
                 "HANDOFF.md", "AGENTS.md", "CLAUDE.md", "README.md"):
        assert lwb_lanes.classify_path(path) == "shared", path


def test_classify_tests_subdirectory():
    assert lwb_lanes.classify_path("tests/adapters/fixtures/claude/pretooluse_read.json") == "claude"
    assert lwb_lanes.classify_path("tests/adapters/fixtures/codex/pretooluse_read.json") == "codex"


def test_classify_named_test_module_extension():
    assert lwb_lanes.classify_path("tests/adapters/test_claude_hook_io.py") == "claude"
    assert lwb_lanes.classify_path("tests/adapters/test_codex_hook_io.py") == "codex"


def test_classify_other_for_unrelated_path():
    assert lwb_lanes.classify_path("examples/policies/example-routing.json") == "other"


def test_classify_shared_test_module_is_shared_not_other():
    """A test covering a shared script must be writable by either CLI under
    two-CTO review. These used to classify as "other" — in no lane and not
    shared — so NEITHER CLI could add a test for a shared script."""
    for path in (
        "tests/test_lwb_check_env_leak.py",
        "tests/test_lwb_check_proof.py",
        "tests/test_lwb_lanes.py",
        "tests/conftest.py",
        "tests/core/test_engine_mutation.py",
    ):
        assert lwb_lanes.classify_path(path) == "shared", path


def test_lane_owned_paths_inside_tests_still_win_over_shared():
    """`tests/` being shared must not swallow the lane-owned carve-outs."""
    assert lwb_lanes.classify_path("tests/adapters/fixtures/claude/x.json") == "claude"
    assert lwb_lanes.classify_path("tests/adapters/test_codex_hook_io.py") == "codex"


def test_bootstrap_exception_skips_pr_4():
    # rev_range irrelevant since pr_number gate short-circuits before any git call
    assert lwb_lanes.check_lanes("HEAD~1..HEAD", 4) == []
    assert lwb_lanes.check_lanes("HEAD~1..HEAD", 1) == []


def test_commit_agent_parses_trailer(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "f.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "f.txt"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "msg\n\nLWB-Agent: claude"],
        cwd=repo,
        check=True,
    )
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = repo
        assert lwb_lanes.commit_agent(sha) == "claude"
        assert lwb_lanes.commit_files(sha) == ["f.txt"]
    finally:
        lwb_lanes.REPO_ROOT = original_root


def test_review_ok_requires_distinct_reviewer_and_author_identity(tmp_path):
    reviews_dir = tmp_path / "reviews" / "9"
    reviews_dir.mkdir(parents=True)
    (reviews_dir / "claude-cto.json").write_text(
        json.dumps(
            {
                "pr": 9,
                "reviewer_agent": "claude",
                "reviewer_id": "same-session",
                "commit_author_agent": "codex",
                "commit_author_id": "same-session",
                "verdict": "AGREE",
            }
        ),
        encoding="utf-8",
    )

    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        ok = lwb_lanes._review_ok(9, "claude", "deadbeef", errors)
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert ok is False
    assert any("equals" in e for e in errors)

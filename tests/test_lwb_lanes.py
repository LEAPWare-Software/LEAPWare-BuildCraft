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


def test_bootstrap_exemption_covers_only_the_named_prs():
    # rev_range irrelevant since the pr_number gate short-circuits before any git call
    for exempt in sorted(lwb_lanes.BOOTSTRAP_EXEMPT_PRS):
        assert lwb_lanes.check_lanes("HEAD~1..HEAD", exempt) == []


def test_bootstrap_exemption_is_an_explicit_set_not_a_range():
    """A `<= N` threshold let Dependabot spend #2-#4 of a window meant for
    the PRs that stood this system up. Naming them stops that."""
    assert lwb_lanes.BOOTSTRAP_EXEMPT_PRS == frozenset({1, 5})
    assert not hasattr(lwb_lanes, "BOOTSTRAP_LAST_EXEMPT_PR")
    # The numbers Dependabot took must NOT be exempt.
    for taken in (2, 3, 4):
        assert taken not in lwb_lanes.BOOTSTRAP_EXEMPT_PRS


def test_bot_author_emails_are_recognised():
    for email in (
        "dependabot[bot]@users.noreply.github.com",
        "49699333+dependabot[bot]@users.noreply.github.com",
        "dependabot@github.com",
    ):
        assert any(p.search(email) for p in lwb_lanes.BOT_AUTHOR_PATTERNS), email


def test_human_and_agent_emails_are_not_treated_as_bots():
    for email in ("leapware@outlook.com", "someone@example.com"):
        assert not any(p.search(email) for p in lwb_lanes.BOT_AUTHOR_PATTERNS), email


def test_bot_commit_skips_lane_enforcement(tmp_path):
    """A Dependabot commit touches shared paths, carries no LWB-Agent
    trailer, and must still pass a non-exempt PR."""
    repo = tmp_path / "botrepo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "dependabot[bot]"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "49699333+dependabot[bot]@users.noreply.github.com"],
        cwd=repo,
        check=True,
    )
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    workflows = repo / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("bumped\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "chore(deps): bump actions/checkout from 5 to 7"],
        cwd=repo,
        check=True,
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = repo
        # PR 42 is well outside the bootstrap set, so only the bot skip can save it.
        assert lwb_lanes.check_lanes(f"{base}..{head}", 42) == []
    finally:
        lwb_lanes.REPO_ROOT = original_root


def test_non_bot_commit_without_trailer_still_fails(tmp_path):
    """The bot skip must not become a general amnesty."""
    repo = tmp_path / "humanrepo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Someone"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "someone@example.com"], cwd=repo, check=True)
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    (repo / "seed.txt").write_text("changed\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "no trailer here"], cwd=repo, check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = repo
        errors = lwb_lanes.check_lanes(f"{base}..{head}", 42)
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert any("LWB-Agent" in e for e in errors)


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


def _write_review(tmp_path, name: str, **overrides):
    reviews_dir = tmp_path / "reviews" / "9"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "pr": 9,
        "reviewer_agent": "claude",
        "reviewer_id": "reviewer-session",
        "commit_author_agent": "claude",
        "commit_author_id": "author-session",
        "verdict": "AGREE",
    }
    record.update(overrides)
    (reviews_dir / name).write_text(json.dumps(record), encoding="utf-8")


def test_review_ok_requires_distinct_reviewer_and_author_identity(tmp_path):
    _write_review(tmp_path, "claude-cto.json", reviewer_id="same", commit_author_id="same")
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        got = lwb_lanes._review_ok(tmp_path / "reviews" / "9" / "claude-cto.json", errors)
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got is None
    assert any("equals" in e for e in errors)


def test_independent_reviews_accepts_any_filename_not_just_per_vendor(tmp_path):
    """The gate counts distinct reviewer identities, not vendor filenames.
    It used to demand BOTH claude-cto.json and codex-cto.json, which no
    single-CLI repo could ever satisfy."""
    _write_review(tmp_path, "verifier.json", reviewer_id="independent-verifier")
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        ok = lwb_lanes.independent_reviews(9, "deadbeefcafe", errors)
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert ok is True, errors
    assert errors == []


def test_independent_reviews_fails_with_no_records(tmp_path):
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        ok = lwb_lanes.independent_reviews(9, "deadbeefcafe", errors)
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert ok is False
    assert any("independent review" in e for e in errors)


def test_independent_reviews_counts_distinct_reviewers_not_files(tmp_path):
    """Two records from the SAME reviewer are one independent review."""
    _write_review(tmp_path, "a.json", reviewer_id="same-reviewer")
    _write_review(tmp_path, "b.json", reviewer_id="same-reviewer")
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        lwb_lanes.REQUIRED_INDEPENDENT_REVIEWS = 2
        errors: list[str] = []
        ok = lwb_lanes.independent_reviews(9, "deadbeefcafe", errors)
    finally:
        lwb_lanes.REQUIRED_INDEPENDENT_REVIEWS = 1
        lwb_lanes.REPO_ROOT = original_root

    assert ok is False
    assert any("1 independent review" in e for e in errors)


def test_independent_reviews_rejects_a_disagree_verdict(tmp_path):
    _write_review(tmp_path, "claude-cto.json", verdict="DISAGREE")
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        ok = lwb_lanes.independent_reviews(9, "deadbeefcafe", errors)
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert ok is False
    assert any("DISAGREE" in e for e in errors)

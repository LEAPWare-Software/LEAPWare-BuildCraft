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


def test_classify_gitignore_is_shared():
    """`.gitignore` governs the whole repo, so it belongs to no one lane.

    Found by the independent review of PR #16: that PR added `graphify-out/`
    to `.gitignore` to keep build artifacts carrying the operator's username
    out of this PUBLIC repo, and the lane gate rejected the commit as being
    outside the claude lane -- an un-landable fix for a directive-8 concern.
    """
    assert lwb_lanes.classify_path(".gitignore") == "shared"


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


HEAD_SHA = "deadbeefcafefeed0000000000000000000000"


def _write_review(tmp_path, name: str, **overrides):
    reviews_dir = tmp_path / "reviews" / "9"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "pr": 9,
        "reviewed_commit": HEAD_SHA,
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
        got = lwb_lanes._review_ok(
            tmp_path / "reviews" / "9" / "claude-cto.json", HEAD_SHA, 9, errors
        )
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
        ok = lwb_lanes.independent_reviews(9, "deadbeefcafe", HEAD_SHA, errors)
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert ok is True, errors
    assert errors == []


def test_independent_reviews_fails_with_no_records(tmp_path):
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        ok = lwb_lanes.independent_reviews(9, "deadbeefcafe", HEAD_SHA, errors)
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
        ok = lwb_lanes.independent_reviews(9, "deadbeefcafe", HEAD_SHA, errors)
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
        ok = lwb_lanes.independent_reviews(9, "deadbeefcafe", HEAD_SHA, errors)
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert ok is False
    assert any("DISAGREE" in e for e in errors)


def test_review_ok_rejects_record_with_no_reviewed_commit(tmp_path):
    """A null reviewed_commit is now caught by the schema's type check
    (reviewed_commit must be a string) before the STALE logic ever runs --
    a clearer, earlier error for a shape violation, not the staleness
    message meant for a wrong-but-well-formed value."""
    _write_review(tmp_path, "claude-cto.json", reviewed_commit=None)
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        got = lwb_lanes._review_ok(
            tmp_path / "reviews" / "9" / "claude-cto.json", HEAD_SHA, 9, errors
        )
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got is None
    assert any("reviewed_commit" in e for e in errors), errors


def test_review_ok_rejects_record_whose_reviewed_commit_does_not_match_head(tmp_path):
    _write_review(tmp_path, "claude-cto.json", reviewed_commit="0123456")
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        got = lwb_lanes._review_ok(
            tmp_path / "reviews" / "9" / "claude-cto.json", HEAD_SHA, 9, errors
        )
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got is None
    assert any("STALE" in e and "0123456" in e and HEAD_SHA in e for e in errors)


def test_review_ok_accepts_matching_reviewed_commit(tmp_path):
    _write_review(tmp_path, "claude-cto.json", reviewed_commit=HEAD_SHA)
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        got = lwb_lanes._review_ok(
            tmp_path / "reviews" / "9" / "claude-cto.json", HEAD_SHA, 9, errors
        )
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got == "reviewer-session"
    assert errors == []


def _git(repo, *args, **kwargs):
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True, **kwargs
    ).stdout.strip()


def _init_repo(repo):
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)


def _commit(repo, path: str, content: str, message: str) -> str:
    fp = repo / path
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=repo, check=True)
    return _git(repo, "rev-parse", "HEAD")


def test_reviewable_head_skips_trailing_reviews_only_commit(tmp_path):
    """A record naming a substantive commit must still pass even when a
    LATER commit touched only reviews/ — committing the record itself
    must not make the record it just wrote look stale."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _commit(repo, "seed.txt", "seed\n", "seed")
    substantive = _commit(repo, "core/thing.py", "code\n", "substantive change")
    _commit(repo, "reviews/9/verifier.json", "{}\n", "record the review")

    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = repo
        got = lwb_lanes.resolve_reviewable_head("HEAD")
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got == substantive


def test_reviewable_head_skips_trailing_proof_only_commit(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    _commit(repo, "seed.txt", "seed\n", "seed")
    substantive = _commit(repo, "core/thing.py", "code\n", "substantive change")
    _commit(repo, "proof/9.json", "{}\n", "record proof")

    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = repo
        got = lwb_lanes.resolve_reviewable_head("HEAD")
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got == substantive


def test_reviewable_head_still_rejects_stale_review_before_a_later_substantive_commit(tmp_path):
    """The fix must not defeat the original staleness protection: a record
    naming a sha older than a LATER substantive commit is still stale."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _commit(repo, "seed.txt", "seed\n", "seed")
    older_substantive = _commit(repo, "core/a.py", "a\n", "first substantive change")
    newer_substantive = _commit(repo, "core/b.py", "b\n", "second substantive change")

    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = repo
        reviewable_head = lwb_lanes.resolve_reviewable_head("HEAD")
        assert reviewable_head == newer_substantive

        _write_review(repo, "verifier.json", reviewed_commit=older_substantive)
        errors: list[str] = []
        got = lwb_lanes._review_ok(
            repo / "reviews" / "9" / "verifier.json", reviewable_head, 9, errors
        )
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got is None
    assert any("STALE" in e for e in errors)


def test_reviewable_head_falls_back_to_raw_head_when_every_commit_is_record_only(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    seed = _commit(repo, "reviews/9/first.json", "{}\n", "seed, record-only")
    head = _commit(repo, "proof/9.json", "{}\n", "also record-only")
    assert head != seed

    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = repo
        got = lwb_lanes.resolve_reviewable_head("HEAD")
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got == head


def _write_review_pr(tmp_path, pr: int, name: str, **overrides):
    """Like _write_review but for an arbitrary PR number, needed to exercise
    the REVIEWER_ID_FORMAT_CUTOFF_PR behaviour (records below the cutoff are
    exempt from the parseable-identity format; records at/above it are not)."""
    reviews_dir = tmp_path / "reviews" / str(pr)
    reviews_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "pr": pr,
        "reviewed_commit": HEAD_SHA,
        "reviewer_agent": "claude",
        "reviewer_id": "reviewer-session",
        "commit_author_agent": "claude",
        "commit_author_id": "author-session",
        "verdict": "AGREE",
    }
    record.update(overrides)
    (reviews_dir / name).write_text(json.dumps(record), encoding="utf-8")


def test_cutoff_constant_is_the_next_pr():
    assert lwb_lanes.REVIEWER_ID_FORMAT_CUTOFF_PR == 19


def test_parse_identity_parses_from_the_right_with_hyphenated_role_and_model():
    """The role and model are one blob, hyphens and all -- `[^-]+`-per-field
    hard-failed real identifiers like `lw-verifier` (this repo's own agent
    name) or `claude-sonnet-5` (a real model id). Parsing from the right
    (date, then session-token, then everything left over as
    role-and-model) is the only way to accept those without pushing authors
    toward degraded ids just to satisfy the validator."""
    parsed = lwb_lanes._parse_identity(
        "lw-verifier-claude-opus-5-abc123-2026-09-19", "reviewer_id", "rec", []
    )
    assert parsed == ("lw-verifier-claude-opus-5", "abc123", "2026-09-19")


def test_parse_identity_parses_from_the_right_second_case():
    parsed = lwb_lanes._parse_identity(
        "verifier-sonnet-5-1-tok-2026-09-19", "reviewer_id", "rec", []
    )
    assert parsed == ("verifier-sonnet-5-1", "tok", "2026-09-19")


def test_parse_identity_rejects_single_field_id():
    errors: list[str] = []
    parsed = lwb_lanes._parse_identity("justoneword", "reviewer_id", "rec", errors)
    assert parsed is None
    assert errors


def test_parse_identity_rejects_id_missing_fields():
    errors: list[str] = []
    parsed = lwb_lanes._parse_identity("just-three-fields", "reviewer_id", "rec", errors)
    assert parsed is None
    assert errors


def test_review_ok_below_cutoff_does_not_require_parseable_ids(tmp_path):
    """Records 7-18 use free-form ids that do not parse into the new
    format. The cutoff means they stay valid without being rewritten."""
    _write_review_pr(
        tmp_path, 18, "verifier.json",
        reviewer_id="lw-verifier-sonnet-acc84f592377940aa-2026-09-18",
        commit_author_id="claude-code-opus5-session-f8da3f9e-2026-09-18",
    )
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        got = lwb_lanes._review_ok(
            tmp_path / "reviews" / "18" / "verifier.json", HEAD_SHA, 18, errors
        )
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got == "lw-verifier-sonnet-acc84f592377940aa-2026-09-18"
    assert errors == []


def test_review_ok_at_cutoff_rejects_unparseable_reviewer_id(tmp_path):
    # No trailing "-YYYY-MM-DD": unparseable under the from-the-right
    # algorithm too, unlike the older "lw-verifier-sonnet-<token>-<date>"
    # style ids, which DO parse now that role-and-model may contain
    # hyphens (that shape used to hard-fail the old [^-]+-per-field regex,
    # which is exactly the false-fail this format was rewritten to fix).
    _write_review_pr(
        tmp_path, 19, "verifier.json",
        reviewer_id="lw-verifier-sonnet-no-trailing-date-here",
        commit_author_id="author-role-model-token-2026-09-20",
        reviewer_was_dispatched_by_author=False,
    )
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        got = lwb_lanes._review_ok(
            tmp_path / "reviews" / "19" / "verifier.json", HEAD_SHA, 19, errors
        )
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got is None
    assert any("does not" in e or "format" in e for e in errors), errors


def test_review_ok_at_cutoff_rejects_shared_session_token(tmp_path):
    """The accidental self-review this PR exists to catch: two ids that
    parse fine individually but share the same session-token field -- a
    subagent reviewing its own dispatching session."""
    _write_review_pr(
        tmp_path, 19, "verifier.json",
        reviewer_id="verifier-sonnet-f8da3f9e-2026-09-20",
        commit_author_id="implementer-opus-f8da3f9e-2026-09-19",
        reviewer_was_dispatched_by_author=False,
    )
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        got = lwb_lanes._review_ok(
            tmp_path / "reviews" / "19" / "verifier.json", HEAD_SHA, 19, errors
        )
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got is None
    assert any("segment" in e for e in errors), errors


def test_review_ok_at_cutoff_requires_dispatched_boolean_field(tmp_path):
    _write_review_pr(
        tmp_path, 19, "verifier.json",
        reviewer_id="verifier-sonnet-tokenA-2026-09-20",
        commit_author_id="implementer-opus-tokenB-2026-09-19",
        # no reviewer_was_dispatched_by_author
    )
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        got = lwb_lanes._review_ok(
            tmp_path / "reviews" / "19" / "verifier.json", HEAD_SHA, 19, errors
        )
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got is None
    assert any("reviewer_was_dispatched_by_author" in e for e in errors), errors


def test_review_ok_at_cutoff_accepts_and_notices_when_dispatched_true(tmp_path):
    """A True value must not silently pass as though it proved
    independence -- the gate still accepts the record (it cannot verify
    the claim either way) but must emit a notice saying so."""
    _write_review_pr(
        tmp_path, 19, "verifier.json",
        reviewer_id="verifier-sonnet-tokenA-2026-09-20",
        commit_author_id="implementer-opus-tokenB-2026-09-19",
        reviewer_was_dispatched_by_author=True,
    )
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        notices: list[str] = []
        got = lwb_lanes._review_ok(
            tmp_path / "reviews" / "19" / "verifier.json", HEAD_SHA, 19, errors, notices
        )
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got == "verifier-sonnet-tokenA-2026-09-20"
    assert errors == []
    assert any("audit trail" in n or "not independent" in n for n in notices), notices


def test_review_ok_at_cutoff_accepts_cleanly_when_dispatched_false(tmp_path):
    _write_review_pr(
        tmp_path, 19, "verifier.json",
        reviewer_id="verifier-sonnet-tokenA-2026-09-20",
        commit_author_id="implementer-opus-tokenB-2026-09-19",
        reviewer_was_dispatched_by_author=False,
    )
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        notices: list[str] = []
        got = lwb_lanes._review_ok(
            tmp_path / "reviews" / "19" / "verifier.json", HEAD_SHA, 19, errors, notices
        )
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got == "verifier-sonnet-tokenA-2026-09-20"
    assert errors == []
    assert notices == []


# ---------------------------------------------------------------------------
# The bypass: `pr` used to be trusted from inside the record itself, not
# from the authoritative pr_number the caller (independent_reviews, keyed
# off the directory it globbed) actually has. A record filed under
# reviews/19/ claiming "pr": 18 skipped every pr>=19 check entirely.
# ---------------------------------------------------------------------------


def test_review_ok_rejects_record_whose_pr_field_disagrees_with_its_directory(tmp_path):
    """The adversarial-review bypass: a record sitting in reviews/19/ but
    self-declaring "pr": 18 must not be judged as a pr-18 (pre-cutoff,
    free-form-ok) record just because it says so. The directory it was
    found under, passed in by the caller as the authoritative pr_number,
    is what must gate the cutoff -- not the field inside the file."""
    _write_review_pr(
        tmp_path, 19, "sneaky.json",
        reviewer_id="reviewer-session",
        commit_author_id="author-session",
        # no reviewer_was_dispatched_by_author -- would fail the pr>=19
        # path outright if that path were reached, proving the bypass
        # actually skips it rather than merely also passing it
    )
    path = tmp_path / "reviews" / "19" / "sneaky.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["pr"] = 18  # self-declared, disagrees with the reviews/19/ directory
    path.write_text(json.dumps(data), encoding="utf-8")

    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        got = lwb_lanes._review_ok(
            tmp_path / "reviews" / "19" / "sneaky.json", HEAD_SHA, 19, errors
        )
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got is None
    assert any("18" in e and "19" in e for e in errors), errors


def test_review_ok_rejects_pr_field_as_string(tmp_path):
    """"pr": "19" (a string, not an int) must not silently satisfy the
    reconciliation check via Python's == treating them as different values
    that just happen to render the same -- nor should it slip past the
    cutoff logic by masquerading as the right value."""
    _write_review_pr(tmp_path, 19, "verifier.json")
    path = tmp_path / "reviews" / "19" / "verifier.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["pr"] = "19"
    path.write_text(json.dumps(data), encoding="utf-8")
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        got = lwb_lanes._review_ok(
            tmp_path / "reviews" / "19" / "verifier.json", HEAD_SHA, 19, errors
        )
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got is None
    assert errors


def test_review_ok_rejects_pr_field_as_float(tmp_path):
    _write_review_pr(tmp_path, 19, "verifier.json")
    path = tmp_path / "reviews" / "19" / "verifier.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["pr"] = 19.0
    path.write_text(json.dumps(data), encoding="utf-8")
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        got = lwb_lanes._review_ok(
            tmp_path / "reviews" / "19" / "verifier.json", HEAD_SHA, 19, errors
        )
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got is None
    assert errors


def test_review_ok_rejects_missing_pr_field(tmp_path):
    _write_review_pr(tmp_path, 19, "verifier.json")
    path = tmp_path / "reviews" / "19" / "verifier.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["pr"]
    path.write_text(json.dumps(data), encoding="utf-8")

    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        got = lwb_lanes._review_ok(path, HEAD_SHA, 19, errors)
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got is None
    assert any("pr" in e for e in errors), errors


def test_review_ok_rejects_null_pr_field(tmp_path):
    _write_review_pr(tmp_path, 19, "verifier.json")
    path = tmp_path / "reviews" / "19" / "verifier.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["pr"] = None
    path.write_text(json.dumps(data), encoding="utf-8")
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        got = lwb_lanes._review_ok(
            tmp_path / "reviews" / "19" / "verifier.json", HEAD_SHA, 19, errors
        )
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got is None
    assert errors


def test_review_ok_accepts_when_pr_field_matches_directory(tmp_path):
    """The reconciliation check must not reject the ordinary, honest case."""
    _write_review_pr(
        tmp_path, 19, "verifier.json",
        reviewer_id="verifier-sonnet-tokenA-2026-09-20",
        commit_author_id="implementer-opus-tokenB-2026-09-19",
        reviewer_was_dispatched_by_author=False,
    )
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        got = lwb_lanes._review_ok(
            tmp_path / "reviews" / "19" / "verifier.json", HEAD_SHA, 19, errors
        )
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got == "verifier-sonnet-tokenA-2026-09-20"
    assert errors == []


# ---------------------------------------------------------------------------
# Schema type checking (item 2): required/enum/pattern already ran; "type"
# was decorative. isinstance(True, int) is a trap for "integer".
# ---------------------------------------------------------------------------


def test_validate_against_schema_rejects_bool_for_integer_field():
    errors: list[str] = []
    lwb_lanes._validate_against_schema({"pr": True}, "rec", errors)
    assert any("pr" in e and "type" in e.lower() for e in errors), errors


def test_validate_against_schema_accepts_real_integer_for_integer_field():
    errors: list[str] = []
    full_record = {
        "pr": 19,
        "reviewed_commit": HEAD_SHA,
        "reviewer_agent": "claude",
        "reviewer_id": "reviewer-session",
        "commit_author_agent": "claude",
        "commit_author_id": "author-session",
        "verdict": "AGREE",
    }
    lwb_lanes._validate_against_schema(full_record, "rec", errors)
    assert errors == []


def test_validate_against_schema_rejects_wrong_type_for_string_field():
    errors: list[str] = []
    lwb_lanes._validate_against_schema({"reviewer_id": 12345}, "rec", errors)
    assert any("reviewer_id" in e for e in errors), errors


def test_validate_against_schema_rejects_wrong_type_for_boolean_field():
    errors: list[str] = []
    lwb_lanes._validate_against_schema(
        {"reviewer_was_dispatched_by_author": "true"}, "rec", errors
    )
    assert any("reviewer_was_dispatched_by_author" in e for e in errors), errors


def test_type_matches_covers_integer_string_boolean_array_object():
    tm = lwb_lanes._type_matches
    assert tm(1, "integer") is True
    assert tm(True, "integer") is False  # the bool-is-an-int trap
    assert tm(False, "integer") is False
    assert tm("x", "string") is True
    assert tm(1, "string") is False
    assert tm(True, "boolean") is True
    assert tm("true", "boolean") is False
    assert tm([], "array") is True
    assert tm({}, "array") is False
    assert tm({}, "object") is True
    assert tm([], "object") is False


# ---------------------------------------------------------------------------
# A non-string reviewed_commit used to crash with an uncaught TypeError at
# `len(reviewed_commit) < 7` -- `1234567890` passed the schema pattern
# check (guarded by isinstance(value, str)) and then hit the un-guarded
# STALE check.
# ---------------------------------------------------------------------------


def test_review_ok_non_string_reviewed_commit_is_a_clean_error_not_a_crash(tmp_path):
    _write_review_pr(tmp_path, 9, "verifier.json", reviewed_commit=1234567890)
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        got = lwb_lanes._review_ok(
            tmp_path / "reviews" / "9" / "verifier.json", HEAD_SHA, 9, errors
        )
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got is None
    assert any("reviewed_commit" in e for e in errors), errors


# ---------------------------------------------------------------------------
# Item 4: session-token-sharing rejection must still work against the
# from-the-right parse, using ids with real hyphenated role/model blobs.
# ---------------------------------------------------------------------------


def test_review_ok_at_cutoff_rejects_shared_session_token_with_hyphenated_ids(tmp_path):
    """Shared token is 8 characters -- at MIN_SHARED_SEGMENT_LENGTH -- so
    this stays a genuine collision under the segment-set rule."""
    _write_review_pr(
        tmp_path, 19, "verifier.json",
        reviewer_id="lw-verifier-claude-opus-5-tok12345-2026-09-20",
        commit_author_id="lw-implementer-claude-sonnet-5-tok12345-2026-09-19",
        reviewer_was_dispatched_by_author=False,
    )
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        got = lwb_lanes._review_ok(
            tmp_path / "reviews" / "19" / "verifier.json", HEAD_SHA, 19, errors
        )
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got is None
    assert any("segment" in e for e in errors), errors


# ---------------------------------------------------------------------------
# Re-review finding: the positional check above ("the segment immediately
# before the date") is itself both an evasion and a false-positive
# generator. Replaced with a segment-SET comparison (excluding the
# stripped trailing date) that flags any shared segment of at least
# MIN_SHARED_SEGMENT_LENGTH characters, wherever it sits in either id.
# ---------------------------------------------------------------------------


def test_shared_long_segment_none_for_unrelated_ids():
    assert lwb_lanes._shared_long_segment(
        "verifier-sonnet-ac5ffd6d6cde8a968-2026-09-17",
        "claude-code-opus5-session-f8da3f9e-2026-09-17",
    ) is None


def test_shared_long_segment_finds_token_not_adjacent_to_date():
    """The actual PR 15-17 shape: the shared session token sits BEFORE an
    extra trailing segment, not immediately before the date. This is
    exactly what the old position-only check missed and is why it was
    replaced."""
    shared = lwb_lanes._shared_long_segment(
        "lw-verifier-sonnet5-f8da3f9e-scope13to15-2026-09-18",
        "claude-code-opus5-session-f8da3f9e-2026-09-18",
    )
    assert shared == "f8da3f9e"


def test_shared_long_segment_catches_the_padded_suffix_evasion(tmp_path):
    """A one-segment suffix appended after the real token must not defeat
    the check: comparing SETS of segments, not the one adjacent to the
    date, still finds the real token shared between the two ids."""
    shared = lwb_lanes._shared_long_segment(
        "verifier-sonnet-realtoken123-2026-09-19",
        "author-claude-realtoken123-extra-2026-09-19",
    )
    assert shared == "realtoken123"


def test_shared_long_segment_ignores_short_coincidental_overlap():
    """Two unrelated ids that happen to both end in the same SHORT chunk
    before the date must not be treated as a collision -- that blocks a
    legitimate review, the failure mode that gets a gate disabled."""
    assert lwb_lanes._shared_long_segment(
        "verifier-sonnet-aaaa-bbbb-9999-2026-09-19",
        "author-claude-cccc-dddd-9999-2026-09-19",
    ) is None


def test_review_ok_at_cutoff_rejects_the_padded_suffix_evasion(tmp_path):
    _write_review_pr(
        tmp_path, 19, "verifier.json",
        reviewer_id="verifier-sonnet-realtoken123-2026-09-19",
        commit_author_id="author-claude-realtoken123-extra-2026-09-19",
        reviewer_was_dispatched_by_author=False,
        reviewed_commit=HEAD_SHA,
    )
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        got = lwb_lanes._review_ok(
            tmp_path / "reviews" / "19" / "verifier.json", HEAD_SHA, 19, errors
        )
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got is None
    assert any("realtoken123" in e for e in errors), errors


def test_review_ok_at_cutoff_accepts_short_coincidental_overlap(tmp_path):
    _write_review_pr(
        tmp_path, 19, "verifier.json",
        reviewer_id="verifier-sonnet-aaaa-bbbb-9999-2026-09-19",
        commit_author_id="author-claude-cccc-dddd-9999-2026-09-19",
        reviewer_was_dispatched_by_author=False,
        reviewed_commit=HEAD_SHA,
    )
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        got = lwb_lanes._review_ok(
            tmp_path / "reviews" / "19" / "verifier.json", HEAD_SHA, 19, errors
        )
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got == "verifier-sonnet-aaaa-bbbb-9999-2026-09-19"
    assert errors == []


def test_review_ok_validates_against_schema_required_fields(tmp_path):
    """reviews/schema.json is now actually wired in: a record missing a
    schema-required field (e.g. reviewer_agent) fails even below the
    cutoff, since this is a presence check, not a format check."""
    _write_review_pr(tmp_path, 9, "verifier.json")
    # Remove a schema-required field after the fact.
    path = tmp_path / "reviews" / "9" / "verifier.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["reviewer_agent"]
    path.write_text(json.dumps(data), encoding="utf-8")

    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        got = lwb_lanes._review_ok(path, HEAD_SHA, 9, errors)
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got is None
    assert any("reviewer_agent" in e for e in errors), errors


def test_review_ok_validates_schema_enum_for_reviewer_agent(tmp_path):
    _write_review_pr(tmp_path, 9, "verifier.json", reviewer_agent="not-a-real-agent")
    path = tmp_path / "reviews" / "9" / "verifier.json"

    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        got = lwb_lanes._review_ok(path, HEAD_SHA, 9, errors)
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got is None
    assert any("reviewer_agent" in e for e in errors), errors


def test_review_ok_accepts_a_short_prefix_match(tmp_path):
    """A 7-char sha prefix, the shortest allowed by the schema, still matches."""
    _write_review(tmp_path, "claude-cto.json", reviewed_commit=HEAD_SHA[:7])
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        got = lwb_lanes._review_ok(
            tmp_path / "reviews" / "9" / "claude-cto.json", HEAD_SHA, 9, errors
        )
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got == "reviewer-session"
    assert errors == []


def test_generated_vendor_output_is_shared_not_lane_owned():
    """The deadlock this exception exists to break.

    `plugins/<agent>/lwb/vendor/` is machine-written by scripts/lwb_build.py
    from core/ and adapters/, and `lwb_build.py --check` fails CI whenever it
    drifts. While it classified as the agent's own lane, ANY change to core/
    was unlandable by a claude session: the change had to be re-vendored into
    BOTH plugins to keep CI green, and writing plugins/codex/ is outside the
    claude lane.

    That was not hypothetical. core/lwb_core/rules/ held exactly one rule --
    a self-declared no-op -- and the only commit ever to touch
    plugins/codex/lwb/vendor/ was the bootstrap commit. The lane rule was
    holding the shared core closed against the only CLI in operation.
    """
    assert lwb_lanes.classify_path(
        "plugins/codex/lwb/vendor/lwb_core/rules/lwb_proof_required.py"
    ) == "shared"
    assert lwb_lanes.classify_path(
        "plugins/claude/lwb/vendor/lwb_core/rules/lwb_proof_required.py"
    ) == "shared"
    assert lwb_lanes.classify_path("plugins/codex/lwb/vendor/policy/default.json") == "shared"
    assert lwb_lanes.classify_path("plugins/claude/lwb/vendor/adapters/claude/hook_io.py") == "shared"


def test_the_vendor_exception_does_not_leak_into_authored_lane_paths():
    """The exception must be exactly `vendor/`, and nothing else.

    A loophole here would be worse than the deadlock it fixes: it would let
    either agent write the other's real, hand-authored plugin code while the
    lane gate reported success. Every authored path under a lane must still
    classify as that lane.
    """
    for path in (
        "plugins/codex/lwb/hooks/hooks.json",
        "plugins/codex/lwb/bin/lwb_hook.py",
        "plugins/codex/lwb/.codex-plugin/plugin.json",
        "plugins/codex/lwb/skills/lwb-handoff/SKILL.md",
    ):
        assert lwb_lanes.classify_path(path) == "codex", path

    for path in (
        "plugins/claude/lwb/hooks/hooks.json",
        "plugins/claude/lwb/bin/lwb_hook.py",
        "plugins/claude/lwb/.claude-plugin/plugin.json",
    ):
        assert lwb_lanes.classify_path(path) == "claude", path

    # A path merely CONTAINING the word vendor elsewhere is not exempt.
    assert lwb_lanes.classify_path("plugins/codex/lwb/bin/vendor_helper.py") == "codex"
    assert lwb_lanes.classify_path("plugins/codex/vendor/x.py") == "codex"



# ---------------------------------------------------------------------------
# independent_reviews must not let a record that does not COUNT (because
# _review_ok rejected it -- stale, wrong verdict, bad identity, whatever)
# also VETO an otherwise-sufficient set of valid records. _review_ok's own
# contract, and its own direct tests above, are unchanged: a record either
# counts toward REQUIRED_INDEPENDENT_REVIEWS or it does not, and that
# decision is unaffected. What changes is that a record which does NOT
# count must not be able to fail the whole gate when enough OTHER, valid
# records already exist in the same reviews/<pr>/ directory.
# ---------------------------------------------------------------------------


def test_independent_reviews_passes_with_one_stale_and_one_fresh_valid_record(tmp_path):
    """The exact bug this fixes: a leftover stale record from an earlier
    review round must not veto the gate once a fresh, valid AGREE record
    already satisfies REQUIRED_INDEPENDENT_REVIEWS on its own."""
    _write_review(
        tmp_path, "stale-reviewer.json",
        reviewer_id="old-reviewer", reviewed_commit="0123456",
    )
    _write_review(
        tmp_path, "fresh-reviewer.json",
        reviewer_id="fresh-reviewer", reviewed_commit=HEAD_SHA,
    )
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        notices: list[str] = []
        ok = lwb_lanes.independent_reviews(9, "deadbeefcafe", HEAD_SHA, errors, notices)
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert ok is True, errors
    assert errors == []
    # The stale record's reason is not silently dropped -- it is surfaced
    # as a notice, since it did not count but enough other records did.
    assert any("STALE" in n for n in notices), notices


def test_independent_reviews_still_fails_on_a_lone_stale_record(tmp_path):
    """No valid record exists at all -- a single stale record must still
    fail the gate, and its STALE reason must still be visible in `errors`
    (not silently swallowed now that it no longer vetoes a sufficient set,
    since here the set is NOT sufficient)."""
    _write_review(
        tmp_path, "stale-reviewer.json",
        reviewer_id="old-reviewer", reviewed_commit="0123456",
    )
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        ok = lwb_lanes.independent_reviews(9, "deadbeefcafe", HEAD_SHA, errors)
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert ok is False
    assert any("STALE" in e for e in errors), errors
    assert any("0 independent review" in e for e in errors), errors


def test_independent_reviews_ordinary_single_valid_record_still_passes(tmp_path):
    """REQUIRED_INDEPENDENT_REVIEWS = 1, one fresh valid record, no stale
    records at all -- the ordinary case this fix must leave unaffected."""
    _write_review(tmp_path, "claude-cto.json", reviewer_id="the-reviewer")
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        notices: list[str] = []
        ok = lwb_lanes.independent_reviews(9, "deadbeefcafe", HEAD_SHA, errors, notices)
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert ok is True, errors
    assert errors == []
    assert notices == []



# ---------------------------------------------------------------------------
# commit_files / _is_record_only_commit and MERGE commits.
#
# Plain `git diff-tree` (no -m/-c/--cc) prints NOTHING for a multi-parent
# (merge) commit -- confirmed live against this repo's own history, not
# just in these fixtures. `commit_files` used to run exactly that call
# unconditionally, so every merge commit looked like it changed zero
# files, and `_is_record_only_commit`'s own vacuous-`all()` guard then
# (correctly, given that wrong input) treated a review-record-only merge
# as a real content change -- stopping resolve_reviewable_head's walk at
# the merge and staling the very records it had just brought in. These
# tests exercise the fix: a merge's file list must come from its diff
# against its FIRST PARENT specifically.
# ---------------------------------------------------------------------------


def _branch_name(repo) -> str:
    return _git(repo, "rev-parse", "--abbrev-ref", "HEAD")


def _merge_no_ff(repo, onto_branch: str, other_ref: str, message: str) -> str:
    subprocess.run(["git", "checkout", "-q", onto_branch], cwd=repo, check=True)
    subprocess.run(
        ["git", "merge", "--no-ff", "-q", "-m", message, other_ref],
        cwd=repo,
        check=True,
    )
    return _git(repo, "rev-parse", "HEAD")


def test_commit_files_uses_first_parent_diff_for_a_merge_commit(tmp_path):
    """The live defect, reproduced in a throwaway repo: a merge whose
    first-parent diff touches only reviews/ must report exactly those
    files, not the empty list plain diff-tree gives a merge."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _commit(repo, "seed.txt", "seed\n", "seed")
    main_branch = _branch_name(repo)
    substantive = _commit(repo, "core/thing.py", "code\n", "substantive change")

    subprocess.run(["git", "checkout", "-q", "-b", "side"], cwd=repo, check=True)
    _commit(repo, "reviews/9/verifier.json", "{}\n", "record the review")

    merge_sha = _merge_no_ff(repo, main_branch, "side", "merge review record")

    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = repo
        files = lwb_lanes.commit_files(merge_sha)
        parents = lwb_lanes._commit_parents(merge_sha)
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert files == ["reviews/9/verifier.json"]
    assert len(parents) == 2
    assert parents[0] == substantive


def test_reviewable_head_skips_a_merge_that_only_brought_in_review_records(tmp_path):
    """The consequence that actually matters: resolve_reviewable_head must
    walk PAST a merge commit whose only content, relative to its first
    parent, is under reviews/ or proof/ -- exactly like it already skips
    an ordinary record-only commit."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _commit(repo, "seed.txt", "seed\n", "seed")
    main_branch = _branch_name(repo)
    substantive = _commit(repo, "core/thing.py", "code\n", "substantive change")

    subprocess.run(["git", "checkout", "-q", "-b", "side"], cwd=repo, check=True)
    _commit(repo, "reviews/9/verifier.json", "{}\n", "record the review")

    _merge_no_ff(repo, main_branch, "side", "merge review record")

    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = repo
        got = lwb_lanes.resolve_reviewable_head("HEAD")
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert got == substantive


def test_reviewable_head_does_not_skip_a_merge_carrying_real_content_too(tmp_path):
    """The case that must NOT regress: a merge must never be able to
    smuggle real content past the review requirement just by also
    carrying a reviews/ file alongside it. A merge whose first-parent
    diff touches BOTH a review record AND a real file is not record-only,
    and resolve_reviewable_head must return the merge itself, not walk
    past it."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _commit(repo, "seed.txt", "seed\n", "seed")
    main_branch = _branch_name(repo)
    _commit(repo, "core/thing.py", "code\n", "substantive change")

    subprocess.run(["git", "checkout", "-q", "-b", "side"], cwd=repo, check=True)
    _commit(repo, "reviews/9/verifier.json", "{}\n", "record the review")
    _commit(repo, "core/other.py", "more code\n", "real content on the side branch too")

    merge_sha = _merge_no_ff(repo, main_branch, "side", "merge side branch")

    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = repo
        files = lwb_lanes.commit_files(merge_sha)
        got = lwb_lanes.resolve_reviewable_head("HEAD")
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert set(files) == {"reviews/9/verifier.json", "core/other.py"}
    assert got == merge_sha


def test_is_record_only_commit_true_for_a_merge_with_empty_first_parent_diff(tmp_path):
    """A merge whose first-parent diff is EMPTY (its tree is byte-identical
    to its first parent's -- e.g. an `-s ours` no-op merge) is not the
    same ambiguous case an ordinary empty commit is. `commit_files`
    diffing a merge against its first parent specifically makes an empty
    result here a PROVEN claim that nothing changed, so this is treated as
    record-only (skippable) -- the opposite of the ordinary-commit guard,
    and deliberately so: refusing to skip it would reproduce the exact
    staling bug this mechanism exists to prevent, by stopping the walk at
    a merge that changed nothing."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _commit(repo, "seed.txt", "seed\n", "seed")
    main_branch = _branch_name(repo)
    substantive = _commit(repo, "core/thing.py", "code\n", "substantive change")

    subprocess.run(["git", "checkout", "-q", "-b", "side"], cwd=repo, check=True)
    _commit(repo, "unrelated.txt", "on the side branch only\n", "side content")

    subprocess.run(["git", "checkout", "-q", main_branch], cwd=repo, check=True)
    subprocess.run(
        ["git", "merge", "--no-ff", "-q", "-s", "ours", "-m", "ours merge, keep main's tree", "side"],
        cwd=repo,
        check=True,
    )
    merge_sha = _git(repo, "rev-parse", "HEAD")

    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = repo
        files = lwb_lanes.commit_files(merge_sha)
        record_only = lwb_lanes._is_record_only_commit(merge_sha)
        got = lwb_lanes.resolve_reviewable_head("HEAD")
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert files == []
    assert record_only is True
    assert got == substantive


def test_is_record_only_commit_still_false_for_an_ordinary_empty_commit(tmp_path):
    """Unchanged from before: a genuinely empty ORDINARY (non-merge) commit
    stays NOT record-only -- the ambiguity this guard exists for is a
    property of a single-parent commit having nothing to say about itself,
    not something the merge fix should touch."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _commit(repo, "seed.txt", "seed\n", "seed")
    subprocess.run(
        ["git", "commit", "--allow-empty", "-q", "-m", "deliberately empty"],
        cwd=repo,
        check=True,
    )
    empty_sha = _git(repo, "rev-parse", "HEAD")

    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = repo
        assert lwb_lanes.commit_files(empty_sha) == []
        assert len(lwb_lanes._commit_parents(empty_sha)) == 1
        record_only = lwb_lanes._is_record_only_commit(empty_sha)
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert record_only is False


def test_commit_parents_root_commit_has_none_and_ordinary_commit_has_one(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    root = _commit(repo, "seed.txt", "seed\n", "seed")
    child = _commit(repo, "core/thing.py", "code\n", "child")

    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = repo
        assert lwb_lanes._commit_parents(root) == []
        assert lwb_lanes._commit_parents(child) == [root]
    finally:
        lwb_lanes.REPO_ROOT = original_root



# ---------------------------------------------------------------------------
# Finding A (second round of independent review): the stale-veto fix must
# not over-widen into silencing a genuine DISAGREE, a self-review
# collision, or any other non-STALE rejection just because a different,
# valid AGREE record also exists. Only STALE is routine churn.
# ---------------------------------------------------------------------------


def test_independent_reviews_disagree_still_fails_even_with_a_sufficient_fresh_agree(tmp_path):
    """The case that must NOT regress: a DISAGREE record sitting right next
    to a fresh, valid AGREE from a DIFFERENT reviewer must not be silently
    outvoted. REQUIRED_INDEPENDENT_REVIEWS=1 is already satisfied by the
    AGREE alone, but the gate must still fail on the live objection."""
    _write_review(tmp_path, "disagree-reviewer.json", reviewer_id="disagreeing-reviewer", verdict="DISAGREE")
    _write_review(tmp_path, "agree-reviewer.json", reviewer_id="agreeing-reviewer")
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        ok = lwb_lanes.independent_reviews(9, "deadbeefcafe", HEAD_SHA, errors)
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert ok is False
    assert any("DISAGREE" in e for e in errors), errors


def test_independent_reviews_self_review_collision_still_fails_with_a_sufficient_fresh_agree(tmp_path):
    """Same principle, a different non-STALE rejection reason: a
    reviewer_id == commit_author_id record must keep failing the gate
    even when a different, valid AGREE record also exists."""
    _write_review(tmp_path, "self-review.json", reviewer_id="same-id", commit_author_id="same-id")
    _write_review(tmp_path, "agree-reviewer.json", reviewer_id="agreeing-reviewer")
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        ok = lwb_lanes.independent_reviews(9, "deadbeefcafe", HEAD_SHA, errors)
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert ok is False
    assert any("equals" in e for e in errors), errors


def test_independent_reviews_stale_is_downgraded_but_disagree_is_not_in_the_same_directory(tmp_path):
    """A directory holding all three at once: a STALE record (routine
    churn, downgradable), a DISAGREE record (a live objection, never
    downgradable), and a fresh valid AGREE (sufficient on its own for
    REQUIRED_INDEPENDENT_REVIEWS=1). The gate must still fail overall
    (because of the DISAGREE), with the STALE reason demoted to a notice
    and the DISAGREE reason kept in errors."""
    _write_review(
        tmp_path, "stale-reviewer.json",
        reviewer_id="stale-reviewer", reviewed_commit="0123456",
    )
    _write_review(tmp_path, "disagree-reviewer.json", reviewer_id="disagreeing-reviewer", verdict="DISAGREE")
    _write_review(tmp_path, "agree-reviewer.json", reviewer_id="agreeing-reviewer")
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        notices: list[str] = []
        ok = lwb_lanes.independent_reviews(9, "deadbeefcafe", HEAD_SHA, errors, notices)
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert ok is False
    assert any("DISAGREE" in e for e in errors), errors
    assert not any("STALE" in e for e in errors), errors
    assert any("STALE" in n for n in notices), notices


# ---------------------------------------------------------------------------
# PR #56 finding F1 (reviews/56/cloud-reviewer-b.json): the STALE-vs-other
# classification used to be `_is_stale_only_rejection`, a bare substring
# search ("STALE" in record_errors[0]) over `_review_ok`'s formatted error
# TEXT. Every one of those messages is built as f"{rel}: ...", and `rel` is
# the review record's OWN FILENAME -- reviews/README.md says explicitly that
# any filename is accepted, so the record's author fully controls it. A
# record with a genuine DISAGREE verdict, or a genuine self-review identity
# collision, filed at a path that merely CONTAINS the substring "STALE" (with
# nothing to do with actual staleness) produced an error message containing
# "STALE" purely because of the filename, and the old check misclassified it
# as routine staleness -- silently demoting a live DISAGREE (or a detected
# self-review) to a mere notice instead of failing the gate. This is exactly
# the "a DISAGREE is silently outvoted" bug an earlier review round already
# found and this code was supposed to have fixed.
#
# The fix replaces the substring search with a structured `rejection_kind`
# tag that `_review_ok` sets itself, at the exact branch that rejects a
# record, never inferred afterward from message text. These tests go through
# `independent_reviews` (the real entry point that decides pass/fail), not
# `_review_ok` in isolation, because the exploit is specifically about what
# `independent_reviews` does with the classification.
# ---------------------------------------------------------------------------


def test_independent_reviews_disagree_at_a_stale_named_path_still_fails(tmp_path):
    """The exact reproduction from finding F1: a genuine DISAGREE record
    filed at a path/filename containing the literal substring "STALE",
    alongside a separate fresh, valid AGREE record from a different
    reviewer. REQUIRED_INDEPENDENT_REVIEWS=1 is already satisfied by the
    AGREE alone, but the DISAGREE must not be silently demoted just
    because its filename happens to contain "STALE" -- the gate must
    still fail."""
    _write_review(
        tmp_path, "whatever-STALE-whatever.json",
        reviewer_id="disagreeing-reviewer", verdict="DISAGREE",
    )
    _write_review(tmp_path, "agree-reviewer.json", reviewer_id="agreeing-reviewer")
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        notices: list[str] = []
        ok = lwb_lanes.independent_reviews(9, "deadbeefcafe", HEAD_SHA, errors, notices)
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert ok is False, errors
    assert any("DISAGREE" in e for e in errors), errors
    # It must not have been swallowed into a notice either -- a live
    # objection is never "not counted toward ... but enough already
    # exist", however its filename happens to read.
    assert not any("DISAGREE" in n for n in notices), notices


def test_independent_reviews_self_review_collision_at_a_stale_named_path_still_fails(tmp_path):
    """Same exploit, the other non-stale rejection reason: a
    reviewer_id == commit_author_id self-review collision filed at a
    "STALE"-containing path must keep failing the gate even alongside a
    sufficient fresh AGREE record."""
    _write_review(
        tmp_path, "collide-STALE-collide.json",
        reviewer_id="same-id", commit_author_id="same-id",
    )
    _write_review(tmp_path, "agree-reviewer.json", reviewer_id="agreeing-reviewer")
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        notices: list[str] = []
        ok = lwb_lanes.independent_reviews(9, "deadbeefcafe", HEAD_SHA, errors, notices)
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert ok is False, errors
    assert any("equals" in e for e in errors), errors
    assert not any("equals" in n for n in notices), notices


def test_independent_reviews_genuinely_stale_at_a_stale_named_path_is_still_downgraded(tmp_path):
    """Confirms the fix does not over-narrow: a record that IS genuinely
    stale (reviewed_commit does not match the reviewable head), filed at a
    path that also happens to contain "STALE", must still be correctly
    downgraded to a notice once a sufficient fresh AGREE exists elsewhere
    -- the filename must not matter either way, for staleness any more
    than for a non-stale rejection."""
    _write_review(
        tmp_path, "old-STALE-reviewer.json",
        reviewer_id="old-reviewer", reviewed_commit="0123456",
    )
    _write_review(
        tmp_path, "fresh-reviewer.json",
        reviewer_id="fresh-reviewer", reviewed_commit=HEAD_SHA,
    )
    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = tmp_path
        errors: list[str] = []
        notices: list[str] = []
        ok = lwb_lanes.independent_reviews(9, "deadbeefcafe", HEAD_SHA, errors, notices)
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert ok is True, errors
    assert errors == []
    assert any("STALE" in n for n in notices), notices


# ---------------------------------------------------------------------------
# Finding B (second round of independent review): commit_files reporting a
# merge's real first-parent diff must not feed the LANE-OWNERSHIP check --
# only the shared-path / review-freshness determination. A merge did not
# personally author the files it brings in from its second parent; each of
# those commits was already lane-checked individually when it landed.
# ---------------------------------------------------------------------------


def test_check_lanes_merge_with_out_of_lane_file_does_not_fail_lane_ownership(tmp_path):
    """A merge that catches a claude branch up with a codex-lane file
    already on main must NOT be flagged as the claude merger personally
    touching a file outside their lane."""
    repo = tmp_path / "repo"
    _init_repo(repo)

    def _commit_with_trailer(path: str, content: str, message: str, agent: str) -> str:
        fp = repo / path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", f"{message}\n\nLWB-Agent: {agent}"],
            cwd=repo,
            check=True,
        )
        return _git(repo, "rev-parse", "HEAD")

    _commit_with_trailer("seed.txt", "seed\n", "seed", "human")
    base = _git(repo, "rev-parse", "HEAD")
    main_branch = _branch_name(repo)

    # A codex-lane commit lands on main -- already lane-checked as codex's
    # own commit when IT landed.
    _commit_with_trailer(
        "plugins/codex/lwb/bin/lwb_hook.py", "code\n", "codex work", "codex"
    )

    subprocess.run(["git", "checkout", "-q", "-b", "side", base], cwd=repo, check=True)
    _commit_with_trailer(
        "plugins/claude/lwb/bin/lwb_hook.py", "code\n", "claude work", "claude"
    )

    subprocess.run(["git", "checkout", "-q", "side"], cwd=repo, check=True)
    subprocess.run(
        [
            "git", "merge", "--no-ff", "-q",
            "-m", f"merge main into side\n\nLWB-Agent: claude",
            main_branch,
        ],
        cwd=repo,
        check=True,
    )
    head = _git(repo, "rev-parse", "HEAD")

    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = repo
        merge_files = lwb_lanes.commit_files(head)
        errors = lwb_lanes.check_lanes(f"{base}..{head}", 42)
    finally:
        lwb_lanes.REPO_ROOT = original_root

    # The merge's first-parent diff really does carry the codex file (the
    # thing that made the old, pre-fix behavior a latent bug) -- this
    # assertion pins that the fix isn't accidentally hiding it from
    # commit_files itself, only from lane-OWNERSHIP checking.
    assert merge_files == ["plugins/codex/lwb/bin/lwb_hook.py"]
    assert errors == [], errors


def test_check_lanes_merge_still_rejects_a_directly_authored_out_of_lane_file(tmp_path):
    """Must NOT regress: the merge exemption is for FILES THE MERGE BRINGS
    IN, not a blanket amnesty. A non-merge commit by the claude agent that
    directly touches a codex-lane file must still fail, exactly as
    before."""
    repo = tmp_path / "repo"
    _init_repo(repo)

    def _commit_with_trailer(path: str, content: str, message: str, agent: str) -> str:
        fp = repo / path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", f"{message}\n\nLWB-Agent: {agent}"],
            cwd=repo,
            check=True,
        )
        return _git(repo, "rev-parse", "HEAD")

    _commit_with_trailer("seed.txt", "seed\n", "seed", "human")
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit_with_trailer(
        "plugins/codex/lwb/bin/lwb_hook.py", "code\n", "claude touching codex's lane", "claude"
    )

    original_root = lwb_lanes.REPO_ROOT
    try:
        lwb_lanes.REPO_ROOT = repo
        errors = lwb_lanes.check_lanes(f"{base}..{head}", 42)
    finally:
        lwb_lanes.REPO_ROOT = original_root

    assert any("outside the claude lane" in e for e in errors), errors

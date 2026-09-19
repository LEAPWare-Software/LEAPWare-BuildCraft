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
    assert any("session-token" in e for e in errors), errors


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
    _write_review_pr(
        tmp_path, 19, "verifier.json",
        reviewer_id="lw-verifier-claude-opus-5-tokX-2026-09-20",
        commit_author_id="lw-implementer-claude-sonnet-5-tokX-2026-09-19",
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
    assert any("session-token" in e for e in errors), errors


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

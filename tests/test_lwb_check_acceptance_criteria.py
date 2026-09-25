"""Tests for scripts/lwb_check_acceptance_criteria.py.

D24 (docs/requirements/decisions.md): acceptance criteria must be anchored
to a GitHub issue's own creation timestamp, compared against the
deliverable's first commit. Conventions follow tests/test_lwb_check_state_
claims.py and tests/test_lwb_lanes.py: a real tmp_path git repo built via
subprocess, no mocking of git itself. `gh` is the one exception -- tests
stub it out via monkeypatching `m._gh_api_json`, the same pattern
tests/test_lwb_check_state_claims.py uses for `m._pr_state`, since CI has
no `gh` auth and a unit test must not depend on network access either.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import lwb_check_acceptance_criteria as m  # noqa: E402


# ---------------------------------------------------------------------------
# git repo fixtures
# ---------------------------------------------------------------------------


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    return repo


def _commit(repo: Path, name: str, text: str, *, author_date: str | None = None) -> str:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", name], cwd=repo, check=True)
    env = None
    if author_date is not None:
        env = dict(os.environ)
        env["GIT_AUTHOR_DATE"] = author_date
        env["GIT_COMMITTER_DATE"] = author_date
    subprocess.run(
        ["git", "commit", "-q", "-m", f"add {name}"],
        cwd=repo,
        check=True,
        env=env,
    )
    return _rev_parse(repo, "HEAD")


def _rev_parse(repo: Path, ref: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", ref], cwd=repo, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _seed_base_and_work(repo: Path) -> str:
    """`main` with one seed commit, then a fresh `work` branch off it --
    mirrors a real deliverable branch. Returns main's sha."""
    subprocess.run(["git", "checkout", "-b", "main"], cwd=repo, check=True)
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)
    main_sha = _rev_parse(repo, "HEAD")
    subprocess.run(["git", "checkout", "-b", "work"], cwd=repo, check=True)
    return main_sha


def _write_exempt(repo: Path, entries: list) -> None:
    path = repo / m.EXEMPT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries), encoding="utf-8")


# ---------------------------------------------------------------------------
# gh stub
# ---------------------------------------------------------------------------


def _fake_gh(*, pr_body: str | None = "", issue_created_at: str | None = None, error: str | None = None):
    """Returns a function with `_gh_api_json`'s exact signature, dispatching
    on whether the path names a PR or an issue -- mirrors
    tests/test_lwb_check_state_claims.py's `m._pr_state` stub pattern."""

    def fake(path: str, *, timeout: int = 20):
        if error is not None:
            return None, error
        if "/pulls/" in path:
            return {"body": pr_body if pr_body is not None else ""}, None
        if "/issues/" in path:
            return {"created_at": issue_created_at}, None
        raise AssertionError(f"unexpected gh path in test: {path}")

    return fake


# ---------------------------------------------------------------------------
# PASS / FAIL: the timestamp comparison itself
# ---------------------------------------------------------------------------


def test_issue_created_before_first_commit_is_pass(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    _seed_base_and_work(repo)
    first_sha = _commit(repo, "feature.txt", "work\n", author_date="2026-09-25T14:00:00+00:00")

    monkeypatch.setattr(
        m,
        "_gh_api_json",
        _fake_gh(pr_body="Closes #100", issue_created_at="2026-09-25T12:00:00Z"),
    )
    result = m.check_acceptance_criteria(
        repo=repo, base="main", head="work", pr_number=1, branch=None, gh_repo="o/r"
    )
    assert result.outcome == m.Outcome.PASS, result.render()
    assert result.exit_code == m.ACCEPTANCE_EXIT_PASS
    assert first_sha in result.message
    assert "#100" in result.message


def test_issue_created_exactly_at_first_commit_is_pass(tmp_path, monkeypatch):
    """The rule is <=, not <: an issue created at the same instant as the
    first commit's author date must not fail -- D24 asks for "before work
    starts", and the two clocks can plausibly agree to the second."""
    repo = _init_repo(tmp_path)
    _seed_base_and_work(repo)
    _commit(repo, "feature.txt", "work\n", author_date="2026-09-25T14:00:00+00:00")

    monkeypatch.setattr(
        m,
        "_gh_api_json",
        _fake_gh(pr_body="Closes #100", issue_created_at="2026-09-25T14:00:00Z"),
    )
    result = m.check_acceptance_criteria(
        repo=repo, base="main", head="work", pr_number=1, branch=None, gh_repo="o/r"
    )
    assert result.outcome == m.Outcome.PASS, result.render()


def test_issue_created_after_first_commit_is_fail_naming_both_timestamps(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    _seed_base_and_work(repo)
    first_sha = _commit(repo, "feature.txt", "work\n", author_date="2026-09-25T10:00:00+00:00")
    # The exact ISO-8601 UTC-offset spelling `git log --format=%aI` emits
    # for a zero offset is NOT pinned across git versions -- git 2.43
    # prints "+00:00", git 2.55 prints "Z" for the identical commit. Read
    # it back from git itself rather than assuming a spelling, so this
    # test is not version-fragile (found the hard way: this exact
    # assumption failed on a real CI runner's newer git while passing
    # locally).
    actual_first_author_date = m._commit_author_date(repo, first_sha)

    monkeypatch.setattr(
        m,
        "_gh_api_json",
        _fake_gh(pr_body="Fixes #200", issue_created_at="2026-09-25T12:00:00Z"),
    )
    result = m.check_acceptance_criteria(
        repo=repo, base="main", head="work", pr_number=1, branch=None, gh_repo="o/r"
    )
    assert result.outcome == m.Outcome.FAIL, result.render()
    assert result.exit_code == m.ACCEPTANCE_EXIT_FAIL
    # Both timestamps must be named in the failure message, per this
    # script's brief.
    assert "2026-09-25T12:00:00Z" in result.message
    assert actual_first_author_date in result.message
    assert first_sha in result.message
    assert "#200" in result.message


# ---------------------------------------------------------------------------
# No issue reference
# ---------------------------------------------------------------------------


def test_no_issue_reference_in_pr_body_is_fail_no_issue_reference(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    _seed_base_and_work(repo)
    _commit(repo, "feature.txt", "work\n")

    monkeypatch.setattr(m, "_gh_api_json", _fake_gh(pr_body="No closing keyword here at all."))
    result = m.check_acceptance_criteria(
        repo=repo, base="main", head="work", pr_number=1, branch=None, gh_repo="o/r"
    )
    assert result.outcome == m.Outcome.NO_ISSUE_REFERENCE, result.render()
    assert result.exit_code == m.ACCEPTANCE_EXIT_FAIL


def test_find_closing_issue_matches_all_keyword_spellings_case_insensitively():
    for text, expected in [
        ("this Closes #5", 5),
        ("CLOSED #6 today", 6),
        ("fix #7", 7),
        ("Fixes #8", 8),
        ("fixed #9", 9),
        ("resolve #10", 10),
        ("Resolves #11", 11),
        ("resolved #12", 12),
        ("no keyword here, #13 is just a number", None),
    ]:
        assert m.find_closing_issue(text) == expected, text


def test_find_closing_issue_multiple_matches_first_one_wins():
    body = "Closes #10 and also fixes #20"
    assert m.find_closing_issue(body) == 10


# ---------------------------------------------------------------------------
# Exemption mechanism
# ---------------------------------------------------------------------------


def test_pr_in_exempt_file_is_exempt_even_with_no_issue_reference(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    _seed_base_and_work(repo)
    _commit(repo, "feature.txt", "work\n")
    _write_exempt(repo, [{"pr": 42, "branch": None, "reason": "pre-D24 spike work"}])

    def _boom(*args, **kwargs):
        raise AssertionError("gh must not be called for an exempted deliverable")

    monkeypatch.setattr(m, "_gh_api_json", _boom)
    result = m.check_acceptance_criteria(
        repo=repo, base="main", head="work", pr_number=42, branch=None, gh_repo="o/r"
    )
    assert result.outcome == m.Outcome.EXEMPT, result.render()
    assert result.exit_code == m.ACCEPTANCE_EXIT_PASS
    assert "pre-D24 spike work" in result.message


def test_branch_in_exempt_file_is_exempt(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    _seed_base_and_work(repo)
    _commit(repo, "feature.txt", "work\n")
    _write_exempt(repo, [{"pr": None, "branch": "lwb-spike-thing", "reason": "incident fix"}])

    def _boom(*args, **kwargs):
        raise AssertionError("gh must not be called for an exempted deliverable")

    monkeypatch.setattr(m, "_gh_api_json", _boom)
    result = m.check_acceptance_criteria(
        repo=repo,
        base="main",
        head="work",
        pr_number=None,
        branch="lwb-spike-thing",
        gh_repo="o/r",
    )
    assert result.outcome == m.Outcome.EXEMPT, result.render()
    assert "incident fix" in result.message


def test_exempt_entry_does_not_match_an_unrelated_pr(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    _seed_base_and_work(repo)
    _commit(repo, "feature.txt", "work\n", author_date="2026-09-25T10:00:00+00:00")
    _write_exempt(repo, [{"pr": 999, "branch": None, "reason": "unrelated deliverable"}])

    monkeypatch.setattr(m, "_gh_api_json", _fake_gh(pr_body="no keyword"))
    result = m.check_acceptance_criteria(
        repo=repo, base="main", head="work", pr_number=1, branch=None, gh_repo="o/r"
    )
    assert result.outcome == m.Outcome.NO_ISSUE_REFERENCE, result.render()


# ---------------------------------------------------------------------------
# gh unavailable / unauthenticated / network failure
# ---------------------------------------------------------------------------


def test_gh_unavailable_is_unverifiable_not_pass(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    _seed_base_and_work(repo)
    _commit(repo, "feature.txt", "work\n")

    monkeypatch.setattr(
        m, "_gh_api_json", _fake_gh(error="the 'gh' executable is not installed on this machine")
    )
    result = m.check_acceptance_criteria(
        repo=repo, base="main", head="work", pr_number=1, branch=None, gh_repo="o/r"
    )
    assert result.outcome == m.Outcome.UNVERIFIABLE, result.render()
    assert result.exit_code == m.ACCEPTANCE_EXIT_UNVERIFIABLE
    assert result.exit_code not in (m.ACCEPTANCE_EXIT_PASS, m.ACCEPTANCE_EXIT_FAIL)


def test_gh_failure_fetching_the_linked_issue_is_also_unverifiable(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    _seed_base_and_work(repo)
    _commit(repo, "feature.txt", "work\n")

    def fake(path, *, timeout=20):
        if "/pulls/" in path:
            return {"body": "Closes #7"}, None
        return None, "gh api rate limited"

    monkeypatch.setattr(m, "_gh_api_json", fake)
    result = m.check_acceptance_criteria(
        repo=repo, base="main", head="work", pr_number=1, branch=None, gh_repo="o/r"
    )
    assert result.outcome == m.Outcome.UNVERIFIABLE, result.render()


def test_gh_api_json_missing_executable_reports_unverifiable_reason(monkeypatch):
    def _raise(*args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr(subprocess, "run", _raise)
    data, error = m._gh_api_json("repos/o/r/pulls/1")
    assert data is None
    assert "gh" in error


# ---------------------------------------------------------------------------
# Empty / unresolvable range
# ---------------------------------------------------------------------------


def test_empty_range_head_equals_base_is_distinct_not_pass_or_fail(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    _seed_base_and_work(repo)
    # No commit made on `work`: base and head are the same commit.

    def _boom(*args, **kwargs):
        raise AssertionError("gh must not be called when there is no range to check")

    monkeypatch.setattr(m, "_gh_api_json", _boom)
    result = m.check_acceptance_criteria(
        repo=repo, base="main", head="work", pr_number=1, branch=None, gh_repo="o/r"
    )
    assert result.outcome == m.Outcome.NO_RANGE, result.render()
    assert result.exit_code == m.ACCEPTANCE_EXIT_NO_RANGE
    assert result.exit_code not in (m.ACCEPTANCE_EXIT_PASS, m.ACCEPTANCE_EXIT_FAIL)


def test_base_unresolvable_is_distinct_not_pass_or_fail(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    _seed_base_and_work(repo)
    _commit(repo, "feature.txt", "work\n")

    def _boom(*args, **kwargs):
        raise AssertionError("gh must not be called when base does not resolve")

    monkeypatch.setattr(m, "_gh_api_json", _boom)
    result = m.check_acceptance_criteria(
        repo=repo,
        base="origin/does-not-exist",
        head="work",
        pr_number=1,
        branch=None,
        gh_repo="o/r",
    )
    assert result.outcome == m.Outcome.NO_RANGE, result.render()
    assert result.exit_code == m.ACCEPTANCE_EXIT_NO_RANGE
    assert result.exit_code not in (m.ACCEPTANCE_EXIT_PASS, m.ACCEPTANCE_EXIT_FAIL)


# ---------------------------------------------------------------------------
# The first-commit walk: a merge-forward-from-base must not be mistaken
# for the deliverable's own first commit.
# ---------------------------------------------------------------------------


def test_merge_forward_from_base_does_not_change_the_first_commit(tmp_path, monkeypatch):
    """branch diverges, base advances, branch merges base in, THEN check:
    the merge commit must not be mistaken for the deliverable's own first
    commit, and the ORIGINAL first commit (before the merge) must still be
    the one used."""
    repo = _init_repo(tmp_path)
    _seed_base_and_work(repo)  # main: seed. work: branched off main.

    # The deliverable's real first commit.
    first_sha = _commit(repo, "feature1.txt", "one\n", author_date="2026-09-25T09:00:00+00:00")
    # A second commit on the deliverable branch.
    _commit(repo, "feature2.txt", "two\n", author_date="2026-09-25T09:30:00+00:00")

    # Base advances after the deliverable branched off it.
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True)
    _commit(repo, "main2.txt", "advance\n", author_date="2026-09-25T09:45:00+00:00")

    # The deliverable branch merges base forward to resolve a conflict --
    # this repo's own conductor routines do this constantly (see the
    # module docstring).
    subprocess.run(["git", "checkout", "work"], cwd=repo, check=True)
    env = dict(os.environ)
    env["GIT_AUTHOR_DATE"] = "2026-09-25T10:00:00+00:00"
    env["GIT_COMMITTER_DATE"] = "2026-09-25T10:00:00+00:00"
    subprocess.run(
        ["git", "merge", "main", "--no-ff", "-m", "merge main into work"],
        cwd=repo,
        check=True,
        env=env,
    )

    resolved_sha, author_date, range_result = m.resolve_first_commit(repo, "main", "work")
    assert range_result is None, range_result
    assert resolved_sha == first_sha, (
        f"expected the deliverable's ORIGINAL first commit {first_sha}, got {resolved_sha}"
    )
    # Compare against what git itself reports for that commit, not a
    # hardcoded ISO-8601 spelling -- see the note in
    # test_issue_created_after_first_commit_is_fail_naming_both_timestamps
    # about %aI's "+00:00" vs "Z" divergence across git versions.
    assert author_date == m._commit_author_date(repo, first_sha)


def test_check_acceptance_criteria_uses_the_original_first_commit_through_a_merge(
    tmp_path, monkeypatch
):
    """End-to-end version of the merge-forward scenario above: the PASS/
    FAIL decision itself must key off the pre-merge first commit."""
    repo = _init_repo(tmp_path)
    _seed_base_and_work(repo)
    _commit(repo, "feature1.txt", "one\n", author_date="2026-09-25T09:00:00+00:00")

    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True)
    _commit(repo, "main2.txt", "advance\n", author_date="2026-09-25T09:45:00+00:00")
    subprocess.run(["git", "checkout", "work"], cwd=repo, check=True)
    env = dict(os.environ)
    env["GIT_AUTHOR_DATE"] = "2026-09-25T10:00:00+00:00"
    env["GIT_COMMITTER_DATE"] = "2026-09-25T10:00:00+00:00"
    subprocess.run(
        ["git", "merge", "main", "--no-ff", "-m", "merge main into work"],
        cwd=repo,
        check=True,
        env=env,
    )

    # An issue created at 09:30 -- AFTER the real first commit (09:00) but
    # BEFORE the merge commit (10:00). If the merge commit were wrongly
    # treated as "the first commit", this would wrongly PASS.
    monkeypatch.setattr(
        m,
        "_gh_api_json",
        _fake_gh(pr_body="Closes #77", issue_created_at="2026-09-25T09:30:00Z"),
    )
    result = m.check_acceptance_criteria(
        repo=repo, base="main", head="work", pr_number=1, branch=None, gh_repo="o/r"
    )
    assert result.outcome == m.Outcome.FAIL, result.render()


# ---------------------------------------------------------------------------
# Malformed acceptance_exempt.json
# ---------------------------------------------------------------------------


def test_exempt_entry_with_both_pr_and_branch_null_is_rejected_loudly(tmp_path):
    repo = _init_repo(tmp_path)
    _seed_base_and_work(repo)
    _write_exempt(repo, [{"pr": None, "branch": None, "reason": "nothing to match"}])

    entries, error = m.load_exemptions(repo)
    assert entries is None
    assert error is not None
    assert "both 'pr' and 'branch' are null" in error


def test_exempt_entry_missing_reason_is_rejected_loudly(tmp_path):
    repo = _init_repo(tmp_path)
    _seed_base_and_work(repo)
    _write_exempt(repo, [{"pr": 5, "branch": None}])

    entries, error = m.load_exemptions(repo)
    assert entries is None
    assert error is not None
    assert "reason" in error


def test_exempt_entry_with_empty_string_reason_is_rejected_loudly(tmp_path):
    repo = _init_repo(tmp_path)
    _seed_base_and_work(repo)
    _write_exempt(repo, [{"pr": 5, "branch": None, "reason": "   "}])

    entries, error = m.load_exemptions(repo)
    assert entries is None
    assert error is not None


def test_malformed_exempt_file_surfaces_as_config_error_not_silently_ignored(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    _seed_base_and_work(repo)
    _commit(repo, "feature.txt", "work\n")
    _write_exempt(repo, [{"pr": None, "branch": None, "reason": "bad entry"}])

    def _boom(*args, **kwargs):
        raise AssertionError("gh must not be called when config itself is broken")

    monkeypatch.setattr(m, "_gh_api_json", _boom)
    result = m.check_acceptance_criteria(
        repo=repo, base="main", head="work", pr_number=1, branch=None, gh_repo="o/r"
    )
    assert result.outcome == m.Outcome.CONFIG_ERROR, result.render()
    assert result.exit_code == m.ACCEPTANCE_EXIT_CONFIG_ERROR


def test_missing_exempt_file_is_treated_as_zero_entries_not_a_config_error(tmp_path):
    repo = _init_repo(tmp_path)
    _seed_base_and_work(repo)
    # docs/requirements/acceptance_exempt.json intentionally not written.
    entries, error = m.load_exemptions(repo)
    assert entries == []
    assert error is None


# ---------------------------------------------------------------------------
# --pr not given
# ---------------------------------------------------------------------------


def test_no_pr_given_and_not_exempt_is_config_error_not_unverifiable(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    _seed_base_and_work(repo)
    _commit(repo, "feature.txt", "work\n")

    def _boom(*args, **kwargs):
        raise AssertionError("gh must not be called with no PR number to fetch")

    monkeypatch.setattr(m, "_gh_api_json", _boom)
    result = m.check_acceptance_criteria(
        repo=repo, base="main", head="work", pr_number=None, branch=None, gh_repo="o/r"
    )
    assert result.outcome == m.Outcome.CONFIG_ERROR, result.render()
    assert result.outcome != m.Outcome.UNVERIFIABLE


# ---------------------------------------------------------------------------
# --help / CLI smoke test
# ---------------------------------------------------------------------------


def test_help_runs_cleanly():
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent.parent / "scripts" / "lwb_check_acceptance_criteria.py"), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--pr" in result.stdout
    assert "--base" in result.stdout


# ---------------------------------------------------------------------------
# Non-vacuous PASS/FAIL logic: the exit-code enum is genuinely distinct.
# ---------------------------------------------------------------------------


def test_all_seven_outcomes_map_to_the_documented_exit_codes():
    """Pins the exit-code table in the module docstring -- PASS and EXEMPT
    share code 0 (deliberately, per this script's brief); every other
    outcome has its OWN distinct non-zero code."""
    assert m._OUTCOME_EXIT_CODE[m.Outcome.PASS] == 0
    assert m._OUTCOME_EXIT_CODE[m.Outcome.EXEMPT] == 0
    non_zero = {
        m.Outcome.FAIL: m._OUTCOME_EXIT_CODE[m.Outcome.FAIL],
        m.Outcome.NO_ISSUE_REFERENCE: m._OUTCOME_EXIT_CODE[m.Outcome.NO_ISSUE_REFERENCE],
        m.Outcome.UNVERIFIABLE: m._OUTCOME_EXIT_CODE[m.Outcome.UNVERIFIABLE],
        m.Outcome.NO_RANGE: m._OUTCOME_EXIT_CODE[m.Outcome.NO_RANGE],
        m.Outcome.CONFIG_ERROR: m._OUTCOME_EXIT_CODE[m.Outcome.CONFIG_ERROR],
    }
    for code in non_zero.values():
        assert code != 0
    # FAIL and NO_ISSUE_REFERENCE are the one deliberate pair that DOES
    # share a code (both are "a completion claim that should block once
    # armed") -- everything else must be pairwise distinct.
    assert non_zero[m.Outcome.FAIL] == non_zero[m.Outcome.NO_ISSUE_REFERENCE]
    distinct = {non_zero[m.Outcome.FAIL], non_zero[m.Outcome.UNVERIFIABLE],
                non_zero[m.Outcome.NO_RANGE], non_zero[m.Outcome.CONFIG_ERROR]}
    assert len(distinct) == 4

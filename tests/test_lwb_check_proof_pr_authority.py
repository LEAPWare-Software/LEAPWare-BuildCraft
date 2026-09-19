"""Tests for the CI-authoritative PR number check in lwb_check_proof.py.

Adversarial re-review of the filename-authority mechanism
(`_authoritative_pr_from_filename`) found it illusory for a NEWLY CREATED
file: the filename is exactly as attacker-controlled as the record's own
`pr` field when both are being written for the first time in the same PR.
Two disclosed bypasses: a slug-named record (`proof/sneaky-slug.json`
with `"pr": 19`) and a self-consistent fabricated digit filename
(`proof/007.json` with `"pr": 7`) -- neither trips the filename-mismatch
check, because there is nothing to disagree with.

`reviews/<pr>/` genuinely has external authority because the DIRECTORY is
named by the PR under review -- something the record's own author does not
control after the fact. `proof/` has no such directory. The one place a
PR number IS genuinely external to every record's own content is CI
itself: `.github/workflows/ci.yml`'s `lwb-proof-pr` step already knows
`github.event.pull_request.number` and passes it as `--pr N`. This test
file covers `check_new_proof_records_declare_pr`, which uses that CLI
number (already threaded, no workflow change needed) to check every
proof/*.json file that is NEW or CHANGED in this PR's diff against a base
ref: such a file must self-declare `pr` == the real PR number, independent
of what its filename says.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lwb_check_proof  # noqa: E402


def _run(*args, cwd):
    subprocess.run(list(args), cwd=cwd, check=True, capture_output=True)


def _init_repo(tmp_path) -> Path:
    repo = tmp_path / "pra"
    repo.mkdir()
    _run("git", "init", "-q", cwd=repo)
    _run("git", "config", "user.email", "fixture@example.com", cwd=repo)
    _run("git", "config", "user.name", "Fixture", cwd=repo)
    (repo / "proof").mkdir()
    (repo / "f.txt").write_text("base\n", encoding="utf-8")
    _run("git", "add", ".", cwd=repo)
    _run("git", "commit", "-q", "-m", "base", cwd=repo)
    return repo


def _write_record(repo: Path, name: str, data: dict) -> None:
    (repo / "proof" / name).write_text(json.dumps(data), encoding="utf-8")


def _commit_all(repo: Path, message: str) -> None:
    _run("git", "add", ".", cwd=repo)
    _run("git", "commit", "-q", "-m", message, cwd=repo)


def _with_repo_root(repo: Path, fn, *args, **kwargs):
    orig_root, orig_dir = lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR
    try:
        lwb_check_proof.REPO_ROOT = repo
        lwb_check_proof.PROOF_DIR = repo / "proof"
        return fn(*args, **kwargs)
    finally:
        lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR = orig_root, orig_dir


def test_new_or_changed_proof_paths_finds_an_added_file(tmp_path):
    repo = _init_repo(tmp_path)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    _write_record(repo, "20.json", {"pr": 20})
    _commit_all(repo, "add record")

    paths = _with_repo_root(repo, lwb_check_proof._new_or_changed_proof_paths, f"{base}..HEAD")
    assert paths == {"proof/20.json"}


def test_new_or_changed_proof_paths_returns_none_on_unresolvable_range(tmp_path):
    repo = _init_repo(tmp_path)
    paths = _with_repo_root(
        repo, lwb_check_proof._new_or_changed_proof_paths, "no-such-ref-at-all..HEAD"
    )
    assert paths is None


def test_slug_named_bypass_is_caught_by_the_ci_authoritative_check(tmp_path):
    """The exact first disclosed bypass: a slug-named file self-declaring a
    stale PR number to dodge the pr >= 20 field requirements."""
    repo = _init_repo(tmp_path)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    _write_record(repo, "sneaky-slug.json", {"pr": 19, "deliverable": "sneaky"})
    _commit_all(repo, "add sneaky record")

    errors = _with_repo_root(
        repo,
        lwb_check_proof.check_new_proof_records_declare_pr,
        20,
        f"{base}..HEAD",
    )
    assert any(
        "sneaky-slug.json" in e and "20" in e and "19" in e for e in errors
    ), errors


def test_fabricated_digit_filename_bypass_is_caught_by_the_ci_authoritative_check(tmp_path):
    """The second disclosed bypass: a SELF-CONSISTENT fabricated digit
    filename (007.json declaring pr: 7) -- agreement with its own filename
    gives it zero errors under _authoritative_pr_from_filename alone. The
    CI-authoritative check does not care about the filename at all."""
    repo = _init_repo(tmp_path)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    _write_record(repo, "007.json", {"pr": 7, "deliverable": "7"})
    _commit_all(repo, "add fabricated record")

    errors = _with_repo_root(
        repo,
        lwb_check_proof.check_new_proof_records_declare_pr,
        20,
        f"{base}..HEAD",
    )
    assert any("007.json" in e and "20" in e and "7" in e for e in errors), errors


def test_a_record_that_honestly_declares_the_real_pr_passes(tmp_path):
    repo = _init_repo(tmp_path)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    _write_record(repo, "20.json", {"pr": 20, "deliverable": "20"})
    _commit_all(repo, "add honest record")

    errors = _with_repo_root(
        repo,
        lwb_check_proof.check_new_proof_records_declare_pr,
        20,
        f"{base}..HEAD",
    )
    assert errors == []


def test_an_unchanged_historical_record_is_not_flagged(tmp_path):
    """A record already on the base branch (not part of THIS PR's diff)
    must never be flagged just because its pr differs from the PR
    currently under CI."""
    repo = _init_repo(tmp_path)
    _write_record(repo, "7.json", {"pr": 7, "deliverable": "7"})
    _commit_all(repo, "historical record")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    (repo / "f.txt").write_text("changed\n", encoding="utf-8")
    _commit_all(repo, "unrelated change")

    errors = _with_repo_root(
        repo,
        lwb_check_proof.check_new_proof_records_declare_pr,
        20,
        f"{base}..HEAD",
    )
    assert errors == []


def test_unresolvable_range_degrades_to_a_notice_not_an_error(tmp_path):
    """When the diff itself cannot be computed (no such ref in this
    checkout), this is not silently treated as ALL-CLEAR: no errors are
    manufactured, but a notice says the pr field is self-declared and
    unverified in this run."""
    repo = _init_repo(tmp_path)
    notices: list[str] = []
    errors = _with_repo_root(
        repo,
        lwb_check_proof.check_new_proof_records_declare_pr,
        20,
        "no-such-ref..HEAD",
        notices,
    )
    assert errors == []
    assert any("unverified" in n or "UNVERIFIED" in n for n in notices), notices


def test_main_threads_explicit_base_head_in_preference_to_the_default(tmp_path, monkeypatch):
    """`.github/workflows/ci.yml`'s sibling base/head-sensitive steps
    (lwb_check_commit_identity.py, lwb_lanes.py, lwb_check_env_leak.py
    --range) all pass github.event.pull_request.base.sha / head.sha
    explicitly, because HEAD in a pull_request checkout is the synthetic
    refs/pull/N/merge commit -- this check must not be the lone exception
    relying on its own hardcoded 'origin/main..HEAD' default. main() must
    prefer an explicit --base/--head over that default."""
    repo = _init_repo(tmp_path)
    captured = {}

    def fake_check(pr_number, rev_range="origin/main..HEAD", notices=None):
        captured["pr_number"] = pr_number
        captured["rev_range"] = rev_range
        return []

    monkeypatch.setattr(lwb_check_proof, "check_new_proof_records_declare_pr", fake_check)
    monkeypatch.setattr(
        lwb_check_proof.sys,
        "argv",
        [
            "lwb_check_proof.py",
            "--pr", "20",
            "--base", "deadbeef0000000000000000000000000000dead",
            "--head", "beefdead0000000000000000000000000000beef",
        ],
    )
    _with_repo_root(repo, lwb_check_proof.main)
    assert captured["pr_number"] == 20
    assert captured["rev_range"] == (
        "deadbeef0000000000000000000000000000dead..beefdead0000000000000000000000000000beef"
    )


def test_main_falls_back_to_default_range_without_explicit_base_head(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    captured = {}

    def fake_check(pr_number, rev_range="origin/main..HEAD", notices=None):
        captured["rev_range"] = rev_range
        return []

    monkeypatch.setattr(lwb_check_proof, "check_new_proof_records_declare_pr", fake_check)
    monkeypatch.setattr(lwb_check_proof.sys, "argv", ["lwb_check_proof.py", "--pr", "20"])
    _with_repo_root(repo, lwb_check_proof.main)
    assert captured["rev_range"] == "origin/main..HEAD"


def test_deleted_proof_file_is_not_flagged(tmp_path):
    """A file deleted in this PR's diff is not on disk to read -- must be
    skipped, not crash or falsely flag."""
    repo = _init_repo(tmp_path)
    _write_record(repo, "old.json", {"pr": 5})
    _commit_all(repo, "add old record")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    (repo / "proof" / "old.json").unlink()
    _commit_all(repo, "delete old record")

    errors = _with_repo_root(
        repo,
        lwb_check_proof.check_new_proof_records_declare_pr,
        20,
        f"{base}..HEAD",
    )
    assert errors == []

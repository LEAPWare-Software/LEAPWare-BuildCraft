"""Tests for the flat-proof/-layout check in lwb_check_proof.py.

Adversarial review found a scope mismatch between the two checks that look
at proof/*.json files: `check_new_proof_records_declare_pr` finds files via
`git diff -- proof`, which matches RECURSIVELY, while `validate_all()` and
`check_pr_has_record()` use `PROOF_DIR.glob("*.json")`, which does NOT. A
record at `proof/sub/20.json` would be seen (and pr-checked) by the first
and completely invisible to the others -- it could carry no
`sanitiser_version`, no `verifiable`, malformed `commands[]`, and nothing
would ever validate it.

Decision: reject a nested proof/**/*.json outright rather than make the
glob recursive everywhere. `proof/README.md` documents a flat
`proof/<id>.json` convention; a nested file is more likely an editor
accident or an evasion attempt than a legitimate layout, and rejecting it
keeps every OTHER check's non-recursive glob correct rather than widening
scope to match the one check that happened to be recursive by accident.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lwb_check_proof  # noqa: E402


def _with_repo_root(repo: Path, fn, *args, **kwargs):
    orig_root, orig_dir = lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR
    try:
        lwb_check_proof.REPO_ROOT = repo
        lwb_check_proof.PROOF_DIR = repo / "proof"
        return fn(*args, **kwargs)
    finally:
        lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR = orig_root, orig_dir


def test_flat_proof_directory_has_no_layout_errors(tmp_path):
    repo = tmp_path / "flat"
    (repo / "proof").mkdir(parents=True)
    (repo / "proof" / "20.json").write_text(json.dumps({"pr": 20}), encoding="utf-8")
    errors = _with_repo_root(repo, lwb_check_proof.check_flat_proof_layout)
    assert errors == []


def test_nested_proof_file_is_rejected(tmp_path):
    repo = tmp_path / "nested"
    (repo / "proof" / "sub").mkdir(parents=True)
    (repo / "proof" / "sub" / "20.json").write_text(json.dumps({"pr": 20}), encoding="utf-8")
    errors = _with_repo_root(repo, lwb_check_proof.check_flat_proof_layout)
    assert len(errors) == 1
    assert "proof" in errors[0] and "sub" in errors[0] and "20.json" in errors[0]


def test_deeply_nested_proof_file_is_rejected(tmp_path):
    repo = tmp_path / "deep"
    (repo / "proof" / "a" / "b").mkdir(parents=True)
    (repo / "proof" / "a" / "b" / "c.json").write_text("{}", encoding="utf-8")
    errors = _with_repo_root(repo, lwb_check_proof.check_flat_proof_layout)
    assert len(errors) == 1


def test_missing_proof_directory_has_no_layout_errors(tmp_path):
    repo = tmp_path / "missing"
    repo.mkdir()
    errors = _with_repo_root(repo, lwb_check_proof.check_flat_proof_layout)
    assert errors == []


def test_no_proof_directory_is_missing_from_this_repo():
    """The real proof/ directory in THIS repo must itself be flat -- a
    layout violation in the actual repo would mean this check, if it
    existed, was never run."""
    errors = lwb_check_proof.check_flat_proof_layout()
    assert errors == []


def test_scope_agreement_nested_file_invisible_to_validate_all_but_rejected_by_layout_check(tmp_path):
    """Pins the exact defect: validate_all()'s non-recursive glob never
    sees a nested file at all (silently), but check_flat_proof_layout DOES
    see it and rejects it -- so main()'s combined error list is never
    silent about a nested record, even though validate_all() alone would
    be."""
    repo = tmp_path / "scope"
    (repo / "proof" / "sub").mkdir(parents=True)
    (repo / "proof" / "sub" / "20.json").write_text(
        json.dumps({"pr": 20, "commands": "not-a-list"}), encoding="utf-8"
    )

    all_errors, count = _with_repo_root(repo, lwb_check_proof.validate_all)
    assert count == 0  # invisible to the non-recursive glob, as before
    assert all_errors == []  # validate_all() alone says nothing

    layout_errors = _with_repo_root(repo, lwb_check_proof.check_flat_proof_layout)
    assert len(layout_errors) == 1  # but the layout check catches it


def test_new_proof_records_check_skips_nested_files_layout_check_owns_them(tmp_path):
    """check_new_proof_records_declare_pr must not ALSO independently
    pr-check a nested file -- check_flat_proof_layout is the single
    authority that rejects it, so a nested file with a correct 'pr' does
    not silently pass the pr-authority check while remaining rejected by
    the layout check (which would be a confusing, inconsistent report)."""
    import subprocess

    repo = tmp_path / "scope2"
    repo.mkdir()
    run = lambda *a: subprocess.run(list(a), cwd=repo, check=True, capture_output=True)
    run("git", "init", "-q")
    run("git", "config", "user.email", "fixture@example.com")
    run("git", "config", "user.name", "Fixture")
    (repo / "proof").mkdir()
    (repo / "f.txt").write_text("base\n", encoding="utf-8")
    run("git", "add", ".")
    run("git", "commit", "-q", "-m", "base")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    (repo / "proof" / "sub").mkdir()
    (repo / "proof" / "sub" / "20.json").write_text(
        json.dumps({"pr": 20}), encoding="utf-8"
    )
    run("git", "add", ".")
    run("git", "commit", "-q", "-m", "nested record")

    errors = _with_repo_root(
        repo,
        lwb_check_proof.check_new_proof_records_declare_pr,
        20,
        f"{base}..HEAD",
    )
    assert errors == []

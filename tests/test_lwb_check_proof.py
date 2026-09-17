"""Tests for scripts/lwb_check_proof.py against tests/fixtures/proof/.

These fixtures live under tests/fixtures/proof/, never under the real
proof/ directory — proof/ is proof of a real deliverable, not test data
(see proof/README.md: "This scaffolding session wrote NO proof records").
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lwb_check_proof  # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "proof"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_valid_record_has_no_errors():
    errors = lwb_check_proof._validate_record(FIXTURES / "valid.json", _load("valid.json"))
    assert errors == []


def _fixture_repo(tmp_path, subjects: list[str]):
    """A throwaway repo whose commits look like squash merges."""
    import subprocess

    repo = tmp_path / "cov"
    repo.mkdir()
    run = lambda *a: subprocess.run(list(a), cwd=repo, check=True, capture_output=True)
    run("git", "init", "-q")
    run("git", "config", "user.email", "fixture@example.com")
    run("git", "config", "user.name", "Fixture")
    (repo / "f.txt").write_text("base\n", encoding="utf-8")
    run("git", "add", ".")
    run("git", "commit", "-q", "-m", "base")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    shas = []
    for i, subject in enumerate(subjects):
        (repo / "f.txt").write_text(f"change {i}\n", encoding="utf-8")
        run("git", "add", ".")
        run("git", "commit", "-q", "-m", subject)
        shas.append(
            subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
            ).stdout.strip()
        )
    return repo, base, shas


def test_coverage_fails_for_a_landed_deliverable_with_no_record(tmp_path):
    """The defect this closes: validate_all only checks records that exist,
    so an empty proof/ reported 'skipped' and exited 0 while five
    deliverables merged straight through the gate."""
    repo, base, shas = _fixture_repo(tmp_path, ["feat: a thing (#7)"])
    (repo / "proof").mkdir()

    orig_root, orig_dir, orig_exempt = (
        lwb_check_proof.REPO_ROOT,
        lwb_check_proof.PROOF_DIR,
        lwb_check_proof.EXEMPT_PATH,
    )
    try:
        lwb_check_proof.REPO_ROOT = repo
        lwb_check_proof.PROOF_DIR = repo / "proof"
        lwb_check_proof.EXEMPT_PATH = repo / "proof" / "exempt.json"
        errors = lwb_check_proof.check_coverage(f"{base}..HEAD")
    finally:
        lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR, lwb_check_proof.EXEMPT_PATH = (
            orig_root,
            orig_dir,
            orig_exempt,
        )

    assert len(errors) == 1
    assert shas[0][:12] in errors[0]
    assert "no proof/*.json record" in errors[0]


def test_coverage_passes_when_a_record_names_the_commit(tmp_path):
    repo, base, shas = _fixture_repo(tmp_path, ["feat: a thing (#7)"])
    (repo / "proof").mkdir()
    (repo / "proof" / "d7.json").write_text(
        json.dumps({"commit": shas[0], "deliverable": "7"}), encoding="utf-8"
    )

    orig = (lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR, lwb_check_proof.EXEMPT_PATH)
    try:
        lwb_check_proof.REPO_ROOT = repo
        lwb_check_proof.PROOF_DIR = repo / "proof"
        lwb_check_proof.EXEMPT_PATH = repo / "proof" / "exempt.json"
        errors = lwb_check_proof.check_coverage(f"{base}..HEAD")
    finally:
        (lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR, lwb_check_proof.EXEMPT_PATH) = orig

    assert errors == []


def test_coverage_skips_an_exempted_sha(tmp_path):
    repo, base, shas = _fixture_repo(tmp_path, ["chore(deps): bump x (#8)"])
    (repo / "proof").mkdir()
    (repo / "proof" / "exempt.json").write_text(
        json.dumps({"merges": {shas[0]: {"pr": 8, "reason": "dependabot"}}}), encoding="utf-8"
    )

    orig = (lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR, lwb_check_proof.EXEMPT_PATH)
    try:
        lwb_check_proof.REPO_ROOT = repo
        lwb_check_proof.PROOF_DIR = repo / "proof"
        lwb_check_proof.EXEMPT_PATH = repo / "proof" / "exempt.json"
        errors = lwb_check_proof.check_coverage(f"{base}..HEAD")
    finally:
        (lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR, lwb_check_proof.EXEMPT_PATH) = orig

    assert errors == []


def test_coverage_ignores_commits_that_are_not_squash_merges(tmp_path):
    repo, base, _ = _fixture_repo(tmp_path, ["wip: not a merge"])
    (repo / "proof").mkdir()

    orig = (lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR, lwb_check_proof.EXEMPT_PATH)
    try:
        lwb_check_proof.REPO_ROOT = repo
        lwb_check_proof.PROOF_DIR = repo / "proof"
        lwb_check_proof.EXEMPT_PATH = repo / "proof" / "exempt.json"
        errors = lwb_check_proof.check_coverage(f"{base}..HEAD")
    finally:
        (lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR, lwb_check_proof.EXEMPT_PATH) = orig

    assert errors == []


def test_real_exempt_file_is_wellformed_and_only_covers_history():
    """Every exempt sha must be a real commit on this repo's history, so the
    list cannot quietly excuse a future merge."""
    import subprocess

    exempt = json.loads((REPO_ROOT / "proof" / "exempt.json").read_text(encoding="utf-8"))
    merges = exempt["merges"]
    assert merges, "exempt.json must name the gap explicitly, not be empty"
    for sha, entry in merges.items():
        assert "reason" in entry and entry["reason"].strip(), sha
        assert "pr" in entry, sha
        rc = subprocess.run(
            ["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=REPO_ROOT, capture_output=True
        ).returncode
        assert rc == 0, f"{sha} is not a commit in this repo"


def test_self_certified_record_is_rejected():
    errors = lwb_check_proof._validate_record(FIXTURES / "self_certified.json", _load("self_certified.json"))
    assert any("self-certified" in e for e in errors)


def test_exit_mismatch_record_is_rejected():
    errors = lwb_check_proof._validate_record(FIXTURES / "exit_mismatch.json", _load("exit_mismatch.json"))
    assert any("expect_exit" in e for e in errors)


def test_missing_field_record_is_rejected():
    errors = lwb_check_proof._validate_record(FIXTURES / "missing_field.json", _load("missing_field.json"))
    assert any("unproven" in e for e in errors)


def test_real_proof_directory_validates_clean():
    # This scaffolding session ships proof/ with no records yet (see
    # proof/README.md) -- an empty proof/ is not itself a failure. Once a
    # deliverable lands its own proof/<id>.json, the validator must still
    # find every record clean, not a failure.
    errors, count = lwb_check_proof.validate_all()
    assert errors == []
    assert count >= 0

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


def test_coverage_over_a_prs_own_range_finds_nothing(tmp_path):
    """Why --coverage alone is not enough, pinned as a test.

    GitHub fabricates the `(#N)` squash commit AT MERGE TIME, so a PR's own
    commits never carry that subject and --coverage over base..head can
    never fire. The first version of this check was wired exactly that way
    and was a guaranteed no-op; independent review of PR #6 caught it.
    """
    repo, base, _ = _fixture_repo(tmp_path, ["fix: real work", "docs: more real work"])
    (repo / "proof").mkdir()

    orig = (lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR, lwb_check_proof.EXEMPT_PATH)
    try:
        lwb_check_proof.REPO_ROOT = repo
        lwb_check_proof.PROOF_DIR = repo / "proof"
        lwb_check_proof.EXEMPT_PATH = repo / "proof" / "exempt.json"
        errors = lwb_check_proof.check_coverage(f"{base}..HEAD")
    finally:
        (lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR, lwb_check_proof.EXEMPT_PATH) = orig

    assert errors == [], "pre-merge commits carry no (#N), so coverage is silent here"


def test_pr_check_fails_when_no_record_names_the_pr(tmp_path):
    orig = (lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR)
    try:
        lwb_check_proof.REPO_ROOT = tmp_path
        lwb_check_proof.PROOF_DIR = tmp_path / "proof"
        errors = lwb_check_proof.check_pr_has_record(6)
    finally:
        (lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR) = orig

    assert len(errors) == 1
    assert "PR #6" in errors[0]


def test_pr_check_passes_only_on_the_typed_pr_field(tmp_path):
    proof_dir = tmp_path / "proof_pr"
    proof_dir.mkdir()
    (proof_dir / "r.json").write_text(json.dumps({"pr": 6}), encoding="utf-8")
    orig = (lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR)
    try:
        lwb_check_proof.REPO_ROOT = tmp_path
        lwb_check_proof.PROOF_DIR = proof_dir
        errors = lwb_check_proof.check_pr_has_record(6)
    finally:
        (lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR) = orig
    assert errors == [], errors


def test_a_digit_deliverable_does_not_satisfy_the_pr_gate(tmp_path):
    """The collision an earlier version of this check asserted as CORRECT.

    schema.json documents `deliverable` as "an issue/step number or a short
    slug", so a small integer is ordinary usage. Accepting it as an alias
    for the PR number meant a record proving step 6 of an unrelated plan
    silently satisfied PR #6's directive-7 gate forever. Found by
    independent review of PR #6; only the typed `pr` field counts now.
    """
    proof_dir = tmp_path / "proof_del"
    proof_dir.mkdir()
    (proof_dir / "r.json").write_text(
        json.dumps({"deliverable": "6", "author": "unrelated work"}), encoding="utf-8"
    )
    orig = (lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR)
    try:
        lwb_check_proof.REPO_ROOT = tmp_path
        lwb_check_proof.PROOF_DIR = proof_dir
        errors = lwb_check_proof.check_pr_has_record(6)
    finally:
        (lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR) = orig
    assert len(errors) == 1, errors


def test_coverage_is_not_satisfied_by_a_digit_deliverable(tmp_path):
    """Same collision on the post-merge half."""
    repo, base, _ = _fixture_repo(tmp_path, ["feat: thing (#7)"])
    (repo / "proof").mkdir()
    (repo / "proof" / "unrelated.json").write_text(
        json.dumps({"deliverable": "7", "author": "unrelated work"}), encoding="utf-8"
    )

    orig = (lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR, lwb_check_proof.EXEMPT_PATH)
    try:
        lwb_check_proof.REPO_ROOT = repo
        lwb_check_proof.PROOF_DIR = repo / "proof"
        lwb_check_proof.EXEMPT_PATH = repo / "proof" / "exempt.json"
        errors = lwb_check_proof.check_coverage(f"{base}..HEAD")
    finally:
        (lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR, lwb_check_proof.EXEMPT_PATH) = orig

    assert len(errors) == 1, errors


def test_pr_check_is_not_satisfied_by_another_prs_record(tmp_path):
    proof_dir = tmp_path / "proof"
    proof_dir.mkdir()
    (proof_dir / "r.json").write_text(json.dumps({"pr": 5, "deliverable": "5"}), encoding="utf-8")
    orig = (lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR)
    try:
        lwb_check_proof.REPO_ROOT = tmp_path
        lwb_check_proof.PROOF_DIR = proof_dir
        errors = lwb_check_proof.check_pr_has_record(6)
    finally:
        (lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR) = orig
    assert len(errors) == 1


def test_coverage_ignores_a_record_whose_commit_is_too_short(tmp_path):
    """A short/garbage `commit` must not satisfy coverage by prefix accident."""
    repo, base, shas = _fixture_repo(tmp_path, ["feat: thing (#9)"])
    (repo / "proof").mkdir()
    (repo / "proof" / "r.json").write_text(json.dumps({"commit": shas[0][:3]}), encoding="utf-8")

    orig = (lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR, lwb_check_proof.EXEMPT_PATH)
    try:
        lwb_check_proof.REPO_ROOT = repo
        lwb_check_proof.PROOF_DIR = repo / "proof"
        lwb_check_proof.EXEMPT_PATH = repo / "proof" / "exempt.json"
        errors = lwb_check_proof.check_coverage(f"{base}..HEAD")
    finally:
        (lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR, lwb_check_proof.EXEMPT_PATH) = orig

    assert len(errors) == 1


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


def test_coverage_matches_a_record_by_pr_number_not_only_commit(tmp_path):
    """A record is written INSIDE the PR it proves, so it can never name the
    squash-merge sha -- that sha is created at merge time. Keying coverage on
    the (#N) subject is what makes a properly-proven PR pass post-merge."""
    repo, base, shas = _fixture_repo(tmp_path, ["feat: thing (#11)"])
    (repo / "proof").mkdir()
    # Note: deliberately names a DIFFERENT commit (the pre-merge head).
    (repo / "proof" / "d11.json").write_text(
        json.dumps({"pr": 11, "deliverable": "11", "commit": base}), encoding="utf-8"
    )

    orig = (lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR, lwb_check_proof.EXEMPT_PATH)
    try:
        lwb_check_proof.REPO_ROOT = repo
        lwb_check_proof.PROOF_DIR = repo / "proof"
        lwb_check_proof.EXEMPT_PATH = repo / "proof" / "exempt.json"
        errors = lwb_check_proof.check_coverage(f"{base}..HEAD")
    finally:
        (lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR, lwb_check_proof.EXEMPT_PATH) = orig

    assert errors == [], errors
    assert shas[0] != base


def _pr12_base(**overrides):
    record = {
        "deliverable": "12",
        "author": "claude",
        "checked_by": "codex",
        "commit": "a" * 40,
        "commands": [],
        "mutations": [],
        "unproven": [],
        "pr": 12,
        "acceptance_criteria": [{"criterion": "it works", "met": True}],
        "tokens": {
            "total_input": 1,
            "cached_input": 0,
            "uncached_input": 1,
            "output": 1,
            "retries": 0,
            "setup_overhead": "unknown",
            "tool_overhead": "unknown",
            "wall_time_seconds": 1,
            "source": "transcript message.usage",
        },
    }
    record.update(overrides)
    return record


def test_pr12_record_missing_acceptance_criteria_fails():
    record = _pr12_base()
    del record["acceptance_criteria"]
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert any("acceptance_criteria" in e for e in errors)


def test_pr12_record_with_unmet_criterion_fails():
    record = _pr12_base(acceptance_criteria=[{"criterion": "it works", "met": False}])
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert any("'met' is false" in e for e in errors)


def test_pr12_record_missing_tokens_fails():
    record = _pr12_base()
    del record["tokens"]
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert any("'tokens' must be an object" in e for e in errors)


def test_pr12_record_with_total_input_zero_fails():
    record = _pr12_base()
    record["tokens"] = dict(record["tokens"])
    record["tokens"]["total_input"] = 0
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert any("tokens.total_input is 0" in e for e in errors)


def test_pr12_record_with_unknown_values_passes():
    errors = lwb_check_proof._validate_record(Path("r.json"), _pr12_base())
    assert errors == []


def test_pr12_record_with_spend_ledger_source_is_rejected():
    """FIX 3: 'spend-ledger' named a PowerShell script from a plugin the
    owner is removing -- nobody on a fresh clone can re-derive it, so a
    record citing it is unreproducible evidence."""
    record = _pr12_base()
    record["tokens"] = dict(record["tokens"])
    record["tokens"]["source"] = "spend-ledger"
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert any("tokens.source" in e and "spend-ledger" in e for e in errors)


def test_pr12_record_with_arbitrary_source_string_is_rejected():
    record = _pr12_base()
    record["tokens"] = dict(record["tokens"])
    record["tokens"]["source"] = "a very convincing but unverifiable claim"
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert any("tokens.source" in e for e in errors)


def test_pr12_record_with_source_unknown_is_accepted():
    record = _pr12_base()
    record["tokens"] = dict(record["tokens"])
    record["tokens"]["source"] = "unknown"
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert errors == []


def test_pr12_record_with_source_transcript_usage_is_accepted():
    record = _pr12_base()
    record["tokens"] = dict(record["tokens"])
    record["tokens"]["source"] = "transcript message.usage"
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert errors == []


def test_pr12_record_with_descriptive_transcript_usage_source_is_accepted():
    """The prefix rule, not a strict enum: detail after the origin -- which
    file, how many records were summed -- is honest provenance and must be
    allowed, not rejected as noise."""
    record = _pr12_base()
    record["tokens"] = dict(record["tokens"])
    record["tokens"]["source"] = (
        "transcript message.usage summed across 1083 usage-bearing assistant "
        "records in <home>/.claude/projects/<repo-slug>/<session-id>.jsonl "
        "(cached_input = cache_read + cache_creation; uncached_input = input_tokens)"
    )
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert errors == []


def test_pr12_record_with_leading_whitespace_before_source_prefix_is_rejected():
    """The prefix match is anchored at position 0 -- leading whitespace
    before an otherwise-allowed origin must still fail."""
    record = _pr12_base()
    record["tokens"] = dict(record["tokens"])
    record["tokens"]["source"] = "  transcript message.usage"
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert any("tokens.source" in e for e in errors)


def test_pr_below_12_record_with_bad_token_source_still_passes():
    """The pr >= 12 gate stays inert below 12: tokens.source enforcement
    must not retroactively break a record that predates the field."""
    record = {
        "deliverable": "11",
        "author": "claude",
        "checked_by": "codex",
        "commit": "a" * 40,
        "commands": [],
        "mutations": [],
        "unproven": [],
        "pr": 11,
        "tokens": {"source": "spend-ledger"},
    }
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert errors == []


def test_pr_below_12_record_without_new_fields_still_passes():
    record = {
        "deliverable": "11",
        "author": "claude",
        "checked_by": "codex",
        "commit": "a" * 40,
        "commands": [],
        "mutations": [],
        "unproven": [],
        "pr": 11,
    }
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert errors == []


def test_coverage_still_fails_when_the_record_names_a_different_pr(tmp_path):
    repo, base, _ = _fixture_repo(tmp_path, ["feat: thing (#11)"])
    (repo / "proof").mkdir()
    (repo / "proof" / "d12.json").write_text(json.dumps({"pr": 12}), encoding="utf-8")

    orig = (lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR, lwb_check_proof.EXEMPT_PATH)
    try:
        lwb_check_proof.REPO_ROOT = repo
        lwb_check_proof.PROOF_DIR = repo / "proof"
        lwb_check_proof.EXEMPT_PATH = repo / "proof" / "exempt.json"
        errors = lwb_check_proof.check_coverage(f"{base}..HEAD")
    finally:
        (lwb_check_proof.REPO_ROOT, lwb_check_proof.PROOF_DIR, lwb_check_proof.EXEMPT_PATH) = orig

    assert len(errors) == 1

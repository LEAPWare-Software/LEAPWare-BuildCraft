"""Tests for `scripts/lwb_check_proof.py --reexecute`.

SPEC-d2-ci-reexecution.md: re-run every command whose `verifiable` is
true, sanitise its output through `lwb_sanitise`, and compare the sha256
against the recorded digest. Four ways this becomes theatre, each guarded
here:

1. Recursion -- a recorded command whose argv resolves to
   `lwb_check_proof.py` must never be re-executed, gated by an explicit
   `--reexecute` flag (never itself present in any recorded argv) plus an
   independent skip of any self-referencing command.
2. Sanitiser drift -- a command whose `sanitiser_version` differs from the
   running `lwb_sanitise.SANITISER_VERSION` is reported UNCOMPARABLE, never
   silently passed or failed.
3. Empty is not success -- a record with zero verifiable commands reports
   "0 of N", never "all verified".
4. Exit codes -- a re-run whose exit differs from the recorded `exit` is a
   failure even when the digest happens to match.

`reexecute_verifiable_commands` takes an injectable `run` callable so these
tests never depend on real subprocess execution except where the test is
explicitly an integration test of real re-execution.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lwb_check_proof  # noqa: E402
import lwb_sanitise  # noqa: E402


def _proc(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def _digest_for(text: str) -> str:
    return hashlib.sha256(lwb_sanitise.sanitise(text).encode("utf-8")).hexdigest()


def _record(commands):
    return {
        "deliverable": "x",
        "author": "a",
        "checked_by": "b",
        "commit": "a" * 40,
        "commands": commands,
        "mutations": [],
        "unproven": [],
    }


def _cmd(argv, **overrides):
    base = {
        "argv": argv,
        "exit": 0,
        "expect_exit": 0,
        "tail": ["ok"],
        "sha256": "b" * 64,
        "sanitiser_version": lwb_sanitise.SANITISER_VERSION,
        "verifiable": True,
    }
    base.update(overrides)
    return base


# --- Guard 1: recursion --------------------------------------------------


def test_self_referencing_command_is_skipped_never_invoked():
    """A recorded command naming lwb_check_proof.py must never reach the
    injected runner -- if the guard were missing, this test's runner would
    be called and would raise, simulating the hang/recursion the guard
    exists to prevent."""

    def _runner(argv, **kwargs):
        raise AssertionError(f"must never re-execute a self-referencing command: {argv!r}")

    records = [("proof/x.json", _record([_cmd(["python", "scripts/lwb_check_proof.py"])]))]
    report = lwb_check_proof.reexecute_verifiable_commands(records, run=_runner)
    assert report["total_reexecuted"] == 0
    assert any("SKIPPED-SELF" in line for line in report["lines"])
    assert report["failures"] == []


def test_self_referencing_command_with_pr_flag_is_also_skipped():
    def _runner(argv, **kwargs):
        raise AssertionError(f"must never re-execute: {argv!r}")

    records = [
        (
            "proof/x.json",
            _record([_cmd(["python", "scripts/lwb_check_proof.py", "--pr", "20"])]),
        )
    ]
    report = lwb_check_proof.reexecute_verifiable_commands(records, run=_runner)
    assert report["total_reexecuted"] == 0
    assert any("SKIPPED-SELF" in line for line in report["lines"])


def test_reexecute_flag_never_appears_in_any_recorded_argv():
    """The mode is gated on an explicit --reexecute flag that must never
    appear in a recorded argv -- otherwise a re-executed command could pass
    the flag on to a nested lwb_check_proof.py invocation and recurse."""
    import json

    proof_dir = REPO_ROOT / "proof"
    for path in sorted(proof_dir.glob("*.json")):
        if path.name in ("schema.json", "exempt.json"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for cmd in data.get("commands", []):
            argv = cmd.get("argv") if isinstance(cmd, dict) else None
            if isinstance(argv, list):
                assert "--reexecute" not in argv, f"{path}: {argv!r}"


# --- Guard 2: sanitiser drift ---------------------------------------------


def test_sanitiser_version_mismatch_is_uncomparable_not_pass_or_fail():
    def _runner(argv, **kwargs):
        raise AssertionError("a version-mismatched command must not be re-run")

    records = [
        (
            "proof/x.json",
            _record([_cmd(["python", "scripts/lwb_check_prefix.py"], sanitiser_version="0")]),
        )
    ]
    report = lwb_check_proof.reexecute_verifiable_commands(records, run=_runner)
    assert report["total_reexecuted"] == 0
    assert any("UNCOMPARABLE" in line for line in report["lines"])
    assert report["failures"] == []


# --- Guard 3: empty is not success -----------------------------------------


def test_record_with_zero_verifiable_commands_reports_0_of_n():
    records = [
        (
            "proof/x.json",
            _record(
                [
                    _cmd(["python", "-m", "pytest"], verifiable=False, verifiable_reason="nondeterministic-output"),
                    _cmd(["python", "scripts/lwb_check_env_leak.py"], verifiable=False, verifiable_reason="needs-repo-secret"),
                ]
            ),
        )
    ]
    report = lwb_check_proof.reexecute_verifiable_commands(records, run=lambda *a, **k: _proc())
    assert report["total_reexecuted"] == 0
    assert report["total_commands"] == 2
    assert any(line == "proof/x.json: 0 of 2 commands re-executed" for line in report["lines"])
    assert not any("all verified" in line.lower() for line in report["lines"])
    assert report["failures"] == []


def test_no_records_reports_0_of_0_not_all_verified():
    report = lwb_check_proof.reexecute_verifiable_commands([], run=lambda *a, **k: _proc())
    assert report["total_commands"] == 0
    assert report["total_reexecuted"] == 0
    assert any(line.startswith("TOTAL: 0 of 0") for line in report["lines"])
    assert not any("all verified" in line.lower() for line in report["lines"])


# --- Guard 4: exit codes ---------------------------------------------------


def test_exit_mismatch_fails_even_when_digest_matches():
    text = "same output"
    digest = _digest_for(text)
    records = [
        (
            "proof/x.json",
            _record([_cmd(["python", "scripts/lwb_check_prefix.py"], exit=0, sha256=digest)]),
        )
    ]
    report = lwb_check_proof.reexecute_verifiable_commands(
        records, run=lambda *a, **k: _proc(returncode=1, stdout=text)
    )
    assert report["total_reexecuted"] == 1
    assert len(report["failures"]) == 1
    assert "exit" in report["failures"][0]


def test_digest_mismatch_fails():
    records = [
        (
            "proof/x.json",
            _record([_cmd(["python", "scripts/lwb_check_prefix.py"], exit=0, sha256="b" * 64)]),
        )
    ]
    report = lwb_check_proof.reexecute_verifiable_commands(
        records, run=lambda *a, **k: _proc(returncode=0, stdout="different output entirely")
    )
    assert report["total_reexecuted"] == 1
    assert len(report["failures"]) == 1
    assert "digest" in report["failures"][0] or "sha256" in report["failures"][0]


def test_digest_and_exit_match_passes():
    text = "identical output"
    digest = _digest_for(text)
    records = [
        (
            "proof/x.json",
            _record([_cmd(["python", "scripts/lwb_check_prefix.py"], exit=0, sha256=digest)]),
        )
    ]
    report = lwb_check_proof.reexecute_verifiable_commands(
        records, run=lambda *a, **k: _proc(returncode=0, stdout=text)
    )
    assert report["total_reexecuted"] == 1
    assert report["failures"] == []
    assert any("PASS" in line for line in report["lines"])


def test_summary_line_carries_both_numbers():
    records = [
        (
            "proof/x.json",
            _record(
                [
                    _cmd(["python", "scripts/lwb_check_prefix.py"], exit=0, sha256=_digest_for("ok")),
                    _cmd(["python", "-m", "pytest"], verifiable=False, verifiable_reason="nondeterministic-output"),
                ]
            ),
        )
    ]
    report = lwb_check_proof.reexecute_verifiable_commands(
        records, run=lambda *a, **k: _proc(returncode=0, stdout="ok")
    )
    total_line = next(line for line in report["lines"] if line.startswith("TOTAL:"))
    assert "1 of 2" in total_line


# --- CLI wiring -------------------------------------------------------------


def test_main_reexecute_requires_explicit_flag(monkeypatch, capsys):
    """Without --reexecute, ordinary invocation never re-executes anything
    -- there is no env var that turns this mode on."""
    monkeypatch.setattr(sys, "argv", ["lwb_check_proof.py"])
    rc = lwb_check_proof.main()
    out = capsys.readouterr().out
    assert "re-executed" not in out
    assert rc in (0, 1)


def test_main_reexecute_real_command_integration(monkeypatch, tmp_path, capsys):
    """A true end-to-end pass: a real subprocess is launched and its digest
    compared, against a hand-built proof/ directory in a tmp repo root."""
    proof_dir = tmp_path / "proof"
    proof_dir.mkdir()
    text_out = subprocess.run(
        [sys.executable, "-c", "print('hello-reexecute')"],
        capture_output=True,
        encoding="utf-8",
    )
    digest = hashlib.sha256(
        lwb_sanitise.sanitise(text_out.stdout + text_out.stderr).encode("utf-8")
    ).hexdigest()
    record = _record(
        [_cmd([sys.executable, "-c", "print('hello-reexecute')"], exit=0, sha256=digest)]
    )
    (proof_dir / "1.json").write_text(__import__("json").dumps(record), encoding="utf-8")

    monkeypatch.setattr(lwb_check_proof, "PROOF_DIR", proof_dir)
    monkeypatch.setattr(sys, "argv", ["lwb_check_proof.py", "--reexecute"])
    rc = lwb_check_proof.main()
    out = capsys.readouterr().out
    assert "1 of 1" in out
    assert rc == 0

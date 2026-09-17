"""Unit tests for scripts/lwb_handoff.py. No network; git/gh calls are
monkeypatched out where a test needs cmd_check/cmd_write end to end."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "lwb_handoff.py"

_spec = importlib.util.spec_from_file_location("lwb_handoff", SCRIPT_PATH)
lwb_handoff = importlib.util.module_from_spec(_spec)
sys.modules["lwb_handoff"] = lwb_handoff
_spec.loader.exec_module(lwb_handoff)


def _valid_text(begin: str = lwb_handoff.BEGIN_MARKER, end: str = lwb_handoff.END_MARKER) -> str:
    return (
        "# HANDOFF\n\n"
        "## Start of session\n- [ ] read this\n\n"
        "## In flight\n1. do the thing\n\n"
        f"{begin}\nGenerated: 2026-09-17 00:00 UTC\nmain SHA: deadbeef\n\nOpen PRs:\n(none)\n\n{end}\n\n"
        "## Re-derive state\n```\ngit status\n```\n\n"
        "## Hard rules\n- stdlib only\n\n"
        "## Traps\n- none yet\n"
    )


def test_valid_text_passes():
    assert lwb_handoff._validate(_valid_text()) == []


def test_missing_section_fails():
    text = _valid_text().replace("## Traps\n", "")
    errors = lwb_handoff._validate(text)
    assert any("Traps" in e for e in errors)


def test_missing_begin_marker_fails():
    text = _valid_text().replace(lwb_handoff.BEGIN_MARKER, "")
    errors = lwb_handoff._validate(text)
    assert any("begin" in e.lower() for e in errors)


def test_duplicate_marker_fails():
    text = _valid_text() + f"\n{lwb_handoff.BEGIN_MARKER}\n{lwb_handoff.END_MARKER}\n"
    errors = lwb_handoff._validate(text)
    assert any("exactly one" in e for e in errors)


def test_markers_out_of_order_fails():
    text = _valid_text(begin=lwb_handoff.END_MARKER, end=lwb_handoff.BEGIN_MARKER)
    errors = lwb_handoff._validate(text)
    assert any("before begin" in e for e in errors)


def test_over_size_cap_fails():
    text = _valid_text() + ("x" * (lwb_handoff.SIZE_CAP_BYTES + 1))
    errors = lwb_handoff._validate(text)
    assert any("bytes" in e and "cap" in e for e in errors)


@pytest.mark.parametrize(
    "needle",
    ["C:\\Users\\someone\\repo", "/Users/someone/repo", "/home/someone/repo"],
)
def test_absolute_path_fails(needle):
    text = _valid_text() + f"\n{needle}\n"
    errors = lwb_handoff._validate(text)
    assert any("absolute path" in e for e in errors)


@pytest.mark.parametrize("needle", ["manny", "Ramos", "FOLLOWOZ", "leapware-cpt", "leapware-financial"])
def test_forbidden_substring_fails(needle):
    text = _valid_text() + f"\n{needle}\n"
    errors = lwb_handoff._validate(text)
    assert any("forbidden substring" in e for e in errors)


def test_cmd_check_missing_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(lwb_handoff, "HANDOFF_PATH", tmp_path / "HANDOFF.md")
    assert lwb_handoff.cmd_check() == 1
    assert "does not exist" in capsys.readouterr().err


def test_cmd_check_valid_file(tmp_path, monkeypatch, capsys):
    path = tmp_path / "HANDOFF.md"
    path.write_text(_valid_text(), encoding="utf-8")
    monkeypatch.setattr(lwb_handoff, "HANDOFF_PATH", path)
    assert lwb_handoff.cmd_check() == 0
    assert "OK" in capsys.readouterr().out


def test_cmd_check_invalid_file(tmp_path, monkeypatch, capsys):
    path = tmp_path / "HANDOFF.md"
    path.write_text(_valid_text().replace("## Traps\n", ""), encoding="utf-8")
    monkeypatch.setattr(lwb_handoff, "HANDOFF_PATH", path)
    assert lwb_handoff.cmd_check() == 1
    assert "FAIL" in capsys.readouterr().err


def test_cmd_write_regenerates_only_the_block(tmp_path, monkeypatch):
    path = tmp_path / "HANDOFF.md"
    path.write_text(_valid_text(), encoding="utf-8")
    monkeypatch.setattr(lwb_handoff, "HANDOFF_PATH", path)
    monkeypatch.setattr(lwb_handoff, "_run_git", lambda args: "cafef00d")
    monkeypatch.setattr(lwb_handoff, "_run_gh", lambda args: "")

    before = path.read_text(encoding="utf-8")
    prose_before = before.split(lwb_handoff.BEGIN_MARKER)[0]

    assert lwb_handoff.cmd_write() == 0

    after = path.read_text(encoding="utf-8")
    prose_after = after.split(lwb_handoff.BEGIN_MARKER)[0]
    assert prose_before == prose_after
    assert "cafef00d" in after
    assert after.count(lwb_handoff.BEGIN_MARKER) == 1
    assert after.count(lwb_handoff.END_MARKER) == 1


def test_cmd_write_requires_existing_markers(tmp_path, monkeypatch, capsys):
    path = tmp_path / "HANDOFF.md"
    path.write_text(_valid_text().replace(lwb_handoff.BEGIN_MARKER, ""), encoding="utf-8")
    monkeypatch.setattr(lwb_handoff, "HANDOFF_PATH", path)
    assert lwb_handoff.cmd_write() == 1
    assert "must already contain" in capsys.readouterr().err


def test_cmd_write_records_cli_and_session(tmp_path, monkeypatch):
    path = tmp_path / "HANDOFF.md"
    path.write_text(_valid_text(), encoding="utf-8")
    monkeypatch.setattr(lwb_handoff, "HANDOFF_PATH", path)
    monkeypatch.setattr(lwb_handoff, "PROOF_DIR", tmp_path / "no-such-proof-dir")
    monkeypatch.setattr(lwb_handoff, "_run_git", lambda args: "cafef00d")
    monkeypatch.setattr(lwb_handoff, "_run_gh", lambda args: "")

    assert lwb_handoff.cmd_write(cli="claude", session="sess-123") == 0

    after = path.read_text(encoding="utf-8")
    assert "CLI: claude" in after
    assert "Session: sess-123" in after


def test_cmd_write_defaults_cli_and_session_to_unknown(tmp_path, monkeypatch):
    path = tmp_path / "HANDOFF.md"
    path.write_text(_valid_text(), encoding="utf-8")
    monkeypatch.setattr(lwb_handoff, "HANDOFF_PATH", path)
    monkeypatch.setattr(lwb_handoff, "PROOF_DIR", tmp_path / "no-such-proof-dir")
    monkeypatch.setattr(lwb_handoff, "_run_git", lambda args: "cafef00d")
    monkeypatch.setattr(lwb_handoff, "_run_gh", lambda args: "")

    assert lwb_handoff.cmd_write() == 0

    after = path.read_text(encoding="utf-8")
    assert "CLI: unknown" in after
    assert "Session: unknown" in after


def test_cmd_write_lists_deliverable_proof_state(tmp_path, monkeypatch):
    path = tmp_path / "HANDOFF.md"
    path.write_text(_valid_text(), encoding="utf-8")
    proof_dir = tmp_path / "proof"
    proof_dir.mkdir()
    (proof_dir / "example.json").write_text(
        '{"deliverable": "example", "author": "a", "checked_by": "b", '
        '"commit": "abc1234", "commands": [], "mutations": [], "unproven": []}',
        encoding="utf-8",
    )
    monkeypatch.setattr(lwb_handoff, "HANDOFF_PATH", path)
    monkeypatch.setattr(lwb_handoff, "PROOF_DIR", proof_dir)
    monkeypatch.setattr(lwb_handoff, "_run_git", lambda args: "cafef00d")
    monkeypatch.setattr(lwb_handoff, "_run_gh", lambda args: "")

    assert lwb_handoff.cmd_write() == 0

    after = path.read_text(encoding="utf-8")
    assert "example: PROVEN (commit abc1234)" in after


def test_cmd_write_reports_no_proof_records_yet(tmp_path, monkeypatch):
    path = tmp_path / "HANDOFF.md"
    path.write_text(_valid_text(), encoding="utf-8")
    proof_dir = tmp_path / "empty-proof"
    proof_dir.mkdir()
    monkeypatch.setattr(lwb_handoff, "HANDOFF_PATH", path)
    monkeypatch.setattr(lwb_handoff, "PROOF_DIR", proof_dir)
    monkeypatch.setattr(lwb_handoff, "_run_git", lambda args: "cafef00d")
    monkeypatch.setattr(lwb_handoff, "_run_gh", lambda args: "")

    assert lwb_handoff.cmd_write() == 0

    after = path.read_text(encoding="utf-8")
    assert "(none yet)" in after


def test_real_handoff_md_passes_check():
    """The repo's own HANDOFF.md must pass --check (guards drift)."""
    monkeypatch_path = REPO_ROOT / "HANDOFF.md"
    text = monkeypatch_path.read_text(encoding="utf-8")
    assert lwb_handoff._validate(text) == []

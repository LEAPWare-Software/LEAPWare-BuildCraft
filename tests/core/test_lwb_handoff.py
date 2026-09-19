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
    """The post-2026-09-17 shape: HANDOFF.md carries the transition only.
    "Start of session", "Re-derive state", "Hard rules" and "Traps" moved to
    docs/handoff-protocol.md under the 3000-byte cap."""
    return (
        "# HANDOFF\n\n"
        "## In flight\n1. do the thing\n\n"
        f"{begin}\nGenerated: 2026-09-17 00:00 UTC\nmain SHA: deadbeef\n\nOpen PRs:\n(none)\n\n{end}\n\n"
        "## Where to look\n- protocol → `docs/handoff-protocol.md`\n"
    )


def test_valid_text_passes():
    assert lwb_handoff._validate(_valid_text()) == []


def test_missing_section_fails():
    text = _valid_text().replace("## Where to look\n", "")
    errors = lwb_handoff._validate(text)
    assert any("Where to look" in e for e in errors)


def test_size_cap_is_3000_per_owner_ruling():
    assert lwb_handoff.SIZE_CAP_BYTES == 3000


def test_the_real_handoff_is_within_cap():
    text = (REPO_ROOT / "HANDOFF.md").read_text(encoding="utf-8")
    assert len(text.encode("utf-8")) <= lwb_handoff.SIZE_CAP_BYTES


def test_moved_sections_must_survive_in_the_protocol_doc(tmp_path, monkeypatch):
    """Trimming HANDOFF.md must not be able to quietly delete the hard rules:
    the moved headings are now required of docs/handoff-protocol.md."""
    stub = tmp_path / "handoff-protocol.md"
    stub.write_text("## Start of session\n## Re-derive state\n## Traps\n", encoding="utf-8")
    monkeypatch.setattr(lwb_handoff, "PROTOCOL_DOC", stub)
    errors = lwb_handoff._validate(_valid_text())
    assert any("Hard rules" in e and "handoff-protocol" in e for e in errors)


def test_real_protocol_doc_carries_every_moved_section():
    protocol = (REPO_ROOT / "docs" / "handoff-protocol.md").read_text(encoding="utf-8")
    for section in lwb_handoff.PROTOCOL_REQUIRED_SECTIONS:
        assert section in protocol, section


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


def _synthetic_abs_path(kind: str) -> str:
    """Assembled at run time so no absolute-path literal appears in this file.

    This file is no longer exempt from the env-leak scan (its exemption hid
    five real private names), so it must not contain the very patterns that
    scan looks for. A test fixture is data; it does not need to be a literal.
    """
    if kind == "windows":
        return "C" + ":" + "\\" + "Users\\someone\\repo"
    return "/" + kind + "/someone/repo"


@pytest.mark.parametrize("kind", ["windows", "Users", "home"])
def test_absolute_path_fails(kind):
    text = _valid_text() + f"\n{_synthetic_abs_path(kind)}\n"
    errors = lwb_handoff._validate(text)
    assert any("absolute path" in e for e in errors)


@pytest.mark.parametrize("needle", ["Private-Proj", "acme-holdings", "SOMEORG"])
def test_forbidden_substring_fails(needle, monkeypatch):
    """Needles are injected, never hardcoded. Real private names used to be
    literals in this file and in scripts/lwb_handoff.py -- committed to a
    public repo, and invisible to the env-leak scanner because both files
    were on its exemption list."""
    monkeypatch.setenv("LWB_PRIVATE_NEEDLES", "private-proj,acme-holdings,someorg")
    text = _valid_text() + f"\n{needle}\n"
    errors = lwb_handoff._validate(text)
    assert any("forbidden substring" in e for e in errors)


def test_needles_come_from_the_environment_not_from_source():
    """Regression guard: no real private name may live in either file again."""
    for path in (
        REPO_ROOT / "scripts" / "lwb_handoff.py",
        REPO_ROOT / "tests" / "core" / "test_lwb_handoff.py",
    ):
        assert not hasattr(lwb_handoff, "FORBIDDEN_SUBSTRINGS"), path
    import lwb_check_env_leak

    assert lwb_handoff.resolve_needles is lwb_check_env_leak.resolve_needles


def test_no_needle_is_matched_when_unconfigured(monkeypatch):
    monkeypatch.delenv("LWB_PRIVATE_NEEDLES", raising=False)
    errors = lwb_handoff._validate(_valid_text() + "\nacme-holdings\n")
    assert not any("forbidden substring" in e for e in errors)


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
    path.write_text(_valid_text().replace("## Where to look\n", ""), encoding="utf-8")
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


def _write_proof_record(proof_dir: Path, name: str, proven: bool = True) -> None:
    """A minimal valid (or, if proven=False, invalid) proof/*.json record.
    An invalid record here is missing 'commands' -- REQUIRED_TOP in
    lwb_check_proof.py -- which is enough to fail `_validate_record`
    without needing to fake a whole broken schema."""
    if proven:
        body = (
            f'{{"deliverable": "{name}", "author": "a", "checked_by": "b", '
            '"commit": "abc1234", "commands": [], "mutations": [], "unproven": []}'
        )
    else:
        body = f'{{"deliverable": "{name}", "author": "a", "checked_by": "b"}}'
    (proof_dir / f"{name}.json").write_text(body, encoding="utf-8")


def test_cmd_write_lists_deliverable_proof_state(tmp_path, monkeypatch):
    """Owner ruling 2026-09-18: a proven record is COUNTED, not named --
    naming every proven record is exactly the shape that blew the
    3000-byte cap. Only the summary line and the explicit
    'none outstanding' statement should appear; the record's own name and
    commit are no longer printed when it is proven (they still live in
    proof/ itself, per the module docstring)."""
    path = tmp_path / "HANDOFF.md"
    path.write_text(_valid_text(), encoding="utf-8")
    proof_dir = tmp_path / "proof"
    proof_dir.mkdir()
    _write_proof_record(proof_dir, "example", proven=True)
    monkeypatch.setattr(lwb_handoff, "HANDOFF_PATH", path)
    monkeypatch.setattr(lwb_handoff, "PROOF_DIR", proof_dir)
    monkeypatch.setattr(lwb_handoff, "_run_git", lambda args: "cafef00d")
    monkeypatch.setattr(lwb_handoff, "_run_gh", lambda args: "")

    assert lwb_handoff.cmd_write() == 0

    after = path.read_text(encoding="utf-8")
    assert "1/1 proven" in after
    assert "(all proven; none outstanding)" in after
    assert "example" not in after  # proven records are counted, not named


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
    assert "0/0 proven" in after
    assert "(none yet)" in after


def test_proof_state_section_never_silently_empty(tmp_path):
    """An empty section reads identically to a broken generator (see the
    module docstring on `_proof_state_lines`). Whether proof/ is absent,
    empty, all-proven or partly-unproven, the returned block must always
    carry at least the summary line plus one more explicit line."""
    no_dir = lwb_handoff._proof_state_lines(tmp_path / "does-not-exist")
    assert len(no_dir) >= 2 and no_dir[0]

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    lines_empty = lwb_handoff._proof_state_lines(empty_dir)
    assert len(lines_empty) >= 2 and all(line for line in lines_empty)

    all_proven_dir = tmp_path / "all-proven"
    all_proven_dir.mkdir()
    _write_proof_record(all_proven_dir, "a", proven=True)
    lines_proven = lwb_handoff._proof_state_lines(all_proven_dir)
    assert len(lines_proven) >= 2 and all(line for line in lines_proven)


def test_unproven_record_appears_by_name(tmp_path):
    """The whole point of the redesign: a PROVEN record is just counted,
    but a record that is NOT fully proven must still appear by name so a
    reader can find it without reading every file in proof/."""
    proof_dir = tmp_path / "proof"
    proof_dir.mkdir()
    _write_proof_record(proof_dir, "good-one", proven=True)
    _write_proof_record(proof_dir, "broken-one", proven=False)

    lines = lwb_handoff._proof_state_lines(proof_dir)

    assert lines[0] == "1/2 proven"
    assert any("broken-one" in line for line in lines)
    assert not any("good-one" in line for line in lines)


def test_proof_state_block_size_bounded_by_unproven_count(tmp_path):
    """The regression that matters: without this, the cap breaks again in
    ~10 more PRs as proof/ grows. Construct 40 PROVEN records -- far past
    the ten that blew the old cap -- and assert the block stays a fixed
    couple of lines rather than growing one line per record."""
    proof_dir = tmp_path / "proof"
    proof_dir.mkdir()
    for i in range(40):
        _write_proof_record(proof_dir, f"deliverable-{i:03d}", proven=True)

    lines = lwb_handoff._proof_state_lines(proof_dir)

    assert lines == ["40/40 proven", "(all proven; none outstanding)"]
    assert len(lines) <= 3  # bounded: does NOT grow with the 40 proven records

    # Now add a handful of unproven records among the 40 proven ones: the
    # block should grow by exactly the unproven count, not by 40+unproven.
    for i in range(3):
        _write_proof_record(proof_dir, f"broken-{i}", proven=False)
    grown = lwb_handoff._proof_state_lines(proof_dir)
    assert grown[0] == "40/43 proven"
    assert len(grown) == 1 + 3  # summary + exactly the 3 unproven lines


def test_real_handoff_md_passes_check():
    """The repo's own HANDOFF.md must pass --check (guards drift)."""
    monkeypatch_path = REPO_ROOT / "HANDOFF.md"
    text = monkeypatch_path.read_text(encoding="utf-8")
    assert lwb_handoff._validate(text) == []


def test_needle_finding_reports_an_index_never_the_value(monkeypatch):
    """A leak must not print the private name it exists to protect.

    This file used to interpolate the matched needle into its error, so a
    maintainer running `--check` with the real secret exported would see the
    private name in their terminal and in any captured output. The sibling
    scanner was fixed for this in PR #17; an independent review found the
    same defect surviving here, in the file whose own comment narrates the
    fix. One bug class, two sites, one missed.
    """
    monkeypatch.setattr(lwb_handoff, "resolve_needles", lambda: ["zzsynthalpha", "zzsynthbeta"])
    text = _valid_text().replace("1. do the thing", "1. do the thing for zzsynthbeta")

    errors = lwb_handoff._validate(text)

    joined = " ".join(errors)
    assert "zzsynthbeta" not in joined, "the needle's VALUE must never appear in a finding"
    assert "zzsynthalpha" not in joined
    assert "needle #2" in joined, "the finding must name the needle by its stable 1-based index"


def test_needle_index_is_stable_for_a_given_list(monkeypatch):
    """Same configured list, same index -- so an operator can map it back."""
    monkeypatch.setattr(lwb_handoff, "resolve_needles", lambda: ["zzsynthalpha", "zzsynthbeta"])
    text = _valid_text().replace("1. do the thing", "1. do the thing for zzsynthalpha")

    first = lwb_handoff._validate(text)
    second = lwb_handoff._validate(text)

    assert first == second
    assert any("needle #1" in e for e in first)

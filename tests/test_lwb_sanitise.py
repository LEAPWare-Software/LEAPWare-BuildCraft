"""Tests for scripts/lwb_sanitise.py.

The sanitiser used to be a throwaway script every session hand-wrote (and
deleted) per docs/maintainers/session-protocol.md. Two different sessions
wrote two different rule sets -- proof records 7-13 replaced `<repo>`,
`<home>` and `<path>`; 15-19 replaced only `<repo>` and `<home>` -- which
makes every historical digest unverifiable by construction: nobody, not
even the record's own author, can re-derive it. This module is the fix:
one committed, versioned function.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lwb_sanitise  # noqa: E402


def test_replaces_repo_root_with_placeholder():
    repo = str(REPO_ROOT)
    text = f"error in {repo}\\scripts\\lwb_build.py"
    out = lwb_sanitise.sanitise(text, repo_root=repo, home=str(Path.home()))
    assert "<repo>" in out
    assert repo not in out


def test_replaces_home_with_placeholder():
    home = str(Path.home())
    text = f"config at {home}/.claude/settings.json"
    out = lwb_sanitise.sanitise(text, repo_root=str(REPO_ROOT), home=home)
    assert "<home>" in out
    assert home not in out


def test_replaces_other_absolute_paths_with_generic_placeholder():
    text = "leaked C:\\Work\\someoneelse\\stuff\\file.txt"
    out = lwb_sanitise.sanitise(text, repo_root=str(REPO_ROOT), home=str(Path.home()))
    assert "<path>" in out
    assert "someoneelse" not in out


def test_repo_root_takes_precedence_over_generic_path_rule():
    repo = str(REPO_ROOT)
    text = f"see {repo}\\HANDOFF.md"
    out = lwb_sanitise.sanitise(text, repo_root=repo, home=str(Path.home()))
    assert out.count("<repo>") == 1
    assert "<path>" not in out


def test_home_takes_precedence_over_generic_path_rule():
    home = str(Path.home())
    text = f"see {home}\\HANDOFF.md"
    out = lwb_sanitise.sanitise(text, repo_root=str(REPO_ROOT), home=home)
    assert out.count("<home>") == 1
    assert "<path>" not in out


def test_windows_and_posix_separators_sanitise_to_identical_bytes():
    """Same logical path, two separator styles -- the plan requires the
    OUTPUT be platform-independent: Windows and ubuntu must produce
    identical bytes for the same logical content."""
    repo = str(REPO_ROOT)
    repo_posix = repo.replace("\\", "/")
    text_win = f"FAIL at {repo}\\scripts\\lwb_build.py:42"
    text_posix = f"FAIL at {repo_posix}/scripts/lwb_build.py:42"
    out_win = lwb_sanitise.sanitise(text_win, repo_root=repo, home=str(Path.home()))
    out_posix = lwb_sanitise.sanitise(text_posix, repo_root=repo, home=str(Path.home()))
    assert out_win == out_posix


def test_deterministic_across_repeated_calls():
    repo = str(REPO_ROOT)
    text = f"{repo}\\a {repo}/b C:\\Work\\other\\c"
    out1 = lwb_sanitise.sanitise(text, repo_root=repo, home=str(Path.home()))
    out2 = lwb_sanitise.sanitise(text, repo_root=repo, home=str(Path.home()))
    assert out1 == out2


def test_text_with_no_absolute_paths_is_unchanged_besides_separators():
    text = "lwb-proof check passed (11 record(s))"
    out = lwb_sanitise.sanitise(text, repo_root=str(REPO_ROOT), home=str(Path.home()))
    assert out == text


def test_sanitiser_version_constant_exists_and_is_a_string():
    assert isinstance(lwb_sanitise.SANITISER_VERSION, str)
    assert lwb_sanitise.SANITISER_VERSION


def test_sibling_directory_sharing_repo_prefix_is_not_corrupted():
    """The load-bearing bug found by adversarial review: a naive
    `.replace(repo_norm, "<repo>")` has no boundary check, so
    `.../proj2/file.py` (a SIBLING of `.../proj`, not the repo itself)
    gets mangled into `.../<repo>2/file.py` -- a path fragment leaks into
    the digest input and an unrelated path is corrupted."""
    repo = "C:\\Work\\alice\\proj"
    text = "see C:/Work/alice/proj2/file.py and C:/Work/alice/proj/file.py"
    out = lwb_sanitise.sanitise(text, repo_root=repo, home="C:\\Work\\alice\\home-unused")
    assert "<repo>2" not in out
    assert out.count("<repo>") == 1
    # The sibling must not be corrupted by the repo-prefix rule; it still
    # gets sanitised, but by the generic <path> rule, not mangled into
    # "<repo>2".
    assert "proj2" not in out
    assert out == "see <path> and <repo>/file.py"


def test_repo_prefix_exact_match_is_replaced():
    repo = "C:\\Work\\alice\\proj"
    text = "C:/Work/alice/proj"
    out = lwb_sanitise.sanitise(text, repo_root=repo, home="C:\\Work\\alice\\home-unused")
    assert out == "<repo>"


def test_repo_prefix_followed_by_separator_is_replaced():
    repo = "C:\\Work\\alice\\proj"
    text = "C:/Work/alice/proj/file.py"
    out = lwb_sanitise.sanitise(text, repo_root=repo, home="C:\\Work\\alice\\home-unused")
    assert out == "<repo>/file.py"


def test_repo_prefix_at_end_of_string_is_replaced():
    repo = "C:\\Work\\alice\\proj"
    text = "cloned into C:/Work/alice/proj"
    out = lwb_sanitise.sanitise(text, repo_root=repo, home="C:\\Work\\alice\\home-unused")
    assert out == "cloned into <repo>"


def test_sibling_directory_sharing_home_prefix_is_not_corrupted():
    home = "C:\\Work\\alice"
    text = "see C:/Work/alice2/file.py and C:/Work/alice/file.py"
    out = lwb_sanitise.sanitise(text, repo_root="C:\\Work\\alice\\repo-unused", home=home)
    assert "<home>2" not in out
    assert out.count("<home>") == 1
    assert "alice2" not in out
    assert out == "see <path> and <home>/file.py"


def test_repo_and_home_case_insensitive_match_produces_identical_bytes():
    """The next PR's CI re-execution depends on identical bytes for the
    same logical content -- if `C:\\Work\\...` sanitises to `<repo>` but
    `c:\\work\\...` (same directory, different case) falls through to the
    generic `<path>` rule, the guarantee breaks. Repo/home prefixes match
    case-insensitively -- Windows paths are case-insensitive on the
    filesystem, so the two spellings name the same directory."""
    repo = "C:\\Work\\Alice\\Proj"
    text_upper = "FAIL at C:\\Work\\Alice\\Proj\\scripts\\lwb_build.py:42"
    text_lower = "FAIL at c:\\work\\alice\\proj\\scripts\\lwb_build.py:42"
    out_upper = lwb_sanitise.sanitise(text_upper, repo_root=repo, home="C:\\Work\\Alice\\home-unused")
    out_lower = lwb_sanitise.sanitise(text_lower, repo_root=repo, home="C:\\Work\\Alice\\home-unused")
    assert out_upper == out_lower
    assert "<path>" not in out_upper
    assert "<path>" not in out_lower


def test_default_repo_root_and_home_are_used_when_omitted():
    """Callers in this repo shouldn't have to pass repo_root/home explicitly
    every time -- sanitise() defaults them to this repo and the real home."""
    home = str(Path.home())
    text = f"config at {home}/.claude/settings.json"
    out = lwb_sanitise.sanitise(text)
    assert "<home>" in out

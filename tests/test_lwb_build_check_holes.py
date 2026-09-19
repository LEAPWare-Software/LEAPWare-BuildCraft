"""Two holes in `scripts/lwb_build.py --check`, both found by the independent
reviewer of PR #25 and both reproduced before being fixed.

WHY THESE MATTER MORE THAN THEY LOOK. PR #25 reclassifies
`plugins/*/lwb/vendor/` from the agent's own lane to `shared`, and its whole
argument for why that is safe is that vendor output is only ever BUILD
OUTPUT, verified by `--check`. That argument is worth exactly what this
check is worth. The reviewer said so directly, then demonstrated two ways
the check could be satisfied by a tree that is not what the build produced.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lwb_build  # noqa: E402


def test_a_file_replaced_by_a_same_named_directory_is_drift(tmp_path):
    """`dircmp` files a name that is a file on one side and a directory on
    the other under `common_funny` -- neither `left_only`, `right_only` nor
    `diff_files` -- and `_trees_equal` never looked at it. So replacing a
    vendored MODULE with a DIRECTORY of the same name passed the drift
    check. Reproduced before the fix: `_trees_equal` returned True.

    It can hide content rather than run it, because the core imports rules
    by name and nothing scans the directory. But a check whose entire job is
    "the vendor tree is exactly what the build produced" must not answer
    True here.
    """
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    (src / "rules").mkdir(parents=True)
    (dst / "rules").mkdir(parents=True)
    (src / "rules" / "lwb_version.py").write_text("reviewed source\n", encoding="utf-8")

    masquerade = dst / "rules" / "lwb_version.py"
    masquerade.mkdir()
    (masquerade / "payload.py").write_text("payload\n", encoding="utf-8")

    assert lwb_build._trees_equal(src, dst) is False


def test_identical_trees_stay_equal_and_extra_files_still_drift(tmp_path):
    """Guard on the guard above.

    Without this, the previous test would pass against a `_trees_equal` that
    simply returned False for everything -- a "fix" that breaks the build
    check entirely.
    """
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    (src / "rules").mkdir(parents=True)
    (dst / "rules").mkdir(parents=True)
    (src / "rules" / "lwb_version.py").write_text("reviewed source\n", encoding="utf-8")
    (dst / "rules" / "lwb_version.py").write_text("reviewed source\n", encoding="utf-8")
    assert lwb_build._trees_equal(src, dst) is True

    (dst / "rules" / "evil.py").write_text("x\n", encoding="utf-8")
    assert lwb_build._trees_equal(src, dst) is False


def test_a_tracked_file_the_build_does_not_produce_is_reported(tmp_path, monkeypatch):
    """The bytecode hole, which is NOT drift and so was invisible to drift.

    `_trees_equal` ignores `__pycache__/` and `*.pyc` deliberately: they are
    regenerated locally and are not drift, and `.gitignore` excludes them.
    But `git add -f` commits one anyway, and a committed `.pyc` under
    `plugins/*/lwb/vendor/` SHIPS IN THE PLUGIN and is what the interpreter
    actually loads -- while the `.py` beside it, the file a reviewer reads,
    never runs. The reviewer reproduced exactly that: an unchecked-hash
    `.pyc` printed `payload` while its source said `reviewed source`, and
    the diff a human sees is a binary blob.

    The rule enforced here is deliberately NOT "no `.pyc` ships". It is
    "nothing ships from vendor/ that the build did not write" -- bytecode is
    merely the instance that prompted it.
    """
    vendor = tmp_path / "vendor"
    staging = tmp_path / "staging"
    (vendor / "rules").mkdir(parents=True)
    (staging / "rules").mkdir(parents=True)
    (staging / "rules" / "lwb_version.py").write_text("x\n", encoding="utf-8")
    (vendor / "rules" / "lwb_version.py").write_text("x\n", encoding="utf-8")
    stowaway = vendor / "rules" / "__pycache__" / "lwb_version.cpython-312.pyc"
    stowaway.parent.mkdir()
    stowaway.write_bytes(bytes([0]) + b"PAYLOAD")

    class _Result:
        returncode = 0
        stdout = chr(0).join(
            [
                "vendor/rules/lwb_version.py",
                "vendor/rules/__pycache__/lwb_version.cpython-312.pyc",
            ]
        )

    monkeypatch.setattr(lwb_build, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(lwb_build.subprocess, "run", lambda *a, **k: _Result())

    found = lwb_build.tracked_files_the_build_does_not_produce(vendor, staging)
    assert found == ["vendor/rules/__pycache__/lwb_version.cpython-312.pyc"], found


def test_no_stowaways_when_every_tracked_file_is_built(tmp_path, monkeypatch):
    """Guard on that guard: it must not flag files the build DID produce, or
    `--check` would fail on every clean tree and be turned off."""
    vendor = tmp_path / "vendor"
    staging = tmp_path / "staging"
    (vendor / "rules").mkdir(parents=True)
    (staging / "rules").mkdir(parents=True)
    for root in (vendor, staging):
        (root / "rules" / "lwb_version.py").write_text("x\n", encoding="utf-8")

    class _Result:
        returncode = 0
        stdout = "vendor/rules/lwb_version.py"

    monkeypatch.setattr(lwb_build, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(lwb_build.subprocess, "run", lambda *a, **k: _Result())
    assert lwb_build.tracked_files_the_build_does_not_produce(vendor, staging) == []


def test_git_unavailable_reports_nothing_rather_than_inventing_an_answer(tmp_path, monkeypatch):
    """A non-zero `git ls-files` must not crash the build, and must not be
    dressed up as a positive finding. It returns an empty list; `main`
    decides how to report that state."""
    vendor = tmp_path / "vendor"
    staging = tmp_path / "staging"
    vendor.mkdir()
    staging.mkdir()

    class _Result:
        returncode = 128
        stdout = ""

    monkeypatch.setattr(lwb_build, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(lwb_build.subprocess, "run", lambda *a, **k: _Result())
    assert lwb_build.tracked_files_the_build_does_not_produce(vendor, staging) == []

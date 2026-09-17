"""Vendor trees must be committed, not gitignored, and exactly what the build
produces -- not merely non-empty.

A marketplace/plugin install pulls the repo from git with no build step run
afterward (scripts/lwb_build.py never executes on the install path), so
plugins/*/lwb/vendor/ must ship as real, tracked files that are byte-identical
to what scripts/lwb_build.py would write today. This test would have caught
#LWB-D0's first CI break (vendor/ gitignored, no tree for CI to check against)
*and* a narrower regression the first version of this test missed: untracking
a single vendored file (`git rm --cached` one file, leaving it on disk) left
`git ls-files` non-empty, so a truthiness check like `assert tracked` still
passed. This version asserts the *set* of git-tracked paths under each
vendor/ dir equals the *set* scripts/lwb_build.py would produce, one for one.
"""

from __future__ import annotations

import filecmp
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lwb_build  # noqa: E402

VENDOR_DIRS = [
    "plugins/claude/lwb/vendor",
    "plugins/codex/lwb/vendor",
]


def _tracked_files(relative_dir: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", relative_dir],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def _walk_files(root: Path) -> set[str]:
    # git always reports forward-slash paths (even on Windows); match that
    # so this set-equality check isn't a false failure on Windows CI.
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def test_vendor_trees_are_tracked_by_git():
    for vendor_dir in VENDOR_DIRS:
        tracked = _tracked_files(vendor_dir)
        assert tracked, (
            f"{vendor_dir} has no files tracked by git (git ls-files returned "
            f"nothing) -- vendor/ must be committed, not gitignored, or an "
            f"install from git ships with no vendor tree"
        )


def test_vendor_dirs_not_gitignored():
    for vendor_dir in VENDOR_DIRS:
        result = subprocess.run(
            ["git", "check-ignore", "-q", vendor_dir],
            cwd=REPO_ROOT,
        )
        assert result.returncode != 0, f"{vendor_dir} is gitignored"


def test_vendor_tracked_set_and_content_exactly_matches_build():
    """The strong version: git's tracked file *set* under vendor/, and every
    byte in it, must equal exactly what scripts/lwb_build.py would produce
    today -- not just "some files are tracked".

    Untracking one real file while leaving it on disk (`git rm --cached
    <file>`) is exactly the regression this catches: `git ls-files` then
    omits that path from the tracked set, which no longer equals the built
    set, so this test fails even though the file is still present on disk
    and a naive non-empty check would still pass.
    """
    with tempfile.TemporaryDirectory(prefix="lwb-build-test-") as tmp:
        tmp_root = Path(tmp)
        for host, vendor_dir in lwb_build.TARGETS:
            staging = lwb_build._build_one(host, vendor_dir, tmp_root)
            built_files = _walk_files(staging)

            rel_vendor_dir = str(vendor_dir.relative_to(REPO_ROOT)).replace("\\", "/")
            tracked_rel = {
                p[len(rel_vendor_dir) + 1 :]
                for p in _tracked_files(rel_vendor_dir)
                # git ls-files always uses forward slashes
                if p.startswith(rel_vendor_dir + "/")
            }

            assert tracked_rel == built_files, (
                f"{rel_vendor_dir}: git-tracked file set does not match what "
                f"scripts/lwb_build.py produces.\n"
                f"tracked only: {sorted(tracked_rel - built_files)}\n"
                f"built only:   {sorted(built_files - tracked_rel)}"
            )

            assert vendor_dir.is_dir(), f"{vendor_dir} missing on disk"
            comparison = filecmp.dircmp(staging, vendor_dir)
            mismatched = _diff_recursive(comparison)
            assert not mismatched, (
                f"{rel_vendor_dir}: committed content differs from "
                f"scripts/lwb_build.py's output: {mismatched} "
                f"(run scripts/lwb_build.py and commit the result)"
            )


def _diff_recursive(comparison: filecmp.dircmp) -> list[str]:
    problems = list(comparison.left_only) + list(comparison.right_only) + list(comparison.diff_files)
    for sub in comparison.subdirs.values():
        problems.extend(_diff_recursive(sub))
    return problems


if __name__ == "__main__":
    sys.exit(0)

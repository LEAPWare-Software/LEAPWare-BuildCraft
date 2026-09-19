#!/usr/bin/env python3
"""Vendor `core/` and the matching `adapters/<host>/` into each plugin's vendor/.

Plugins cannot import from outside their own install directory at runtime
(a Claude Code plugin is distributed as its own subtree; the same is true
for a Codex plugin package). So `lwb_core` and the relevant adapter are
copied — not symlinked, copied, since a symlink does not survive a zip
release artifact — into `plugins/claude/lwb/vendor/` and
`plugins/codex/lwb/vendor/` respectively. This script is the ONLY place
that copy happens; nobody should hand-edit a vendor/ directory.

Usage:
    python scripts/lwb_build.py            # write/refresh both vendor/ trees
    python scripts/lwb_build.py --check    # exit 1 if a vendor/ tree is stale

Stdlib only.
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE_DIR = REPO_ROOT / "core"
ADAPTERS_DIR = REPO_ROOT / "adapters"

# (host adapter subpackage name, plugin vendor dir)
TARGETS = [
    ("claude", REPO_ROOT / "plugins" / "claude" / "lwb" / "vendor"),
    ("codex", REPO_ROOT / "plugins" / "codex" / "lwb" / "vendor"),
]

_IGNORE_PATTERNS = shutil.ignore_patterns("__pycache__", "*.pyc")


def _build_one(host: str, vendor_dir: Path, tmp_root: Path) -> Path:
    """Assemble the vendor tree for `host` under `tmp_root`. Returns its path."""
    staging = tmp_root / host
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    shutil.copytree(CORE_DIR / "lwb_core", staging / "lwb_core", ignore=_IGNORE_PATTERNS)

    policy_dst = staging / "policy"
    policy_dst.mkdir()
    shutil.copy2(CORE_DIR / "policy" / "schema.json", policy_dst / "schema.json")
    shutil.copy2(CORE_DIR / "policy" / "default.json", policy_dst / "default.json")

    adapters_dst = staging / "adapters"
    adapters_dst.mkdir()
    shutil.copy2(ADAPTERS_DIR / "__init__.py", adapters_dst / "__init__.py")
    shutil.copytree(
        ADAPTERS_DIR / host, adapters_dst / host, ignore=_IGNORE_PATTERNS
    )

    return staging


_BUILD_NOISE_DIRS = ("__pycache__",)
_IGNORED_SUFFIXES = (".pyc", ".pyo")


def _is_build_noise(name: str) -> bool:
    """True for interpreter-generated files that are not build output.

    `_build_one` already excludes these when it copies (`_IGNORE_PATTERNS`),
    but the COMPARISON did not, and that asymmetry made `--check` report
    drift that no rebuild could ever fix. Importing anything under
    `vendor/` writes bytecode beside it, and the test suite imports from
    vendor -- so running the tests poisoned the very check that guards
    them. A gate whose own prerequisites break it gets ignored, and this
    one was: the failure was carried for at least two PRs as "pre-existing,
    environment-dependent, not mine".

    Two narrow blind spots follow from this and are accepted deliberately,
    named here so they are a decision rather than an oversight: a directory
    literally called `__pycache__` holding real source is invisible, and a
    file named `*.pyc`/`*.pyo` holding real source is skipped. Both were
    demonstrated by an independent review. They are acceptable because these
    are interpreter-reserved names in a stdlib-only repo -- no legitimate
    vendored source carries them, and a text file named `.pyc` would not
    import as a module anyway.
    """
    return name in _BUILD_NOISE_DIRS or name.endswith(_IGNORED_SUFFIXES)


def _trees_equal(a: Path, b: Path) -> bool:
    """True iff every file under `a` and `b` matches, recursively, by content.

    Interpreter bytecode is ignored on both sides -- see `_is_build_noise`.
    """
    comparison = filecmp.dircmp(a, b, ignore=list(_BUILD_NOISE_DIRS))
    left_only = [n for n in comparison.left_only if not _is_build_noise(n)]
    right_only = [n for n in comparison.right_only if not _is_build_noise(n)]
    if left_only or right_only:
        return False

    # Compare CONTENT, not stat(). `dircmp.diff_files` is shallow: two files
    # with the same size and mtime are called equal without being read. A
    # hand-edit to a vendored file that happens to preserve its length --
    # `mode = "warn"` to `mode = "deny"`, a digit changed, a boolean flipped
    # -- was therefore invisible to this check, which exists precisely to
    # stop a hand-edited vendor tree from shipping. Found by a test written
    # to prove the bytecode exemption had not widened into blindness; the
    # exemption was fine, the comparison underneath it never worked.
    for name in comparison.common_files:
        if _is_build_noise(name):
            continue
        if not filecmp.cmp(a / name, b / name, shallow=False):
            return False
    # A NAME PRESENT ON BOTH SIDES AS DIFFERENT KINDS is not "common" in any
    # useful sense, and `dircmp` does not report it as a difference: it goes
    # into `common_funny` (one side a file, the other a directory, or a stat
    # that failed), which nothing here used to look at. So replacing a
    # vendored MODULE with a DIRECTORY of the same name passed this check --
    # reproduced: `lwb_core/rules/lwb_version.py` turned into a directory
    # holding `payload.py` gave `_trees_equal = True`. It could hide content
    # rather than run it, because the core imports rules by name and nothing
    # scans the directory, but a check whose job is "the vendor tree is
    # exactly what the build produced" must not answer True here.
    # `funny_files` is the same class for files that could not be compared at
    # all. Found by the independent reviewer of PR #25, which is the PR that
    # makes this check load-bearing for review policy.
    if comparison.common_funny or comparison.funny_files:
        return False

    for sub in comparison.common_dirs:
        if not _trees_equal(a / sub, b / sub):
            return False
    return True


def tracked_files_the_build_does_not_produce(vendor_dir: Path, staging: Path) -> list[str]:
    """git-TRACKED paths under `vendor_dir` that the build did not write.

    `_trees_equal` deliberately ignores interpreter bytecode, because it is
    regenerated locally and is not drift. But "ignored by the drift check"
    and "harmless" are different claims, and the gap between them is real:
    `.gitignore` excludes `__pycache__/` and `*.pyc`, yet `git add -f` can
    commit one anyway, and a committed `.pyc` under `plugins/*/lwb/vendor/`
    SHIPS IN THE PLUGIN and is what the interpreter actually loads -- while
    the `.py` beside it, the file a reviewer reads, is never executed. The
    reviewer of PR #25 reproduced exactly that in a scratch package: an
    unchecked-hash `.pyc` printed `payload` while its source said
    `reviewed source`, and the diff a human sees is a binary blob.

    PR #25 argues that vendor output is safe to classify as `shared`
    BECAUSE it is only ever build output, verified by `--check`. That
    argument is worth no more than this function makes it worth. So the
    check now also refuses any tracked file the build does not produce --
    bytecode included, and not by naming bytecode specifically, because the
    rule that matters is "nothing ships from here that the build did not
    write", not "no .pyc ships from here".
    """
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", str(vendor_dir)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        # Not a git repo, or git unavailable. Report nothing rather than
        # inventing a pass OR a fail -- but SAY SO. Returning an empty list
        # silently is indistinguishable from "checked, found nothing", which
        # is this repository's signature defect and the reason this file
        # exists. The reviewer of PR #25 flagged the silence specifically.
        print(
            f"NOTICE: stowaway check could not run for {vendor_dir} "
            f"(git ls-files exited {result.returncode}); NOTHING WAS CHECKED "
            f"-- this is not a pass"
        )
        return []

    # COMPARE AGAINST A SET OF PATHS, NOT `Path.exists()`. `exists()` asks the
    # FILESYSTEM, and on Windows and macOS that question is case-insensitive:
    # a tracked `rules/LWB_VERSION.PY` matched the built `rules/lwb_version.py`
    # and was reported as expected, so a stowaway differing only in case
    # shipped unnoticed on exactly the platform most contributors use. Found by
    # the independent reviewer of PR #25 and reproduced: the case variant
    # returned [] where it should have been reported. Git itself is
    # case-sensitive, so a set comparison on the relative path is the honest
    # test and behaves identically on every OS.
    produced = {
        path.relative_to(staging).as_posix()
        for path in staging.rglob("*")
        if path.is_file()
    }

    unexpected: list[str] = []
    for raw in result.stdout.split(chr(0)):
        rel = raw.strip()
        if not rel:
            continue
        tracked = REPO_ROOT / rel
        try:
            inside = tracked.relative_to(vendor_dir)
        except ValueError:
            continue
        if inside.as_posix() not in produced:
            unexpected.append(rel)
    return sorted(unexpected)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="exit 1 if any vendor/ tree is stale; write nothing"
    )
    args = parser.parse_args()

    import tempfile

    drift_found = False
    with tempfile.TemporaryDirectory(prefix="lwb-build-") as tmp:
        tmp_root = Path(tmp)
        for host, vendor_dir in TARGETS:
            staging = _build_one(host, vendor_dir, tmp_root)

            if args.check:
                if not vendor_dir.exists() or not _trees_equal(staging, vendor_dir):
                    print(f"DRIFT: {vendor_dir} does not match source (run scripts/lwb_build.py)")
                    drift_found = True
                else:
                    print(f"OK: {vendor_dir} matches source")

                # Separate from drift, and reported separately: a tracked
                # file the build does not produce is not "stale", it is
                # something that should not be in the shipped plugin at all.
                stowaways = tracked_files_the_build_does_not_produce(vendor_dir, staging)
                if stowaways:
                    print(
                        f"STOWAWAY: {len(stowaways)} git-tracked file(s) under {vendor_dir} "
                        f"are NOT produced by the build and would ship anyway:"
                    )
                    for rel in stowaways:
                        print(f"    {rel}")
                    drift_found = True
            else:
                if vendor_dir.exists():
                    shutil.rmtree(vendor_dir)
                shutil.copytree(staging, vendor_dir)
                print(f"wrote: {vendor_dir}")

    if args.check and drift_found:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

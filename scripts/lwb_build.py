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
    for sub in comparison.common_dirs:
        if not _trees_equal(a / sub, b / sub):
            return False
    return True


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

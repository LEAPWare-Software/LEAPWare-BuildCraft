#!/usr/bin/env python3
"""CI check `lwb-env-leak`: no local-environment or private-project leak.

SACRED: this repo's build/test/deploy must not depend on, or leak,
anything about the machine or private projects it was built on. Scans
every git-tracked, non-binary file for:

  - a Windows drive letter (`C:\\...`)
  - a POSIX home directory (`/Users/<name>` or `/home/<name>`)
  - a hard-coded interpreter invocation: `py -3`, `py -3.NN`, or an
    absolute path to a `python`/`python3`/`python.exe` binary
  - a private-project name leak: any configured needle, case-insensitive.
    The real needles are supplied out of band through the
    `LWB_PRIVATE_NEEDLES` environment variable and are NEVER committed —
    see "Needle sources" below. A run with no needles configured FAILS
    rather than passing quietly, because a green check that is scanning
    for nothing is worse than no check at all.

Allow-listed: this script's own pattern data (it necessarily names the
patterns it looks for) and files under `tests/**/fixtures/**` whose
filename or path makes clear they are synthetic (contain `fixture`).

A working-tree scan alone misses a leak that was committed and then
removed again -- it is still sitting in the branch's history, and a
`git clone` (or a marketplace pull) carries every commit, not just the
final tree. `--range <base>..<head>` additionally scans the ADDED lines
of every commit in that range (via `git log -p --unified=0`), so a leak
that was committed then reverted within the same PR is still caught, not
just the leaks visible in the final diff.

Needle sources
--------------
This repo is PUBLIC. A private project or org name written into this file
would be published permanently in its git history, leaking precisely what
this check exists to prevent. So the needles come from three places and
only one of them is committed:

1. `LWB_PRIVATE_NEEDLES` — the real private names, comma- or
   newline-separated, supplied out of band: a repository secret exported
   into the CI job, or a local environment variable on a maintainer's
   machine. Never committed, never printed in full.
2. `PUBLIC_NEEDLES` — deliberately empty. A name this repo publishes on
   purpose is not a leak, so needling it would only flag the prose that
   published it.
3. `SYNTHETIC_NEEDLE` — not a real name. It keeps this check and its
   tests meaningful in a fresh clone that has no secret configured.

So an unconfigured scan is looking only for a synthetic name that nothing
should ever contain: it cannot fail, and its passing means nothing. That
is why a missing source 1 is reported as a failure rather than a pass.

Usage:
    LWB_PRIVATE_NEEDLES="name-one,name-two" python scripts/lwb_check_env_leak.py
    python scripts/lwb_check_env_leak.py --range <base-sha>..<head-sha>

Stdlib only. Exits 0 and prints "lwb-env-leak check passed" on success;
otherwise prints every finding (file:line, or commit:file for a
history-only finding) and exits 1.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
SELF_PATH = Path(__file__).resolve()

DRIVE_LETTER = re.compile(r"\b[A-Za-z]:\\[\w][\w.\- ]")
POSIX_HOME = re.compile(r"(?<!\w)/(?:Users|home)/[\w.\-]+")
PY_DASH3 = re.compile(r"\bpy\s+-3(\.\d+)?\b")
HARDCODED_INTERPRETER = re.compile(
    r"(?:[A-Za-z]:\\|/)(?:[\w.\-]+[\\/])*python3?(?:\.exe)?(?=[\s\"'`]|$)"
)

# See "Needle sources" in the module docstring. Only sources 2 and 3 are
# committed; the real names arrive through NEEDLE_ENV_VAR at run time.
NEEDLE_ENV_VAR = "LWB_PRIVATE_NEEDLES"

# Deliberately EMPTY, and not merely unpopulated. A name this repo states on
# purpose -- `HANDOFF.md` and `README.md` both name the legacy repo -- is by
# definition not a leak, so making it a needle would only flag the prose that
# published it and wedge this check permanently red. The slot stays so the
# reasoning is recorded where the next maintainer will look for it.
PUBLIC_NEEDLES: tuple[str, ...] = ()

# Deliberately not a real name: proves the matcher works in a fresh clone.
SYNTHETIC_NEEDLE = "example-private-project"

# Needles are separated by commas or newlines. Not spaces (a real project
# name may contain one) and not `os.pathsep` (a `:` appears inside names
# like `org:team`).
_NEEDLE_SEPARATORS = re.compile(r"[,\n]")


def env_needles(env: Optional[Mapping[str, str]] = None) -> list[str]:
    """The needles supplied through NEEDLE_ENV_VAR, lowercased. May be empty."""
    source = os.environ if env is None else env
    raw = source.get(NEEDLE_ENV_VAR, "") or ""
    needles = []
    for chunk in _NEEDLE_SEPARATORS.split(raw):
        needle = chunk.strip().lower()
        if needle:
            needles.append(needle)
    return needles


def resolve_needles(env: Optional[Mapping[str, str]] = None) -> list[str]:
    """Every needle a scan should look for: env-supplied, public, synthetic."""
    return [*env_needles(env), *PUBLIC_NEEDLES, SYNTHETIC_NEEDLE]

_BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".zip", ".pyc"}


def _tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [REPO_ROOT / line for line in result.stdout.splitlines() if line]


# Files that necessarily carry this scanner's own pattern data (or, for a
# test file, synthetic needles that exercise it) rather than a real leak.
# scripts/lwb_handoff.py and tests/core/test_lwb_handoff.py were REMOVED from
# this set. They were exempt because they carried the needle literals, and the
# exemption meant this scanner could not see five real private names committed
# in plaintext to a public repo. The needles moved to LWB_PRIVATE_NEEDLES, so
# neither file carries pattern data any more and neither may be exempt again.
# An exemption is a blind spot: only this scanner's own source and the test
# holding synthetic needles qualify.
_PATTERN_DATA_EXEMPT = {
    "scripts/lwb_check_env_leak.py",
    "tests/test_lwb_check_env_leak.py",
}


def _is_exempt_posix(posix: str) -> bool:
    if posix in _PATTERN_DATA_EXEMPT:
        return True
    if "fixture" in posix.lower():
        return True
    return False


def _is_exempt(path: Path) -> bool:
    if path == SELF_PATH:
        return True
    return _is_exempt_posix(path.relative_to(REPO_ROOT).as_posix())


def _findings_for_line(
    rel: str,
    lineno: int,
    line: str,
    needles: Optional[list[str]] = None,
) -> list[str]:
    findings: list[str] = []
    if DRIVE_LETTER.search(line):
        findings.append(f"{rel}:{lineno}: Windows drive letter")
    if POSIX_HOME.search(line):
        findings.append(f"{rel}:{lineno}: POSIX home directory path")
    if PY_DASH3.search(line):
        findings.append(f"{rel}:{lineno}: hard-coded 'py -3' interpreter launch")
    if HARDCODED_INTERPRETER.search(line):
        findings.append(f"{rel}:{lineno}: absolute path to a python interpreter")
    lowered = line.lower()
    for needle in resolve_needles() if needles is None else needles:
        if needle in lowered:
            findings.append(f"{rel}:{lineno}: private-project name leak ('{needle}')")
    return findings


def check(needles: Optional[list[str]] = None) -> list[str]:
    needles = resolve_needles() if needles is None else needles
    findings: list[str] = []
    for path in _tracked_files():
        if not path.is_file() or path.suffix.lower() in _BINARY_SUFFIXES:
            continue
        if _is_exempt(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        for lineno, line in enumerate(text.splitlines(), start=1):
            findings.extend(_findings_for_line(rel, lineno, line, needles))
    return findings


# `git log -p` commit boundary; captures the full 40-hex sha.
_COMMIT_RE = re.compile(r"^commit ([0-9a-f]{40})")
# `+++ b/<path>` names the file a hunk's added lines belong to; `/dev/null`
# means the file was deleted in this commit (nothing was added to it).
_NEW_FILE_RE = re.compile(r"^\+\+\+ b/(.+)$")
# `@@ -<old-start>[,<old-count>] +<new-start>[,<new-count>] @@`
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def check_range(rev_range: str, needles: Optional[list[str]] = None) -> list[str]:
    """Scan the ADDED lines of every commit in `rev_range` (base..head).

    Uses `git log -p --unified=0` so each hunk contains only changed lines
    (no surrounding context to mis-scan) and walks it by hand: a commit
    that added a leak and a later commit in the same range that removed it
    again is still caught, because every commit's own diff is scanned, not
    just the net base..head diff.
    """
    needles = resolve_needles() if needles is None else needles
    result = subprocess.run(
        ["git", "log", "-p", "--unified=0", "--no-color", "--no-textconv", rev_range],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    findings: list[str] = []
    commit_sha = "?"
    rel = None
    next_new_line = None

    for raw_line in result.stdout.splitlines():
        commit_match = _COMMIT_RE.match(raw_line)
        if commit_match:
            commit_sha = commit_match.group(1)[:12]
            rel = None
            next_new_line = None
            continue

        new_file_match = _NEW_FILE_RE.match(raw_line)
        if new_file_match:
            candidate = new_file_match.group(1)
            rel = None if candidate == "dev/null" else PurePosixPath(candidate).as_posix()
            next_new_line = None
            continue

        hunk_match = _HUNK_RE.match(raw_line)
        if hunk_match:
            next_new_line = int(hunk_match.group(1))
            continue

        if rel is None or next_new_line is None or _is_exempt_posix(rel):
            continue

        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            content = raw_line[1:]
            for f in _findings_for_line(rel, next_new_line, content, needles):
                findings.append(f"{commit_sha} {f}")
            next_new_line += 1
        # Removed ("-") lines don't advance the new-file line counter, and
        # unified=0 emits no context lines, so nothing else to track here.

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--range",
        dest="rev_range",
        default=None,
        help="also scan added lines of every commit in base..head (e.g. origin/main..HEAD)",
    )
    args = parser.parse_args()

    supplied = env_needles()
    needles = resolve_needles()

    findings = check(needles)
    if args.rev_range:
        findings.extend(check_range(args.rev_range, needles))

    # An unarmed run is a failure in its own right: the scan still ran, but
    # it was only ever looking for the public and synthetic needles, so a
    # clean result proves nothing about this repo's real private names.
    unconfigured = not supplied
    if unconfigured:
        print(
            f"FAIL: lwb-env-leak UNCONFIGURED: {NEEDLE_ENV_VAR} is unset or empty, "
            "so no real private name was scanned for and a clean result proves "
            "nothing. Set it to a comma-separated list of the private repo, org, "
            "or personal-name fragments this repo must never mention."
        )

    if findings:
        for f in findings:
            print(f"FAIL: {f}")

    if findings or unconfigured:
        return 1
    print(f"lwb-env-leak check passed ({len(needles)} needles)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

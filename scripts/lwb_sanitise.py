#!/usr/bin/env python3
"""The proof-record sanitiser, as committed code.

`docs/maintainers/session-protocol.md` used to tell every session to write
a throwaway sanitiser script and delete it after. Two sessions wrote two
different rule sets -- proof records 7-13 replaced `<repo>`, `<home>` and
`<path>`; 15-19 replaced only `<repo>` and `<home>` -- so no two historical
records were sanitised by the same program, and every digest is
unverifiable by construction: nobody, including the record's own author,
can re-derive it. See `docs/maintainers/proof-of-completion-plan.md`,
open blocker 1.

This module is the fix: one documented function, versioned, that every
session and CI call the same way. `SANITISER_VERSION` is recorded on every
`commands[]` entry a proof record writes (see `scripts/lwb_record.py`), so
a digest is attributable to a known set of rules -- bump it whenever the
substitution rules themselves change, so an old digest is never silently
compared against new rules.

Directive 8 (SACRED) forbids this repo carrying anything about the machine
it was built on; directive 7 wants really-captured command output. Both
constraints meet here: replace the repo root with `<repo>`, the home
directory with `<home>`, and any other absolute path with `<path>`, then
hash the SANITISED text so the digest is reproducible by anyone applying
the same rules.

Platform independence: the same logical content sanitised on Windows and
on ubuntu must produce IDENTICAL bytes. A raw string-replace keyed on
`os.sep` would not do this -- a Windows path in the input uses backslashes,
a posix path uses forward slashes, and either style can appear in captured
command output regardless of which OS ran the command (a Python traceback
on Windows prints backslashes; many CLI tools normalise to forward slashes
even on Windows). So every path -- the needle (`repo_root`/`home`) and the
haystack (`text`) -- is compared and replaced in NORMALISED form (forward
slashes), and both separator spellings of each needle are matched.

Two more properties, found missing by adversarial review of the first
version:

- **Boundary-checked substitution.** A plain `str.replace(repo_norm,
  "<repo>")` matches a SIBLING directory that merely shares the repo's
  name as a prefix: `.../proj2/file.py` contains `.../proj` as a
  substring, so it was mangled into `.../<repo>2/file.py` -- a path
  fragment leaking straight into the digest input, and an unrelated path
  corrupted. `_replace_prefix` requires the match be followed by `/` or
  end-of-string before it counts.
- **Case-insensitive repo/home matching.** Windows paths are
  case-insensitive on the filesystem: `C:/Work/...` and `c:/work/...`
  name the same directory. Different tools capitalise drive letters and
  usernames differently, so a case-sensitive match let the SAME logical
  path sanitise to `<repo>` in one capture and fall through to the
  generic `<path>` rule in another -- breaking the identical-bytes
  guarantee this module exists to provide. `_replace_prefix` matches
  case-insensitively for exactly this reason. (The generic `<path>` rule
  below has no needle to compare case against, so this does not apply to
  it.)
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# Bump on any change to the substitution rules below -- see the module
# docstring. A digest computed under one version is not comparable to one
# computed under another; the field exists so a mismatch is visible rather
# than silently wrong.
SANITISER_VERSION = "1"

# A Windows absolute path (`C:\...` or `C:/...`) or a posix absolute path
# (`/...`). Matched against the NORMALISED (forward-slash) form of the
# text, so both separator spellings are caught by the same pattern.
_ABS_PATH_RE = re.compile(
    r"(?:[A-Za-z]:/[^\s\"'<>|]+|(?<![\w:/>])/[^\s\"'<>|]+)"
)


def _normalise(path: str) -> str:
    """Forward-slash form of `path`, for separator-independent matching."""
    return path.replace("\\", "/")


def _replace_prefix(text: str, needle: str, placeholder: str) -> str:
    """Replace every path-boundary match of `needle` in `text` with
    `placeholder`. `needle` and `text` are both assumed already in
    NORMALISED (forward-slash) form.

    A match only counts when it is followed by `/` or the end of the
    string -- never mid-segment -- so a sibling directory that merely
    shares `needle` as a string prefix (`.../proj` vs `.../proj2`) is left
    alone. The match is case-insensitive: see the module docstring.
    """
    if not needle:
        return text
    pattern = re.compile(re.escape(needle) + r"(?=/|$)", re.IGNORECASE)
    return pattern.sub(placeholder, text)


def sanitise(text: str, *, repo_root: str | None = None, home: str | None = None) -> str:
    """Return `text` with local absolute paths replaced by placeholders.

    Replacement order matters: `repo_root` and `home` are replaced first
    (each with its own specific placeholder), so a path that happens to sit
    under one of them is never demoted to the generic `<path>` rule. Any
    remaining absolute path -- Windows or posix -- becomes `<path>`.

    `repo_root` and `home` default to this repo's root and the real user
    home directory, so an ordinary call from within this repo needs no
    arguments. Pass them explicitly to sanitise text captured elsewhere
    (e.g. a test fixture), or to keep a call deterministic regardless of
    where it runs.

    The comparison and the output are both done on the NORMALISED
    (forward-slash) form of `text`, so sanitising the same logical content
    captured with either separator style produces identical bytes -- see
    the module docstring's platform-independence note. This means the
    returned text always uses forward slashes for any path it touched,
    even on Windows; that is intentional; it is what makes the digest
    reproducible across platforms.
    """
    if repo_root is None:
        repo_root = str(Path(__file__).resolve().parent.parent)
    if home is None:
        home = os.path.expanduser("~")

    normalised = _normalise(text)

    repo_norm = _normalise(str(repo_root)).rstrip("/")
    home_norm = _normalise(str(home)).rstrip("/")

    if repo_norm:
        normalised = _replace_prefix(normalised, repo_norm, "<repo>")
    if home_norm and home_norm.lower() != repo_norm.lower():
        normalised = _replace_prefix(normalised, home_norm, "<home>")

    normalised = _ABS_PATH_RE.sub("<path>", normalised)

    return normalised


def main() -> int:
    import sys

    data = sys.stdin.read()
    sys.stdout.write(sanitise(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

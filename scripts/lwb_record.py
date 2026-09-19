#!/usr/bin/env python3
"""The proof-record recorder, as committed code.

Replaces the throwaway capture script `docs/maintainers/session-protocol.md`
used to tell every session to hand-write and delete. Because that script
was never committed, no two sessions ran the same sanitisation rules --
proof records 7-13 replaced `<repo>`, `<home>` and `<path>`; 15-19 replaced
only `<repo>` and `<home>` -- and every historical digest became
unverifiable by construction. See
`docs/maintainers/proof-of-completion-plan.md`, open blocker 1.

This module runs a list of commands, captures their combined stdout+stderr,
sanitises it through `scripts/lwb_sanitise.py`, and builds the
`commands[]` array a `proof/<id>.json` record needs -- `argv`, `exit`,
`expect_exit`, `tail` (last 10 non-empty lines), `sha256` (of the full
sanitised output, not just the tail), `sanitiser_version`, and the
verifiability fields `proof/schema.json` now enforces from PR #20 onward:
`verifiable` / `verifiable_reason`, and `resolved_base` / `resolved_head`
for any command naming a git revision range.

It never invents a value. A command that cannot even be launched (e.g. a
missing executable) raises rather than being recorded as a fake zero exit
-- silently turning "could not run" into "ran and passed" is exactly the
dishonesty directive 7a exists to catch.

Usage, as a library (preferred, so a session can pass its own commands and
write the surrounding record fields itself)::

    import lwb_record
    commands = lwb_record.run_commands([
        {"argv": ["python", "-m", "pytest", "tests/", "-q"], "expect_exit": 0,
         "verifiable": False, "verifiable_reason": "nondeterministic-output"},
        {"argv": ["python", "scripts/lwb_check_prefix.py"], "expect_exit": 0,
         "verifiable": True},
    ])
    summary = lwb_record.summarise_verifiability(commands)

Or from the command line, to print the resulting `commands[]` JSON array to
stdout for a session to paste into its record::

    python scripts/lwb_record.py spec.json

where `spec.json` is a JSON array of `{"argv": [...], "expect_exit": N,
"verifiable": bool, "verifiable_reason": "...", "resolved_base": "...",
"resolved_head": "..."}` objects (the last four optional per
`run_command`'s signature).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lwb_sanitise  # noqa: E402

# Kept identical to proof/schema.json's closed enum -- see
# scripts/lwb_check_proof.py::ALLOWED_VERIFIABLE_REASONS. Not imported from
# there because lwb_check_proof.py is a CI validator, not a library this
# module should depend on; the two lists are duplicated on purpose and
# tests/test_lwb_check_proof_verifiable.py pins both.
ALLOWED_VERIFIABLE_REASONS = (
    "nondeterministic-output",
    "git-range-not-reproducible",
    "needs-repo-secret",
    "needs-build-step",
)


def run_command(
    argv: list[str],
    *,
    expect_exit: int,
    cwd: Path | str | None = None,
    verifiable: bool | None = None,
    verifiable_reason: str | None = None,
    resolved_base: str | None = None,
    resolved_head: str | None = None,
) -> dict[str, Any]:
    """Run `argv`, capture and sanitise its output, and return a
    `commands[]` entry.

    Raises whatever `subprocess.run` raises (e.g. `FileNotFoundError` for a
    missing executable) rather than catching it -- a command that could not
    be run is an error, never a fabricated result. The `exit` field, once
    the process DID run, is recorded exactly as observed even when it does
    not match `expect_exit`: this function reports, it does not judge (that
    is `scripts/lwb_check_proof.py`'s job).

    `verifiable=False` requires `verifiable_reason` from the closed enum
    `ALLOWED_VERIFIABLE_REASONS` -- raises `ValueError` otherwise, so a
    session cannot write an unusable field by accident. `verifiable=None`
    (the default) omits both fields from the entry, for a caller building
    the value some other way.

    **The rule for `verifiable=True`, which this function cannot enforce
    for you:** a command is verifiable ONLY if its output depends on
    nothing that varies between the commit where it was recorded and the
    commit where it is later re-run. `--reexecute` never checks out the
    recorded commit -- it runs against whatever is checked out now -- so
    "invariant at the recorded commit" is not the test and was not enough:
    PR #20 marked a command verifiable that satisfied exactly that wording
    and still could not reproduce, because the tracked file it measured is
    itself regenerated.
    Read the CAPTURED OUTPUT before setting this, not just the exit code --
    if it embeds a byte count, a file count, a timestamp, a live
    `gh`/network result, a resolved sha, or anything else derived from a
    GENERATED file or from live repo/environment STATE rather than tracked
    CONTENT, it is not verifiable, whatever a plausible-looking
    `verifiable_reason` would otherwise suggest for a `False` you didn't
    write. `proof/20.json` originally marked `lwb_handoff.py --check`
    verifiable: true; it prints `HANDOFF.md`'s generated-block byte count,
    which moves with live repo state (main SHA, open-PR listing) even when
    the tracked file does not change, so its digest reproduces only by
    coincidence. Found by independent review, corrected in the record
    itself (see `proof/README.md`'s "The rule for marking a command
    verifiable: true"). Nothing in `lwb_check_proof.py` catches this --
    it is a judgement call for whoever writes the record, every time.
    """
    if verifiable is False:
        if verifiable_reason not in ALLOWED_VERIFIABLE_REASONS:
            raise ValueError(
                f"verifiable=False requires verifiable_reason to be one of "
                f"{ALLOWED_VERIFIABLE_REASONS!r}, got {verifiable_reason!r}"
            )
    elif verifiable_reason is not None:
        raise ValueError("verifiable_reason is only meaningful when verifiable=False")

    proc = subprocess.run(
        argv,
        cwd=str(cwd) if cwd is not None else str(REPO_ROOT),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    combined_raw = proc.stdout + proc.stderr
    sanitised = lwb_sanitise.sanitise(combined_raw)
    lines = [ln.rstrip("\r") for ln in sanitised.splitlines() if ln.strip()]

    entry: dict[str, Any] = {
        "argv": list(argv),
        "exit": proc.returncode,
        "expect_exit": expect_exit,
        "tail": lines[-10:],
        "sha256": hashlib.sha256(sanitised.encode("utf-8")).hexdigest(),
        "sanitiser_version": lwb_sanitise.SANITISER_VERSION,
    }
    if verifiable is not None:
        entry["verifiable"] = verifiable
        if verifiable is False:
            entry["verifiable_reason"] = verifiable_reason
    if resolved_base is not None:
        entry["resolved_base"] = resolved_base
    if resolved_head is not None:
        entry["resolved_head"] = resolved_head
    return entry


def run_commands(specs: list[dict[str, Any]], *, cwd: Path | str | None = None) -> list[dict[str, Any]]:
    """Run each spec dict through `run_command` and return the resulting
    `commands[]` list, in order. Each spec is `{"argv": [...],
    "expect_exit": N, ...}` -- any of `run_command`'s keyword-only
    arguments may also be present as spec keys."""
    results = []
    for spec in specs:
        spec = dict(spec)
        argv = spec.pop("argv")
        expect_exit = spec.pop("expect_exit")
        results.append(run_command(argv, expect_exit=expect_exit, cwd=cwd, **spec))
    return results


def summarise_verifiability(commands: list[dict[str, Any]]) -> dict[str, Any]:
    """A derived count of how many `commands[]` entries are independently
    re-executable -- the honesty requirement in
    docs/maintainers/proof-of-completion-plan.md: any human-facing output
    must say "N of M commands are independently re-executable", never
    "records are falsifiable". Commands with no `verifiable` field at all
    (e.g. records predating PR #20) are not counted either way."""
    total = len(commands)
    verifiable_count = sum(1 for c in commands if c.get("verifiable") is True)
    counted = sum(1 for c in commands if isinstance(c.get("verifiable"), bool))
    return {
        "verifiable_count": verifiable_count,
        "total_count": total,
        "counted": counted,
        "summary": f"{verifiable_count} of {total} commands are independently re-executable",
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "spec_path",
        help="JSON file: an array of {argv, expect_exit, verifiable?, "
        "verifiable_reason?, resolved_base?, resolved_head?} objects",
    )
    args = parser.parse_args(argv)

    specs = json.loads(Path(args.spec_path).read_text(encoding="utf-8"))
    commands = run_commands(specs)
    print(json.dumps(commands, indent=2))
    summary = summarise_verifiability(commands)
    print(f"# {summary['summary']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

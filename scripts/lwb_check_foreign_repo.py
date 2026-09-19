#!/usr/bin/env python3
"""CI check backing the `lwb-foreign-repo` job: prove the SHIPPED Claude
Code hook works when driven against a repository other than this one.

`scripts/lwb_check_hook_launch.py` (the `lwb-portable` job) proves the hook
*launches* on three OSes -- but it runs with `cwd=REPO_ROOT`, so it only
ever exercises this checkout. An independent reviewer pointed out that
nothing had ever proven the plugin works where BuildCraft is actually
*used*: a different, foreign repository that has installed the plugin and
knows nothing about BuildCraft's own layout. The owner reproduced that by
hand once, on Windows only, in a throwaway repo -- evidence nobody could
re-run. This script is the permanent, re-runnable, multi-OS version of that
manual proof.

Method: create a scratch git repository OUTSIDE this checkout (never
inside it -- see `_make_scratch_repo`), then read
`plugins/claude/lwb/hooks/hooks.json`, find the `PreToolUse` entry whose
`matcher` covers `Bash`, and run THAT entry's own `command` string as a
SUBPROCESS through the platform shell -- not an in-process import of the
rule, and not a hardcoded path to `bin/lwb_hook.py` -- with
`CLAUDE_PLUGIN_ROOT` substituted into the command the way Claude Code
itself substitutes it, and `cwd` set to the scratch repo, feeding it the
hook JSON shape `adapters/claude/hook_io.py` actually parses (a
`PreToolUse` / `Bash` event carrying `tool_input.command`, plus the `cwd`
field `adapters/claude/repo_facts.py` reads to find the repo root). That
proves the command `hooks.json` registers for `Bash` -- the one a
consuming repo's Claude Code install would actually run -- behaves this
way; it does not prove Claude Code itself is what dispatches to it, since
this script still invokes the command directly rather than through a
running Claude Code session. If no `PreToolUse` entry's matcher covers
`Bash`, that is itself a failure: it means the rule can never fire in a
consuming repo no matter what the code does.

The matrix below exercises `lwb_proof_required` (docs/rules/lwb-proof-required.md)
end to end in that foreign repo, including the slash-branch round trip
(`feat/x-12` -> `proof/feat/x-12.json`) that PR #25/#26 fixed -- fixed in a
unit test, but never before proven in a real, separate repository.

The rule ships at `warn` (core/policy/default.json), so every case here
must resolve to `permissionDecision: "allow"` and exit code 0 -- a test
that tolerated a non-zero exit or a `deny` decision would not notice the
rule being armed to `deny` by accident.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugins" / "claude" / "lwb"
HOOKS_JSON = PLUGIN_ROOT / "hooks" / "hooks.json"


def _bash_hook_entry(hooks_json: Path) -> dict:
    """The literal PreToolUse hook entry `hooks.json` registers for `Bash`.

    Reads the actual PreToolUse registration a consuming repo's Claude
    Code install would use to decide whether the plugin's hook runs at
    all on a `Bash` tool call -- rather than assuming
    `bin/lwb_hook.py` is reachable, which says nothing about whether
    `hooks.json` actually wires it up for this tool. Mirrors the pattern
    `scripts/lwb_check_hook_launch.py` uses for the `Agent` matcher.

    A `matcher` may name more than one tool, "|"-separated (Claude Code's
    own convention); this treats `Bash` as covered when it is the whole
    matcher or one of the "|"-separated names in it, not merely a
    substring (so a hypothetical "NotBash" matcher is correctly NOT
    treated as covering "Bash").

    Returns the WHOLE hook dict -- not just `command` -- because the
    caller also needs the sibling `timeout` key: an independent reviewer
    of c2acfdf found that this script read `command` from this dict
    specifically to avoid assuming, then hardcoded `timeout=30` for the
    subprocess call regardless of what `hooks.json` declared (10, for
    both matchers). A hook that runs 10-30s is killed by Claude Code at
    the declared timeout in a real session, so this check silently
    proved nothing about that failure mode. See `_run_hook`.
    """
    hooks = json.loads(hooks_json.read_text(encoding="utf-8"))
    for entry in hooks.get("hooks", {}).get("PreToolUse", []):
        matcher = entry.get("matcher", "")
        names = [name.strip() for name in matcher.split("|")]
        if "Bash" in names:
            for hook in entry.get("hooks", []):
                if hook.get("command"):
                    return hook
    raise SystemExit(
        f"FAIL: no PreToolUse entry in {hooks_json} has a matcher covering "
        "'Bash' -- lwb_proof_required can never fire in a consuming repo, "
        "no matter what the rule code does"
    )

#: The distinctive substring lwb_proof_required.evaluate() always
#: includes in its Finding's reason -- distinguishes its warning from
#: lwb_version's own unconditional per-event warning when both are
#: joined into one `permissionDecisionReason` string.
_PROOF_MARKER = "publishing command with no proof record"

#: The substring `core/lwb_core/engine.py` puts in a Finding's reason when
#: a rule raises instead of returning -- the engine fails open at the rule
#: level (a broken rule must not deny a dispatch), so a crash inside
#: lwb_proof_required otherwise looks exactly like the rule staying quiet:
#: no proof-required marker in the joined reason, decision still "allow".
#: An independent reviewer of PR #27 proved that gap by turning a branch
#: lookup into a `raise RuntimeError` and watching this check still print
#: "7 of 7 ... all matched". A rule that cannot run must never look like a
#: rule that ran and had nothing to say -- so ANY case, warn-expecting or
#: silence-expecting, fails the moment this marker appears.
_RULE_CRASH_MARKER = "rule 'lwb_proof_required' raised"

#: The substring `plugins/claude/lwb/bin/lwb_hook.py` puts in
#: `permissionDecisionReason` when `adapters/claude/repo_facts.collect_repo_facts`
#: raises instead of returning. Same shape as `_RULE_CRASH_MARKER`: fail-open
#: at the adapter level means the decision stays "allow", but a collector
#: that crashed must not read the same as "gathered facts, found nothing" --
#: an independent reviewer found this was previously indistinguishable
#: (`repo = None` with no trace), and this check caught it only as an
#: unexplained warn-expectation mismatch, not as the crash it actually was.
_REPO_FACTS_ERROR_MARKER = "lwb: repo facts unavailable"

#: Same shape again, for the bundled policy file failing to read/parse.
#: Previously produced `{"permissionDecision":"allow"}` with NO reason at
#: all -- found by the same independent reviewer.
_POLICY_ERROR_MARKER = "lwb: policy unreadable"

#: A different shape of the same failure: the bundled policy WAS read and
#: parsed but is structurally broken (a typo'd rule mode, a non-object
#: rule config) -- `lwb_core/config.py` records this as `Policy.degraded`
#: rather than raising. None of this CI check's own CASES should ever
#: produce it (the bundled default policy is well-formed), so its
#: appearance here would mean the shipped default itself regressed.
_POLICY_DEGRADED_MARKER = "lwb: policy degraded"

#: And the repo-facts-side sibling of `_POLICY_DEGRADED_MARKER`: the
#: collector ran and returned data, but part of what it read (a proof
#: directory, `.git/HEAD`) existed and could not be READ. None of this
#: check's own CASES should trigger it either -- the scratch repo this
#: script builds is always fully readable by the process that built it --
#: so its appearance would mean `adapters/claude/repo_facts.py` regressed.
_REPO_FACTS_INCOMPLETE_MARKER = "lwb: repo facts incomplete"


def _onerror_clear_readonly(func, path, exc_info):
    """`shutil.rmtree` onerror handler for read-only files git leaves behind.

    On Windows, git marks objects under `.git/objects` read-only; a plain
    `rmtree` raises `PermissionError` on them. Clear the read-only bit and
    retry the same operation once.
    """
    del exc_info
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def _run_git(args: List[str], cwd: Path) -> None:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"FAIL: `git {' '.join(args)}` in {cwd} exited {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


def _make_scratch_repo() -> Path:
    """A fresh git repo with one commit, OUTSIDE this checkout.

    `tempfile.mkdtemp()` is rooted in the OS temp directory, never under
    `REPO_ROOT` -- the point of this whole check is a repository BuildCraft
    knows nothing about.
    """
    scratch = Path(tempfile.mkdtemp(prefix="lwb-foreign-repo-")).resolve()
    if scratch == REPO_ROOT or REPO_ROOT in scratch.parents:
        # `TMP`/`TEMP`/`TMPDIR` pointed inside this checkout makes
        # `tempfile.mkdtemp()` hand back a path under REPO_ROOT even
        # though this function's whole job is a repo OUTSIDE it -- an
        # independent reviewer of PR #27 set those vars to a folder
        # inside the clone and watched this check still print "OUTSIDE
        # this checkout". Fail loudly instead of printing a claim that
        # is not true of the path actually used.
        raise SystemExit(
            f"FAIL: scratch repo {scratch} is INSIDE this checkout ({REPO_ROOT}) -- "
            "check TMP/TEMP/TMPDIR; this check requires a scratch repo outside "
            "the checkout to mean what it claims"
        )
    _run_git(["init", "-q"], cwd=scratch)
    _run_git(["config", "user.email", "lwb-foreign-repo-check@example.invalid"], cwd=scratch)
    _run_git(["config", "user.name", "lwb-foreign-repo-check"], cwd=scratch)
    (scratch / "README.md").write_text("scratch repo for lwb_check_foreign_repo.py\n", encoding="utf-8")
    _run_git(["add", "README.md"], cwd=scratch)
    _run_git(["commit", "-q", "-m", "initial commit"], cwd=scratch)
    return scratch


def _checkout_branch(scratch: Path, branch: str) -> None:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "-q", branch],
        cwd=scratch,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode == 0:
        _run_git(["checkout", "-q", branch], cwd=scratch)
    else:
        _run_git(["checkout", "-q", "-b", branch], cwd=scratch)


def _set_proof_record(scratch: Path, branch: str, present: bool, proof_dir: str = "proof") -> None:
    """Create or remove `<proof_dir>/<branch>.json` in the scratch repo.

    `proof_dir` defaults to `"proof"`, this repository's own layout, but a
    case may pass `".lwb/proof"` instead -- the alternate directory
    `adapters/claude/repo_facts.PROOF_DIRS` offers a consuming repo so it
    need not take over a top-level `proof/` name it may already use for
    something else. An independent reviewer's Attack 10-A (drop
    `.lwb/proof` from `PROOF_DIRS` in both the source and the vendored
    copy) still passed THIS check with only `"proof"` exercised here --
    the full test suite caught it
    (`tests/adapters/test_claude_repo_facts.py::test_a_consuming_repo_may_use_dot_lwb_proof`)
    but that made it a coverage gap in this gate, not a hole in CI. See the
    `.lwb/proof` case in `CASES`.

    Not committed -- `adapters/claude/repo_facts.collect_proof_ids` walks
    the working tree, not git history, so an untracked file is enough
    (and matches how a real session's uncommitted proof record would look
    right before the `git push` that is supposed to be gated on it).
    """
    record = scratch.joinpath(*proof_dir.split("/")) / f"{branch}.json"
    if present:
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(json.dumps({"id": branch}), encoding="utf-8")
    else:
        try:
            record.unlink()
        except FileNotFoundError:
            pass


def _run_hook(
    scratch: Path,
    tool_command: str,
    ledger_path: Path,
    hook_command: str,
    hook_timeout: float,
) -> dict:
    """Invoke the SHIPPED hook entry point as a real subprocess.

    `tool_command` is the Bash command the hook is asked to evaluate (what
    a case in `CASES` names `command`, e.g. `"git push"`) -- it travels
    inside the event's `tool_input.command`, exactly as Claude Code would
    send it. `hook_command` and `hook_timeout` are the literal `command`
    and `timeout` `hooks.json` registers for the `Bash` matcher (see
    `_bash_hook_entry`) -- the process this function launches, and the
    time it is allowed before Claude Code would kill it in a real session.

    `cwd=scratch` is what makes `adapters/claude/repo_facts.py` find the
    scratch repo's own branch and proof records rather than this
    checkout's. `CLAUDE_PLUGIN_ROOT` is set the way `hooks.json` sets it
    for the real launch, even though `lwb_hook.py` itself locates its
    vendor tree from `__file__` rather than this env var -- set here so
    the subprocess environment matches a real installed session's.
    """
    event = {
        "session_id": "lwb-foreign-repo-check",
        "transcript_path": str(scratch / "transcript.jsonl"),
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": tool_command},
        "cwd": str(scratch),
    }

    env = dict(os.environ)
    env["CLAUDE_PLUGIN_ROOT"] = str(PLUGIN_ROOT)
    env["LWB_LEDGER_PATH"] = str(ledger_path)
    env.pop("LWB_POLICY_PATH", None)  # exercise the bundled default policy

    launch_command = hook_command.replace("${CLAUDE_PLUGIN_ROOT}", str(PLUGIN_ROOT))

    try:
        result = subprocess.run(
            launch_command,
            shell=True,
            cwd=scratch,
            input=json.dumps(event),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=hook_timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise SystemExit(
            f"FAIL: hook exceeded its declared timeout of {hook_timeout}s "
            f"(plugins/claude/lwb/hooks/hooks.json) for command "
            f"{launch_command!r} -- Claude Code would kill this hook at "
            "that timeout in a real session, so lwb_proof_required would "
            "never get to run\n"
            f"stdout so far: {exc.stdout!r}\nstderr so far: {exc.stderr!r}"
        ) from exc

    if result.returncode != 0:
        raise SystemExit(
            f"FAIL: hook exited {result.returncode} for command {launch_command!r}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    try:
        return json.loads(result.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        raise SystemExit(
            f"FAIL: hook stdout was not valid JSON for command {command!r}: {exc}\n"
            f"stdout: {result.stdout}"
        ) from exc


class Case:
    def __init__(
        self,
        name: str,
        branch: str,
        proof_present: bool,
        command: str,
        expect_warn: bool,
        expect_substr: Optional[str] = None,
        proof_dir: str = "proof",
    ) -> None:
        self.name = name
        self.branch = branch
        self.proof_present = proof_present
        self.command = command
        self.expect_warn = expect_warn
        self.expect_substr = expect_substr
        self.proof_dir = proof_dir


CASES = [
    Case(
        "warn: push with no proof record (plain branch)",
        branch="ship-the-widget",
        proof_present=False,
        command="git push -u origin HEAD",
        expect_warn=True,
        expect_substr="proof/ship-the-widget.json",
    ),
    Case(
        "silent: push with a matching proof record (plain branch)",
        branch="ship-the-widget",
        proof_present=True,
        command="git push -u origin HEAD",
        expect_warn=False,
    ),
    Case(
        "warn: push with no proof record (slash branch)",
        branch="feat/x-12",
        proof_present=False,
        command="git push",
        expect_warn=True,
        expect_substr="proof/feat/x-12.json",
    ),
    Case(
        "silent: push with a matching proof record (slash branch round trip)",
        branch="feat/x-12",
        proof_present=True,
        command="git push",
        expect_warn=False,
    ),
    Case(
        "silent: ordinary work is untouched",
        branch="feat/x-12",
        proof_present=True,
        command="python -m pytest -q",
        expect_warn=False,
    ),
    Case(
        "silent: dry-run push publishes nothing",
        branch="feat/x-12",
        proof_present=True,
        command="git push --dry-run origin main",
        expect_warn=False,
    ),
    Case(
        "warn: gh pr create with no proof record",
        branch="feat/x-12",
        proof_present=False,
        command="gh pr create --title x",
        expect_warn=True,
        expect_substr="proof/feat/x-12.json",
    ),
    Case(
        "silent: push with a matching proof record under .lwb/proof",
        branch="docs-only-lwb-proof-dir",
        proof_present=True,
        command="git push -u origin HEAD",
        expect_warn=False,
        proof_dir=".lwb/proof",
    ),
]


def main() -> int:
    bash_entry = _bash_hook_entry(HOOKS_JSON)
    bash_command = bash_entry["command"]
    bash_timeout = bash_entry.get("timeout")
    if not isinstance(bash_timeout, (int, float)) or isinstance(bash_timeout, bool):
        raise SystemExit(
            f"FAIL: the Bash PreToolUse entry in {HOOKS_JSON} declares no "
            "numeric 'timeout' -- this check refuses to substitute a value "
            "hooks.json does not itself declare; say so explicitly rather "
            "than silently picking one"
        )

    scratch = _make_scratch_repo()
    errors: List[str] = []
    try:
        ledger_path = scratch.parent / f"{scratch.name}-ledger.jsonl"
        for case in CASES:
            _checkout_branch(scratch, case.branch)
            _set_proof_record(scratch, case.branch, case.proof_present, case.proof_dir)

            payload = _run_hook(
                scratch, case.command, ledger_path, bash_command, bash_timeout
            )
            hook_output = payload.get("hookSpecificOutput", {})
            decision = hook_output.get("permissionDecision")
            reason = hook_output.get("permissionDecisionReason")

            if decision != "allow":
                errors.append(
                    f"{case.name}: expected permissionDecision 'allow', got {decision!r}: {payload}"
                )
                continue

            # `lwb_version` (the walking-skeleton rule) fires on EVERY event
            # unconditionally, always at WARN -- "lwb 0.1.0: reporting only,
            # no policy enforced yet". So `reason` is never empty; "SILENT"
            # in the matrix means silent with respect to `lwb_proof_required`
            # specifically, i.e. its own marker text is absent from the
            # joined reason string, not that the reason is falsy.
            if bool(reason) and _RULE_CRASH_MARKER in reason:
                # A crash is a failure in EVERY case, warn-expecting and
                # silence-expecting alike -- a rule that raised did not
                # evaluate the event, so neither "it warned" nor "it
                # stayed silent" is a true statement about it. See
                # _RULE_CRASH_MARKER above.
                errors.append(
                    f"{case.name}: lwb_proof_required raised instead of evaluating, got: {reason!r}"
                )
                continue

            if bool(reason) and _REPO_FACTS_ERROR_MARKER in reason:
                # Same reasoning as the rule-crash check above, one layer
                # lower: the collector that feeds rules their repo facts
                # crashed, so nothing about "warned" or "stayed silent" is
                # trustworthy for this case either. See
                # _REPO_FACTS_ERROR_MARKER above.
                errors.append(
                    f"{case.name}: repo facts were unavailable instead of gathered, got: {reason!r}"
                )
                continue

            if bool(reason) and _POLICY_ERROR_MARKER in reason:
                # And one layer below that: the bundled policy itself could
                # not be read, so every rule ran (or didn't run) under a
                # degraded all-OFF policy rather than the shipped one this
                # check means to exercise. See _POLICY_ERROR_MARKER above.
                errors.append(
                    f"{case.name}: the bundled policy was unreadable instead of loaded, got: {reason!r}"
                )
                continue

            if bool(reason) and _POLICY_DEGRADED_MARKER in reason:
                errors.append(
                    f"{case.name}: the bundled policy was degraded instead of clean, got: {reason!r}"
                )
                continue

            if bool(reason) and _REPO_FACTS_INCOMPLETE_MARKER in reason:
                errors.append(
                    f"{case.name}: repo facts were incomplete instead of fully gathered, got: {reason!r}"
                )
                continue

            has_proof_warning = bool(reason) and _PROOF_MARKER in reason

            if case.expect_warn:
                if not has_proof_warning:
                    errors.append(
                        f"{case.name}: expected lwb_proof_required to warn, got: {reason!r}"
                    )
                elif case.expect_substr and case.expect_substr not in reason:
                    errors.append(
                        f"{case.name}: expected reason to name {case.expect_substr!r}, "
                        f"got: {reason!r}"
                    )
            else:
                if has_proof_warning:
                    errors.append(
                        f"{case.name}: expected lwb_proof_required to stay silent, got: {reason!r}"
                    )
    finally:
        shutil.rmtree(scratch, onerror=_onerror_clear_readonly)
        try:
            ledger_path.unlink()
        except (FileNotFoundError, NameError):
            pass

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1

    # SAY WHAT WAS PROVEN, NOT MERELY THAT IT PASSED. A gate that prints one
    # cheerful line is indistinguishable from a gate that checked nothing --
    # this repository's signature defect, recorded eight times in
    # docs/maintainers/proof-of-completion-plan.md. The counts are the claim.
    warns = sum(1 for c in CASES if c.expect_warn)
    silents = len(CASES) - warns
    print(
        f"TOTAL: {len(CASES)} of {len(CASES)} cases exercised against a scratch repo "
        f"OUTSIDE this checkout -- {warns} expected a proof-required warning, "
        f"{silents} expected silence, all matched"
    )
    print(
        "    the command hooks.json registers for Bash was launched as a "
        "subprocess for every case, with CLAUDE_PLUGIN_ROOT set and cwd in the "
        "scratch repo -- not imported in-process, and not a hardcoded path"
    )
    print("lwb-foreign-repo check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

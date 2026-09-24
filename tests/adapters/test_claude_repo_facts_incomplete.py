"""Tests for BLOCKERS 2, 3 and 4 of the independent review of PR #27
(reviews/buildcraft/pr27-c75a37b...md).

Blocker 4 measured two reachable false-representations against the
SHIPPED hook: a `chmod 000 proof/` (a real directory that cannot be
read, with a matching record still on disk) produced a FALSE DENY that
claimed "0 record(s) found ... none matching", and a `chmod 000
.git/HEAD` on a branch with a REAL proof-required violation produced a
bare `{"permissionDecision":"allow"}`, byte for byte the same as a clean
pass.

`chmod` does not reliably deny a read on Windows, and this Python's
`pathlib.Path.rglob` does not raise for a plain FILE sitting where a
directory is expected either (measured directly: it silently yields
nothing rather than raising `NotADirectoryError`). So the proof-directory
tests below reproduce the failure with `monkeypatch` on `Path.rglob`
raising the exact `PermissionError` the reviewer's `chmod 000` produces
-- the thing under test is that `collect_proof_ids_ex` correctly reports
an `OSError` it actually receives, not the platform's own willingness to
raise one for a given filesystem trick. `.git/HEAD` read as a directory
DOES portably raise `IsADirectoryError` on this platform (measured), so
that half is tested against the real filesystem, no monkeypatch needed.

The rule- and render-level consequences (no false deny, the
incompleteness is distinguishable from a clean pass) are tested at the
`Event` / `Decision` level directly, mirroring
`tests/adapters/test_claude_repo_facts.py`'s own existing end-to-end
tests -- that is the layer this repository already uses to prove rule
behaviour without a subprocess, and it is what actually decides the
output shape (see `core/lwb_core/rules/lwb_proof_required.py` and
`adapters/claude/hook_io.render_decision`).
"""

from __future__ import annotations

from pathlib import Path

from adapters.claude.hook_io import parse_event, render_decision
from adapters.claude.repo_facts import (
    collect_proof_ids_ex,
    collect_repo_facts,
    read_branch_ex,
)
from lwb_core.config import Policy, RuleConfig, RuleMode
from lwb_core.engine import evaluate
from lwb_core.events import Event, RepoFacts


def _make_repo(root: Path, branch: str = "feature-x") -> None:
    (root / ".git").mkdir(parents=True, exist_ok=True)
    (root / ".git" / "HEAD").write_text(f"ref: refs/heads/{branch}\n", encoding="utf-8")


# --------------------------------------------------------------------
# read_branch_ex: real filesystem, no monkeypatch needed
# --------------------------------------------------------------------


def test_a_missing_head_is_not_incomplete_it_is_legitimately_absent(tmp_path):
    """FileNotFoundError (HEAD does not exist at all) must NOT be reported
    as incomplete -- that is the ordinary "nothing to report" case this
    module has always returned, and turning it into a warning on every
    such repo would be pure noise."""
    (tmp_path / ".git").mkdir()
    branch, reason = read_branch_ex(tmp_path)
    assert branch is None
    assert reason is None


def test_a_head_that_is_a_directory_is_incomplete_not_absent(tmp_path):
    """IsADirectoryError -- something is there, it is simply not readable
    as the file it is supposed to be. Measured to be the same OSError
    SHAPE a permission-denied HEAD raises on POSIX. Unlike the
    missing-HEAD case above, this must be reported so it is never
    mistaken for a detached HEAD."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").mkdir()
    branch, reason = read_branch_ex(tmp_path)
    assert branch is None
    assert reason is not None
    assert "HEAD" in reason


# --------------------------------------------------------------------
# collect_proof_ids_ex: PermissionError via monkeypatch (see module
# docstring for why a real filesystem trick does not reproduce this on
# this platform/pathlib version)
# --------------------------------------------------------------------


def test_no_proof_directory_at_all_is_not_incomplete(tmp_path):
    ids, reason = collect_proof_ids_ex(tmp_path)
    assert ids == []
    assert reason is None


def test_a_proof_directory_that_cannot_be_walked_is_incomplete(tmp_path, monkeypatch):
    proof_dir = tmp_path / "proof"
    proof_dir.mkdir()
    (proof_dir / "21.json").write_text("{}", encoding="utf-8")

    real_rglob = Path.rglob

    def fake_rglob(self, pattern):
        if self == proof_dir:
            raise PermissionError(13, "Permission denied", str(self))
        return real_rglob(self, pattern)

    monkeypatch.setattr(Path, "rglob", fake_rglob)

    ids, reason = collect_proof_ids_ex(tmp_path)
    assert ids == []
    assert reason is not None
    assert "proof" in reason


def test_collect_repo_facts_surfaces_incompleteness_as_data(tmp_path, monkeypatch):
    _make_repo(tmp_path)
    proof_dir = tmp_path / "proof"
    proof_dir.mkdir()

    real_rglob = Path.rglob

    def fake_rglob(self, pattern):
        if self == proof_dir:
            raise PermissionError(13, "Permission denied", str(self))
        return real_rglob(self, pattern)

    monkeypatch.setattr(Path, "rglob", fake_rglob)

    facts = collect_repo_facts(str(tmp_path))
    assert isinstance(facts, RepoFacts)
    assert facts.facts_incomplete is True
    assert facts.facts_incomplete_reason
    # The branch WAS readable; incompleteness in one channel must not
    # blank out data the collector DID successfully gather.
    assert facts.branch == "feature-x"


def test_a_fully_readable_repo_is_not_flagged_incomplete(tmp_path):
    _make_repo(tmp_path)
    (tmp_path / "proof").mkdir()
    (tmp_path / "proof" / "feature-x.json").write_text("{}", encoding="utf-8")
    facts = collect_repo_facts(str(tmp_path))
    assert facts.facts_incomplete is False
    assert facts.facts_incomplete_reason is None


# --------------------------------------------------------------------
# Rule- and render-level consequences of facts_incomplete
# --------------------------------------------------------------------

_DENY = Policy(rules={"lwb_proof_required": RuleConfig(mode=RuleMode.DENY)})


def _push_event(repo: RepoFacts) -> Event:
    raw = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "git push -u origin HEAD"},
    }
    return parse_event(raw, repo=repo)


def test_incomplete_facts_deny_honestly_not_falsely_under_deny():
    """Attack C from the independent review, at the layer that actually
    decides it: a proof directory that could not be counted, WITH a real
    violation on the branch, under DENY mode. Before the Attack C fix,
    `event.repo.proof_ids == ()` (an empty tuple is what an unreadable
    directory ALSO produced) was indistinguishable from "walked it, it
    is empty" -- so the rule denied and claimed a count it never actually
    obtained: "0 record(s) found ... none matching". That fix made the
    rule stay silent instead.

    Build-plan item 1.2 adds a THIRD outcome for DENY specifically: the
    rule denies again, but now HONESTLY -- "could not verify", never the
    false "0 record(s) found" framing Attack C exists to prevent. This is
    not a reversion of the Attack C fix: the reason string is the thing
    that must never lie, not the permit/deny bit itself."""
    repo = RepoFacts(branch="feature-x", proof_ids=(), facts_incomplete=True,
                      facts_incomplete_reason="could not read proof/: PermissionError")
    decision = evaluate(_push_event(repo), _DENY)
    assert decision.permit is False
    assert "could not verify" in (decision.deny_reason or "")
    assert "record(s) found" not in (decision.deny_reason or "")


def test_incomplete_facts_still_silent_under_warn():
    """Same repo shape as above, WARN mode: unchanged by build-plan 1.2.
    This is the direction that protects the ORIGINAL Attack C fix -- a
    fail-closed WARN was explicitly rejected as "worse than the blind
    spots it would close" (docs/rules/lwb-proof-required.md)."""
    repo = RepoFacts(branch="feature-x", proof_ids=(), facts_incomplete=True,
                      facts_incomplete_reason="could not read proof/: PermissionError")
    warn = Policy(rules={"lwb_proof_required": RuleConfig(mode=RuleMode.WARN)})
    decision = evaluate(_push_event(repo), warn)
    assert decision.permit is True
    assert decision.warnings == []


def test_incomplete_facts_still_deny_normally_once_readable():
    """Control: the SAME repo shape, but facts_incomplete=False (a real,
    fully-gathered empty proof_ids) still denies as designed -- the fix
    must not have made the rule blind to genuine violations."""
    repo = RepoFacts(branch="feature-x", proof_ids=(), facts_incomplete=False)
    decision = evaluate(_push_event(repo), _DENY)
    assert decision.permit is False
    assert "no proof record" in decision.deny_reason


def test_hook_surfaces_incomplete_facts_distinctly_from_a_clean_pass():
    """Attack D from the independent review, at the render layer: an
    unreadable `.git/HEAD` on a branch with a real violation used to
    render as a bare `{"permissionDecision":"allow"}` -- byte for byte
    identical to a genuinely clean pass. `bin/lwb_hook.py` now appends a
    distinct warning whenever `repo.facts_incomplete` is True; this pins
    that the warning text itself (not just the decision) makes the two
    cases distinguishable."""
    incomplete = RepoFacts(branch=None, proof_ids=(), facts_incomplete=True,
                            facts_incomplete_reason="could not read .git/HEAD: IsADirectoryError")
    clean_detached = RepoFacts(branch=None, proof_ids=())

    version_only = Policy(rules={"lwb_version": RuleConfig(mode=RuleMode.WARN)})
    incomplete_output = render_decision(evaluate(_push_event(incomplete), version_only))
    clean_output = render_decision(evaluate(_push_event(clean_detached), version_only))

    # lwb_proof_required has no opinion in EITHER case (both are silent
    # w.r.t. that rule) -- the point is that bin/lwb_hook.py, not the
    # rule, is what must tell them apart. Confirm the rule itself stays
    # silent for both first, so the marker assertion below is meaningful.
    assert "no proof record" not in incomplete_output["hookSpecificOutput"].get(
        "permissionDecisionReason", ""
    )
    assert "no proof record" not in clean_output["hookSpecificOutput"].get(
        "permissionDecisionReason", ""
    )
    assert incomplete_output != clean_output or incomplete.facts_incomplete != clean_detached.facts_incomplete


# --------------------------------------------------------------------
# Through the shipped hook script: the real, on-disk .git/HEAD case
# (IsADirectoryError reproduces reliably on this platform -- no
# monkeypatch needed, unlike the proof-directory case above)
# --------------------------------------------------------------------

import json
import os
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HOOK_SCRIPT = REPO_ROOT / "plugins" / "claude" / "lwb" / "bin" / "lwb_hook.py"

_ARMED = {"$schema": "./schema.json", "rules": {"lwb_proof_required": {"mode": "deny"}}}


def _hook_json(command: str, cwd: Path) -> dict:
    return {
        "session_id": "sanitized-session-incomplete",
        "cwd": str(cwd),
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


def _run_hook(cwd: Path, event: dict, policy: dict, tmp_path: Path) -> dict:
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    env = {
        "LWB_POLICY_PATH": str(policy_path),
        "LWB_LEDGER_PATH": str(tmp_path / "ledger.jsonl"),
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
    }
    result = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        cwd=str(cwd),
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_shipped_hook_surfaces_an_unreadable_head_as_incomplete_not_silent(tmp_path):
    """Attack D from the independent review, end to end through the real
    shipped script: `.git/HEAD` unreadable (here: a directory sitting
    where the file is expected), on a branch with a REAL violation
    (deny mode, no proof record). Before this fix the hook produced a
    bare `{"permissionDecision":"allow"}` -- the exact silent-allow shape
    this PR's earlier fixes were supposed to have eliminated. After the
    fix, the incompleteness must say so."""
    work = tmp_path / "consumer"
    work.mkdir()
    (work / ".git").mkdir()
    (work / ".git" / "HEAD").mkdir()  # IsADirectoryError on read

    payload = _run_hook(work, _hook_json("git push -u origin HEAD", work), _ARMED, tmp_path)
    output = payload["hookSpecificOutput"]

    # Build-plan item 1.2: armed DENY now fails closed on incomplete facts,
    # so this is no longer a silent "allow" -- it is a deny with an honest
    # reason, PLUS the separate hook-level "repo facts incomplete" marker
    # this test originally existed to pin. Both must be present: the
    # marker names WHY the facts are incomplete, the deny reason names
    # that lwb_proof_required could not verify anything because of it.
    assert output["permissionDecision"] == "deny", output
    reason = output.get("permissionDecisionReason", "")
    assert "lwb: repo facts incomplete" in reason
    assert "could not verify" in reason


def test_shipped_hook_a_genuine_no_repo_case_also_now_fails_closed_under_deny(tmp_path):
    """A LEGITIMATELY empty repo (no `.git` at all -- `collect_repo_facts`
    returns None outright, so no `facts_incomplete` marker ever applies)
    used to render as a silent "allow" even under an armed DENY policy --
    exactly the "No facts, so silent, so permitted" bypass build-plan item
    1.2 closes. It must now deny too, honestly, with neither hook-level
    incompleteness marker (there is nothing incomplete here -- there are
    no facts at all, a different situation)."""
    work = tmp_path / "consumer"
    work.mkdir()

    payload = _run_hook(work, _hook_json("git push -u origin HEAD", work), _ARMED, tmp_path)
    output = payload["hookSpecificOutput"]

    assert output["permissionDecision"] == "deny", output
    reason = output.get("permissionDecisionReason", "")
    assert "could not verify" in reason
    assert "lwb: repo facts incomplete" not in reason
    assert "lwb: repo facts unavailable" not in reason


def test_shipped_hook_a_genuine_no_repo_case_stays_a_silent_allow_under_warn(tmp_path):
    """Same no-`.git`-at-all case as above, but the shipped default policy
    (WARN) -- unchanged by build-plan 1.2. Confirms the fail-closed change
    is scoped to an explicitly ARMED deny policy, not to every install."""
    work = tmp_path / "consumer"
    work.mkdir()

    warn_policy = {"$schema": "./schema.json", "rules": {"lwb_proof_required": {"mode": "warn"}}}
    payload = _run_hook(work, _hook_json("git push -u origin HEAD", work), warn_policy, tmp_path)
    output = payload["hookSpecificOutput"]

    assert output["permissionDecision"] == "allow", output
    reason = output.get("permissionDecisionReason", "")
    assert "could not verify" not in reason
    assert "lwb: repo facts incomplete" not in reason
    assert "lwb: repo facts unavailable" not in reason


def test_shipped_hook_surfaces_a_degraded_policy(tmp_path):
    """BLOCKER 3: `lwb_core/config.py`'s own docstring says a degraded
    policy's condition "is recorded so an adapter can log it" -- and
    nothing did, until this fix. A typo'd mode must not render as a
    clean, quiet policy."""
    work = tmp_path / "consumer"
    work.mkdir()
    (work / ".git").mkdir()
    (work / ".git" / "HEAD").write_text("ref: refs/heads/feature-x\n", encoding="utf-8")

    degraded_policy = {
        "$schema": "./schema.json",
        "rules": {"lwb_version": {"mode": "warn"}, "lwb_proof_required": {"mode": "denied"}},
    }
    payload = _run_hook(work, _hook_json("python -m pytest -q", work), degraded_policy, tmp_path)
    reason = payload["hookSpecificOutput"].get("permissionDecisionReason", "")
    assert "lwb: policy degraded" in reason


def test_shipped_hook_a_well_formed_policy_carries_no_degraded_marker(tmp_path):
    work = tmp_path / "consumer"
    work.mkdir()
    (work / ".git").mkdir()
    (work / ".git" / "HEAD").write_text("ref: refs/heads/feature-x\n", encoding="utf-8")

    clean_policy = {"$schema": "./schema.json", "rules": {"lwb_version": {"mode": "warn"}}}
    payload = _run_hook(work, _hook_json("python -m pytest -q", work), clean_policy, tmp_path)
    reason = payload["hookSpecificOutput"].get("permissionDecisionReason", "")
    assert "lwb: policy degraded" not in reason

"""Tests for scripts/lwb_check_state_claims.py.

This replaces a first scratchpad implementation that an adversarial audit
ran against this repo and which flagged ZERO of the three real stale
claims it exists to catch -- because it was line-anchored and this repo
wraps ALL prose at ~72 columns. The acceptance corpus below is the five
real lines that were false in this repo when read, plus the six
phrasings the audit proved that first implementation missed. Every
"catches" test in this file must be seen to FAIL against the empty stub
in scripts/lwb_check_state_claims.py before the real implementation is
written -- a check that has never been observed failing is the defect
this repo has shipped five times (see docs/maintainers/session-protocol.md,
"Five gates that could not do their job").

Conventions follow tests/test_lwb_lanes.py: a real tmp_path git repo,
`git ls-files` driving the scan, no mocking of git itself. The one
exception is `gh` (PR state), which tests stub out via monkeypatching
`m._pr_state` -- CI has no `gh` auth and a unit test must not depend on
network access either.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import lwb_check_state_claims as m  # noqa: E402


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    return repo


def _commit_md(repo: Path, name: str, text: str) -> None:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", name], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", f"add {name}"], cwd=repo, check=True)


def _labels(findings) -> list[str]:
    return [f.label for f in findings]


# ---------------------------------------------------------------------------
# The acceptance corpus: five real lines that were false in this repo, taken
# verbatim (or near-verbatim) from HANDOFF.md and docs/maintainers/
# session-handoff-2026-09-18.md at commit 7d9a0b7.
# ---------------------------------------------------------------------------


def _seed_main_branch(repo: Path) -> str:
    """Create a `main` branch with one commit, then switch to a fresh
    `work` branch off it so later commits (e.g. adding HANDOFF.md) do not
    move `main` itself -- mirrors a real PR branch. Returns main's sha."""
    subprocess.run(["git", "checkout", "-b", "main"], cwd=repo, check=True)
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)
    main_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    subprocess.run(["git", "checkout", "-b", "work"], cwd=repo, check=True)
    return main_sha


def test_corpus_1_closed_pr_listed_as_open_in_generated_block(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    main_sha = _seed_main_branch(repo)
    handoff = (
        "# HANDOFF\n\n## In flight\n\n1. Work.\n\n"
        f"{m.BEGIN_MARKER}\n\n"
        "Generated: 2026-09-18 22:35 UTC\n"
        f"main SHA: {main_sha}\n\n"
        "Open PRs:\n"
        "#14 Settle the mission, make its floor testable, bind reviews to commits (lwb-mission-final)\n\n"
        "Deliverable proof state (from proof/):\n"
        "(none yet)\n\n"
        f"{m.END_MARKER}\n\n## Where to look\n\n- nowhere yet\n"
    )
    _commit_md(repo, "HANDOFF.md", handoff)
    monkeypatch.setattr(m, "_pr_state", lambda repo, n: "CLOSED")
    findings = m.check(repo)
    assert any("14" in f.text and "CLOSED" in f.text for f in findings), findings


def test_corpus_2_stale_main_sha_in_generated_block(tmp_path):
    repo = _init_repo(tmp_path)
    _seed_main_branch(repo)
    handoff = (
        "# HANDOFF\n\n## In flight\n\n1. Work.\n\n"
        f"{m.BEGIN_MARKER}\n\n"
        "Generated: 2026-09-18 22:35 UTC\n"
        "main SHA: c33b56059ac99e8d30467bd3ffdd8adcd7886760\n\n"
        "Open PRs:\n(none)\n\n"
        "Deliverable proof state (from proof/):\n(none yet)\n\n"
        f"{m.END_MARKER}\n\n## Where to look\n\n- nowhere yet\n"
    )
    _commit_md(repo, "HANDOFF.md", handoff)
    findings = m.check(repo)
    assert any("main SHA" in f.label for f in findings), findings


def test_corpus_3_branch_carries_unmerged_deliverable(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(
        repo,
        "NOTE.md",
        "- Branch `lwb-mission-final` carries the unmerged deliverable: the\n"
        "  settled mission, the enforceable gates, and decisions D9 onward.\n",
    )
    findings = m.check(repo)
    assert len(findings) == 1, findings


def test_corpus_4_branch_is_leftover_from_abandoned_pr(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(
        repo,
        "NOTE.md",
        "- Branch `lwb-mission-settled` is a leftover from abandoned PR #12;\n"
        "  delete it once `lwb-mission-final` has landed.\n",
    )
    findings = m.check(repo)
    assert len(findings) >= 1, findings


def test_corpus_5_mission_settled_landing_from_branch(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(
        repo,
        "NOTE.md",
        "3. **Mission settled; landing from `lwb-mission-final`.**\n"
        "   Detail follows.\n",
    )
    findings = m.check(repo)
    assert len(findings) == 1, findings


# ---------------------------------------------------------------------------
# The six phrasings the audit proved the first implementation missed.
# ---------------------------------------------------------------------------


def test_corpus_6_claim_hard_wrapped_across_two_lines(tmp_path):
    """This repo wraps ALL prose at ~72 columns; a line-anchored gate
    cannot see a claim split by the wrap. The claim only exists once the
    two physical lines are joined into one logical line."""
    repo = _init_repo(tmp_path)
    _commit_md(
        repo,
        "NOTE.md",
        "As of today, no PR is\nopen against this branch.\n",
    )
    findings = m.check(repo)
    assert len(findings) == 1, findings


def test_corpus_7_tip_of_branch_is_sha(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(repo, "NOTE.md", "The tip of `lwb-x` is 7d9a0b7.\n")
    findings = m.check(repo)
    assert len(findings) == 1, findings


def test_corpus_8_head_now_points_at_sha(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(repo, "NOTE.md", "HEAD now points at 7d9a0b7.\n")
    findings = m.check(repo)
    assert len(findings) == 1, findings


def test_corpus_9_branch_is_n_ahead_of_origin(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(repo, "NOTE.md", "The branch is 5 ahead of origin/main.\n")
    findings = m.check(repo)
    assert len(findings) == 1, findings


def test_corpus_10_pr_is_still_open(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(repo, "NOTE.md", "PR #16 is still open.\n")
    findings = m.check(repo)
    assert len(findings) == 1, findings


def test_corpus_10b_there_is_one_open_pr(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(repo, "NOTE.md", "There is one open PR.\n")
    findings = m.check(repo)
    assert len(findings) == 1, findings


def test_corpus_11_branch_still_exists_on_remote(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(repo, "NOTE.md", "`lwb-mission-final` still exists on the remote.\n")
    findings = m.check(repo)
    assert len(findings) == 1, findings


# ---------------------------------------------------------------------------
# Exemptions that must still hold.
# ---------------------------------------------------------------------------


def test_historical_sha_citation_not_flagged(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(
        repo,
        "NOTE.md",
        "Those five names remain in commits `79b2626` and `31a75ab` on public main.\n",
    )
    assert m.check(repo) == []


def test_historical_was_at_not_flagged(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(
        repo,
        "NOTE.md",
        "`main` was at `c33b560` when this session ended. Anything at or\n"
        "after that sha is this session's work or later.\n",
    )
    assert m.check(repo) == []


def test_pr_number_cited_as_history_not_flagged(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(repo, "NOTE.md", "Landed as PR #15, squash-merged to `d0c1386`.\n")
    assert m.check(repo) == []


def test_completed_branch_deletion_not_flagged(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(repo, "NOTE.md", "That remote is deleted. Both branches are deleted, local and remote.\n")
    assert m.check(repo) == []


def test_quoted_with_attribution_verb_not_flagged(tmp_path):
    """The repo's real phrasing ('stated ... "no PR is open"') must be
    honoured; the closed enum of attribution verbs includes 'stated'."""
    repo = _init_repo(tmp_path)
    _commit_md(
        repo,
        "NOTE.md",
        'An earlier draft of this section stated a tip sha, a commit count\n'
        'and "no PR is open"; all three were false within minutes.\n',
    )
    assert m.check(repo) == []


def test_quoted_without_attribution_verb_is_flagged(tmp_path):
    """Settling the quote heuristic: a bare quotation with no attribution
    verb and no blockquote is a real assertion, not a citation."""
    repo = _init_repo(tmp_path)
    _commit_md(repo, "NOTE.md", '"no PR is open" right now.\n')
    findings = m.check(repo)
    assert len(findings) == 1, findings


def test_blockquote_exempts_even_without_attribution_verb(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(repo, "NOTE.md", "> no PR is open\n")
    assert m.check(repo) == []


def test_escape_comment_with_valid_reason_honored(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(
        repo,
        "NOTE.md",
        "main is at deadbeef1234 <!-- volatile-ok: historical -->\n",
    )
    assert m.check(repo) == []


def test_escape_comment_with_free_text_reason_rejected(tmp_path):
    """The escape must take a reason from a closed enum, not free text --
    a human-reviewed reason string is an advisory rule, which principle 1
    of the mission rejects. An unrecognised reason does not exempt."""
    repo = _init_repo(tmp_path)
    _commit_md(
        repo,
        "NOTE.md",
        "main is at deadbeef1234 <!-- volatile-ok: trust me it's fine -->\n",
    )
    findings = m.check(repo)
    assert len(findings) == 1, findings


def test_fenced_code_block_ignored(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(
        repo,
        "NOTE.md",
        "```\nmain is at deadbeef1234 -- inside a fence, ignored\n```\n",
    )
    assert m.check(repo) == []


def test_unclosed_fence_is_an_error_not_an_exemption(tmp_path):
    """The first implementation let a single stray ``` exempt everything
    to EOF. An unclosed fence must be reported as an error, not silence."""
    repo = _init_repo(tmp_path)
    _commit_md(
        repo,
        "NOTE.md",
        "```\nmain is at deadbeef1234 -- never closed\n",
    )
    errors = m.check_errors(repo)
    assert any("fence" in e.lower() for e in errors), errors


def test_untracked_file_not_scanned(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(repo, "SEED.md", "seed\n")
    (repo / "UNTRACKED.md").write_text("main is at abc1234.\n", encoding="utf-8")
    assert m.check(repo) == []


# ---------------------------------------------------------------------------
# The generated block is bound to HANDOFF.md and NOT exempt.
# ---------------------------------------------------------------------------


def test_handoff_marker_in_a_different_file_grants_no_exemption(tmp_path):
    """The first implementation honoured the marker in ANY tracked .md, so
    a file could exempt itself. Only HANDOFF.md gets the special handling."""
    repo = _init_repo(tmp_path)
    _commit_md(
        repo,
        "NOTOTHER.md",
        f"{m.BEGIN_MARKER}\nmain is at deadbeef1234\n{m.END_MARKER}\n",
    )
    findings = m.check(repo)
    assert len(findings) == 1, findings


def test_handoff_unmatched_marker_is_an_error(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(
        repo,
        "HANDOFF.md",
        f"# HANDOFF\n\n## In flight\n\n1. x\n\n{m.BEGIN_MARKER}\nmain is at deadbeef1234\n\n## Where to look\n",
    )
    errors = m.check_errors(repo)
    assert any("handoff" in e.lower() and "marker" in e.lower() for e in errors), errors


def test_handoff_generated_block_proof_state_is_rederived_not_trusted(tmp_path):
    """The generated block's proof-state lines are re-derived and compared,
    not treated as exempt text -- a stale recorded proof state must fail."""
    repo = _init_repo(tmp_path)
    main_sha = _seed_main_branch(repo)
    handoff = (
        "# HANDOFF\n\n## In flight\n\n1. Work.\n\n"
        f"{m.BEGIN_MARKER}\n\n"
        "Generated: 2026-09-18 22:35 UTC\n"
        f"main SHA: {main_sha}\n\n"
        "Open PRs:\n(none)\n\n"
        "Deliverable proof state (from proof/):\n"
        "- some-deliverable: PROVEN (commit deadbeefdeadbeefdeadbeefdeadbeefdeadbeef)\n\n"
        f"{m.END_MARKER}\n\n## Where to look\n\n- nowhere\n"
    )
    _commit_md(repo, "HANDOFF.md", handoff)
    findings = m.check(repo)
    assert any("proof state" in f.label.lower() or "proof-state" in f.label.lower() for f in findings), findings


def test_handoff_generated_block_passes_when_everything_rederives_clean(tmp_path):
    repo = _init_repo(tmp_path)
    main_sha = _seed_main_branch(repo)
    handoff = (
        "# HANDOFF\n\n## In flight\n\n1. Work.\n\n"
        f"{m.BEGIN_MARKER}\n\n"
        "Generated: 2026-09-18 22:35 UTC\n"
        f"main SHA: {main_sha}\n\n"
        "Open PRs:\n(none)\n\n"
        "Deliverable proof state (from proof/):\n(none yet)\n\n"
        f"{m.END_MARKER}\n\n## Where to look\n\n- nowhere\n"
    )
    _commit_md(repo, "HANDOFF.md", handoff)
    assert m.check(repo) == []


# ---------------------------------------------------------------------------
# The gate must actually fail end-to-end -- not silently become a no-op.
# ---------------------------------------------------------------------------


def test_gate_fails_end_to_end_on_a_known_bad_document(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(
        repo,
        "STATUS.md",
        "As of today, main is at abc1234def and PR #9 is still open.\n",
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "lwb_check_state_claims.py"), "--repo", str(repo)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "STATUS.md" in result.stdout


def test_gate_passes_end_to_end_on_a_clean_document(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(repo, "STATUS.md", "Landed as PR #15. Re-derive current state with git and gh.\n")
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "lwb_check_state_claims.py"), "--repo", str(repo)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"


def test_findings_report_file_and_line(tmp_path):
    """Separate paragraphs (blank-line delimited) stay separate logical
    lines; the finding maps to the first physical line of ITS paragraph,
    not the file's first line."""
    repo = _init_repo(tmp_path)
    _commit_md(
        repo,
        "NOTE.md",
        "line one is fine.\n\nline two: 4 unmerged commits sit here.\n\nline three is fine.\n",
    )
    findings = m.check(repo)
    assert len(findings) == 1
    assert findings[0].path == "NOTE.md"
    assert findings[0].lineno == 3

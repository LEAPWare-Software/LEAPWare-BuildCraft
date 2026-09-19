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

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import lwb_check_state_claims as m  # noqa: E402
import lwb_handoff  # noqa: E402


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
    """A genuinely stale/wrong recorded sha: a REAL commit that exists in
    this repo's history but was never main -- a sibling of `work`, not an
    ancestor of `main`. (An earlier version of this test used a
    fabricated hex string that was never a real object at all; under the
    ancestor-aware check added to close the squash-merge defect, that
    case is UNDETERMINABLE rather than a definite lie -- see the
    'main-sha-ancestor-aware' tests below. This test needs the stronger,
    resolvable case: a real sha git can prove is NOT an ancestor.)"""
    repo = _init_repo(tmp_path)
    _seed_main_branch(repo)
    subprocess.run(["git", "checkout", "-b", "sibling"], cwd=repo, check=True)
    (repo / "sibling.txt").write_text("sibling\n", encoding="utf-8")
    subprocess.run(["git", "add", "sibling.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "sibling"], cwd=repo, check=True)
    sibling_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    subprocess.run(["git", "checkout", "work"], cwd=repo, check=True)
    handoff = (
        "# HANDOFF\n\n## In flight\n\n1. Work.\n\n"
        f"{m.BEGIN_MARKER}\n\n"
        "Generated: 2026-09-18 22:35 UTC\n"
        f"main SHA: {sibling_sha}\n\n"
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
        "Deliverable proof state (from proof/):\n0/0 proven\n(none yet)\n\n"
        f"{m.END_MARKER}\n\n## Where to look\n\n- nowhere\n"
    )
    _commit_md(repo, "HANDOFF.md", handoff)
    assert m.check(repo) == []


# ---------------------------------------------------------------------------
# Coupling: this script's re-derivation of "Deliverable proof state" MUST
# match scripts/lwb_handoff.py's own generator byte for byte, for every
# shape proof/ can take. Written so it fails if either side changes alone
# -- `_derive_proof_state_lines` now just calls `lwb_handoff._proof_state_
# lines` directly, so this test also guards against a future edit that
# re-introduces a second, independent copy of the derivation.
# ---------------------------------------------------------------------------


def _write_proof_record(proof_dir: Path, name: str, proven: bool = True) -> None:
    if proven:
        body = (
            f'{{"deliverable": "{name}", "author": "a", "checked_by": "b", '
            '"commit": "abc1234", "commands": [], "mutations": [], "unproven": []}'
        )
    else:
        body = f'{{"deliverable": "{name}", "author": "a", "checked_by": "b"}}'
    (proof_dir / f"{name}.json").write_text(body, encoding="utf-8")


def test_derivation_matches_generator_zero_records(tmp_path):
    repo = _init_repo(tmp_path)
    generator = lwb_handoff._proof_state_lines(repo / "proof")
    derived = m._derive_proof_state_lines(repo)
    assert derived == generator == ["0/0 proven", "(none yet)"]


def test_derivation_matches_generator_all_proven(tmp_path):
    repo = _init_repo(tmp_path)
    proof_dir = repo / "proof"
    proof_dir.mkdir()
    _write_proof_record(proof_dir, "one", proven=True)
    _write_proof_record(proof_dir, "two", proven=True)

    generator = lwb_handoff._proof_state_lines(proof_dir)
    derived = m._derive_proof_state_lines(repo)

    assert derived == generator == ["2/2 proven", "(all proven; none outstanding)"]


def test_derivation_matches_generator_some_unproven(tmp_path):
    repo = _init_repo(tmp_path)
    proof_dir = repo / "proof"
    proof_dir.mkdir()
    _write_proof_record(proof_dir, "one", proven=True)
    _write_proof_record(proof_dir, "broken", proven=False)

    generator = lwb_handoff._proof_state_lines(proof_dir)
    derived = m._derive_proof_state_lines(repo)

    assert derived == generator
    assert derived[0] == "1/2 proven"
    assert any("broken" in line for line in derived)


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


# ---------------------------------------------------------------------------
# Evasions found by adversarial review of PR (head e7b33d8) -- each fixed
# below was confirmed by direct probe: it produced zero findings when it
# should not have (or, for the escape leak, produced zero findings on a
# claim that was never actually escaped).
# ---------------------------------------------------------------------------


def test_escape_comment_does_not_leak_across_joined_paragraph(tmp_path):
    """The worst evasion: a `volatile-ok` comment anywhere in a hard-wrapped
    paragraph used to exempt the WHOLE joined logical line, so one
    legitimately-escaped clause shielded an unrelated false claim in the
    same paragraph. The escape must be scoped to the physical line it
    appears on."""
    repo = _init_repo(tmp_path)
    _commit_md(
        repo,
        "NOTE.md",
        "- Some legitimate illustrative example. <!-- volatile-ok: illustrative -->\n"
        "  main SHA: deadbeef1234, a live stale claim in the same paragraph.\n",
    )
    findings = m.check(repo)
    assert any("SHA" in f.label for f in findings), findings


def test_escape_on_its_own_line_still_exempts_only_that_line(tmp_path):
    """The positive control for the fix above: the escape must still work
    when the comment and the claim share a physical line."""
    repo = _init_repo(tmp_path)
    _commit_md(
        repo,
        "NOTE.md",
        "- main SHA: deadbeef1234 <!-- volatile-ok: illustrative -->\n"
        "  A second, unrelated sentence with nothing volatile in it.\n",
    )
    assert m.check(repo) == []


def test_spelled_out_commit_count_is_flagged(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(repo, "NOTE.md", "This branch holds six commits on top of main.\n")
    findings = m.check(repo)
    assert len(findings) == 1, findings


def test_spelled_out_zero_open_pull_requests_is_flagged(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(repo, "NOTE.md", "There are zero open pull requests right now.\n")
    findings = m.check(repo)
    assert len(findings) >= 1, findings


def test_capitalized_word_number_open_prs_is_flagged(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(repo, "NOTE.md", "Ten open PRs remain.\n")
    findings = m.check(repo)
    assert len(findings) == 1, findings


def test_table_row_stale_main_sha_is_flagged(tmp_path):
    repo = _init_repo(tmp_path)
    _seed_main_branch(repo)
    _commit_md(
        repo,
        "NOTE.md",
        "| Field | Value |\n| --- | --- |\n"
        "| main SHA | deadbeefdeadbeefdeadbeefdeadbeefdeadbeef |\n",
    )
    findings = m.check(repo)
    assert len(findings) >= 1, findings


def test_table_row_branch_still_exists_is_flagged(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(
        repo,
        "NOTE.md",
        "| Branch | Status |\n| --- | --- |\n"
        "| `foo` | still exists on the remote |\n",
    )
    findings = m.check(repo)
    assert len(findings) >= 1, findings


def test_backticked_sha_label_is_flagged(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(repo, "NOTE.md", "`main` SHA: `deadbeef1234`\n")
    findings = m.check(repo)
    assert len(findings) == 1, findings


def test_reordered_currently_at_sha_on_main_is_flagged(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(repo, "NOTE.md", "We are currently at deadbeef1234 on main.\n")
    findings = m.check(repo)
    assert len(findings) == 1, findings


def test_shorthand_main_colon_sha_is_flagged(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(repo, "NOTE.md", "main: deadbeef1234 (verified).\n")
    findings = m.check(repo)
    assert len(findings) == 1, findings


# ---------------------------------------------------------------------------
# Second adversarial round: Unicode-normalisation evasions. NFKC closes the
# fullwidth colon and the zero-width space; it does NOT close an en dash
# (a genuinely different character) or a Cyrillic homoglyph (no confusable
# folding in stdlib) -- see the module docstring for why those two stay open
# by design, not by oversight.
# ---------------------------------------------------------------------------


def test_fullwidth_colon_sha_label_is_flagged(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(repo, "NOTE.md", "main SHA： deadbeef1234\n")  # U+FF1A fullwidth colon
    findings = m.check(repo)
    assert len(findings) == 1, findings


def test_zero_width_space_in_label_is_flagged(tmp_path):
    repo = _init_repo(tmp_path)
    _commit_md(repo, "NOTE.md", "main​SHA: deadbeef1234\n")  # U+200B zero-width space
    findings = m.check(repo)
    assert len(findings) == 1, findings


def test_word_joiner_in_label_is_flagged(tmp_path):
    """U+2060 WORD JOINER is category Cf, same as the four originally-named
    zero-width code points, but was not one of the four the old regex
    enumerated -- so a label hidden behind it evaded detection until the
    strip switched from enumerating code points to matching the Cf
    category."""
    repo = _init_repo(tmp_path)
    _commit_md(repo, "NOTE.md", "main⁠SHA: deadbeef1234\n")  # U+2060 word joiner
    findings = m.check(repo)
    assert len(findings) == 1, findings


def test_soft_hyphen_in_label_is_flagged(tmp_path):
    """U+00AD SOFT HYPHEN is category Cf; not one of the four originally
    named code points."""
    repo = _init_repo(tmp_path)
    _commit_md(repo, "NOTE.md", "main­SHA: deadbeef1234\n")  # U+00AD soft hyphen
    findings = m.check(repo)
    assert len(findings) == 1, findings


def test_mongolian_vowel_separator_in_label_is_flagged(tmp_path):
    """U+180E MONGOLIAN VOWEL SEPARATOR is category Cf; not one of the four
    originally named code points."""
    repo = _init_repo(tmp_path)
    _commit_md(repo, "NOTE.md", "main᠎SHA: deadbeef1234\n")  # U+180E
    findings = m.check(repo)
    assert len(findings) == 1, findings


def test_en_dash_for_colon_remains_undetected(tmp_path):
    """Documented residue, not a bug: en dash is a genuinely different
    character, not an NFKC equivalent of a colon."""
    repo = _init_repo(tmp_path)
    _commit_md(repo, "NOTE.md", "main SHA– deadbeef1234\n")  # U+2013 en dash
    assert m.check(repo) == []


def test_cyrillic_homoglyph_remains_undetected(tmp_path):
    """Documented residue, not a bug: stdlib has no confusable folding."""
    repo = _init_repo(tmp_path)
    _commit_md(repo, "NOTE.md", "mаin SHA: deadbeef1234\n")  # U+0430 Cyrillic а
    assert m.check(repo) == []


def test_escape_still_binds_correctly_when_paragraph_has_nfkc_rewrite(tmp_path):
    """The critical interaction: NFKC changes string length, so the
    escape's physical-line binding (built on char_linenos) must not
    desync. U+FF1A (fullwidth colon) does NOT exercise this -- it
    normalises one-to-one to ASCII ':', so a test built on it alone never
    actually changes any line's length despite its docstring claiming
    otherwise. U+FB01 (the "fi" ligature) does: NFKC expands it to the two
    ASCII characters "fi", so line 1 here genuinely grows by one character
    under normalisation. Line 1 is legitimately escaped; line 2 is a live,
    unescaped SHA claim in the SAME paragraph and must still be flagged,
    not shielded by line 1's escape -- which it would be if the length
    change desynced the char-to-lineno map."""
    repo = _init_repo(tmp_path)
    _commit_md(
        repo,
        "NOTE.md",
        "- A note about a ﬁle format, purely descriptive, nothing"
        " volatile here. <!-- volatile-ok: illustrative -->\n"
        "  main SHA: deadbeef1234, a live stale claim in the same paragraph.\n",
    )
    findings = m.check(repo)
    assert any("SHA" in f.label for f in findings), findings


# ---------------------------------------------------------------------------
# THE DEFECT: `main SHA:` was compared for EQUALITY against live main. After
# a squash merge, live main becomes a brand-new merge commit that did not
# exist when HANDOFF.md's generated block was written, so the recorded sha
# can never equal live main again -- the gate could not pass post-merge, on
# the very PR whose subject was gates that cannot fail. The fix: an
# ANCESTOR of live main is a true historical claim (report it, don't hide
# it); anything else is either a genuine lie (FAIL) or undeterminable
# (report that, never silently pass).
#
# Built in throwaway repos under the system temp dir per the task brief,
# NOT against this repo's own history and NOT via the shared tmp_path
# fixture (which resolves elsewhere under that same temp root).
# ---------------------------------------------------------------------------

import shutil
import stat
import tempfile

# Throwaway repos for these tests, per the task brief: a dedicated
# subdirectory of the system temp dir, NOT this repo's own history and
# NOT the shared tmp_path fixture. Built from `tempfile.gettempdir()`
# rather than a hard-coded path so this file never commits a
# machine-specific absolute path (that is exactly what
# `lwb_check_env_leak.py`'s "Windows drive letter" gate exists to catch).
_KSTMP_ROOT = Path(tempfile.gettempdir()) / "lwb-ancestor-tests"


def _force_rmtree(path: Path) -> None:
    """Git on Windows marks objects under `.git/objects` read-only;
    plain `shutil.rmtree` then fails with PermissionError. Clear the
    read-only bit on access errors and retry, exactly like the standard
    library's own documented workaround."""
    def _on_error(func, target, exc_info):
        try:
            import os

            os.chmod(target, stat.S_IWRITE)
            func(target)
        except OSError:
            pass

    shutil.rmtree(path, onerror=_on_error)


def _kstmp_repo(name: str) -> Path:
    root = _KSTMP_ROOT / name
    if root.exists():
        _force_rmtree(root)
    root.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    return root


def _commit_file(repo: Path, name: str, text: str) -> str:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", name], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", f"add {name}"], cwd=repo, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def _handoff_text(recorded_sha: str) -> str:
    return (
        "# HANDOFF\n\n## In flight\n\n1. Work.\n\n"
        f"{m.BEGIN_MARKER}\n\n"
        "Generated: 2026-09-18 22:35 UTC\n"
        f"main SHA: {recorded_sha}\n\n"
        "Open PRs:\n(none)\n\n"
        "Deliverable proof state (from proof/):\n0/0 proven\n(none yet)\n\n"
        f"{m.END_MARKER}\n\n## Where to look\n\n- nowhere yet\n"
    )


def test_ancestor_recorded_sha_equal_to_live_main_passes_no_info(tmp_path):
    """Equal case: unchanged behaviour, and NO ancestor-info line -- the
    "info" is specifically for the "predates live main" case, not every
    pass."""
    repo = _kstmp_repo("equal")
    try:
        subprocess.run(["git", "checkout", "-b", "main"], cwd=repo, check=True)
        sha = _commit_file(repo, "a.txt", "a\n")
        # HANDOFF.md is committed on a SEPARATE branch that records main's
        # unmoved tip -- exactly test_corpus_2's `_seed_main_branch`
        # pattern. Committing the recording ONTO main itself is
        # self-referential and unbuildable (the file cannot already
        # contain the sha of the commit that first introduces it).
        subprocess.run(["git", "checkout", "-b", "work"], cwd=repo, check=True)
        (repo / "HANDOFF.md").write_text(_handoff_text(sha), encoding="utf-8")
        subprocess.run(["git", "add", "HANDOFF.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "handoff"], cwd=repo, check=True)
        findings, infos, errors = m._check_all(repo)
        assert findings == [], findings
        assert not any("ancestor" in i.text.lower() or "predates" in i.text.lower() for i in infos), infos
    finally:
        _force_rmtree(repo)


def test_ancestor_recorded_sha_is_ancestor_of_live_main_passes_with_info(tmp_path):
    """The actual squash-merge shape: HANDOFF.md was committed recording
    main's tip at that moment (sha A); main then moved on (fast-forwarded
    to sha B, A is an ancestor of B). This MUST pass -- A really was main
    -- but must not pass silently: the info line must name both shas."""
    repo = _kstmp_repo("ancestor")
    try:
        subprocess.run(["git", "checkout", "-b", "main"], cwd=repo, check=True)
        sha_a = _commit_file(repo, "a.txt", "a\n")
        # Record main's tip (sha_a) on a SEPARATE branch, exactly like
        # _seed_main_branch -- then advance the real `main` ref past it
        # (a stand-in for the squash-merge commit that made the recorded
        # sha unreachable-by-equality but still an ancestor).
        subprocess.run(["git", "checkout", "-b", "work"], cwd=repo, check=True)
        (repo / "HANDOFF.md").write_text(_handoff_text(sha_a), encoding="utf-8")
        subprocess.run(["git", "add", "HANDOFF.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "handoff"], cwd=repo, check=True)
        subprocess.run(["git", "checkout", "main"], cwd=repo, check=True)
        sha_b = _commit_file(repo, "b.txt", "b\n")
        subprocess.run(["git", "checkout", "work"], cwd=repo, check=True)
        findings, infos, errors = m._check_all(repo)
        assert findings == [], findings
        matching = [
            i for i in infos
            if sha_a[:7] in i.text and sha_b[:7] in i.text
        ]
        assert matching, infos
    finally:
        _force_rmtree(repo)


def test_ancestor_recorded_sha_unrelated_fails(tmp_path):
    """Divergent history: the recorded sha is neither equal to nor an
    ancestor of live main -- a sibling branch commit that was never main.
    This is a genuinely false claim and must FAIL."""
    repo = _kstmp_repo("unrelated")
    try:
        subprocess.run(["git", "checkout", "-b", "main"], cwd=repo, check=True)
        _commit_file(repo, "base.txt", "base\n")
        subprocess.run(["git", "checkout", "-b", "side"], cwd=repo, check=True)
        sha_side = _commit_file(repo, "side.txt", "side\n")
        subprocess.run(["git", "checkout", "main"], cwd=repo, check=True)
        _commit_file(repo, "main2.txt", "main2\n")
        (repo / "HANDOFF.md").write_text(_handoff_text(sha_side), encoding="utf-8")
        subprocess.run(["git", "add", "HANDOFF.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "handoff"], cwd=repo, check=True)
        findings, infos, errors = m._check_all(repo)
        assert any("main sha" in f.label.lower() for f in findings), findings
    finally:
        _force_rmtree(repo)


def test_ancestor_recorded_sha_does_not_exist_is_a_failure(tmp_path):
    """THE FIX TO THE FIX: an independent reviewer proved the original
    ancestor-aware rewrite made this WORSE than the bug it replaced -- a
    fabricated/nonexistent sha (or `TBD`, `0`, empty ...) exited 0 and
    printed "check passed" on every probe. A recorded sha that does not
    resolve to live main or live main's first parent is a FAILURE in a
    full clone, full stop -- this test used to assert the opposite and
    thereby locked the defect in."""
    repo = _kstmp_repo("nonexistent")
    try:
        subprocess.run(["git", "checkout", "-b", "main"], cwd=repo, check=True)
        _commit_file(repo, "a.txt", "a\n")
        fake_sha = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
        (repo / "HANDOFF.md").write_text(_handoff_text(fake_sha), encoding="utf-8")
        subprocess.run(["git", "add", "HANDOFF.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "handoff"], cwd=repo, check=True)
        findings, infos, errors = m._check_all(repo)
        assert any("main sha" in f.label.lower() for f in findings), findings
        assert any(fake_sha in f.text for f in findings), findings
    finally:
        _force_rmtree(repo)


def test_ancestor_shallow_clone_is_a_failure_not_a_silent_pass(tmp_path):
    """A shallow clone cannot resolve a commit truncated out of its
    history, so a recorded sha that is not live main itself cannot be
    verified there. The reviewer's words: "report exit non-zero when it
    is shallow" -- not a silent pass, and not a bare UNVERIFIABLE info
    line either."""
    origin = _kstmp_repo("shallow-origin")
    shallow = _KSTMP_ROOT / "shallow-clone"
    try:
        subprocess.run(["git", "checkout", "-b", "main"], cwd=origin, check=True)
        sha_old = _commit_file(origin, "a.txt", "a\n")
        sha_new = _commit_file(origin, "b.txt", "b\n")
        if shallow.exists():
            _force_rmtree(shallow)
        subprocess.run(
            ["git", "clone", "-q", "--depth", "1", "--branch", "main", f"file://{origin.as_posix()}", str(shallow)],
            check=True,
        )
        (shallow / "HANDOFF.md").write_text(_handoff_text(sha_old), encoding="utf-8")
        subprocess.run(["git", "add", "HANDOFF.md"], cwd=shallow, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=shallow, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=shallow, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "handoff"], cwd=shallow, check=True)
        findings, infos, errors = m._check_all(shallow)
        assert any("main sha" in f.label.lower() and "shallow" in f.label.lower() for f in findings), findings
    finally:
        _force_rmtree(origin)
        _force_rmtree(shallow)


def test_ancestor_shallow_clone_recorded_sha_equal_to_live_still_passes(tmp_path):
    """The one thing a shallow clone CAN verify: whether the recorded
    value is live main's own sha, since live main (HEAD) is always
    present even at depth 1."""
    origin = _kstmp_repo("shallow-equal-origin")
    shallow = _KSTMP_ROOT / "shallow-equal-clone"
    try:
        subprocess.run(["git", "checkout", "-b", "main"], cwd=origin, check=True)
        sha = _commit_file(origin, "a.txt", "a\n")
        if shallow.exists():
            _force_rmtree(shallow)
        subprocess.run(
            ["git", "clone", "-q", "--depth", "1", "--branch", "main", f"file://{origin.as_posix()}", str(shallow)],
            check=True,
        )
        (shallow / "HANDOFF.md").write_text(_handoff_text(sha), encoding="utf-8")
        subprocess.run(["git", "add", "HANDOFF.md"], cwd=shallow, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=shallow, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=shallow, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "handoff"], cwd=shallow, check=True)
        findings, infos, errors = m._check_all(shallow)
        assert not any("main sha" in f.label.lower() for f in findings), findings
    finally:
        _force_rmtree(origin)
        _force_rmtree(shallow)


def test_ancestor_root_commit_is_now_a_failure(tmp_path):
    """The root commit is an ancestor of live main, but not live main's
    FIRST PARENT once main has moved on more than one commit -- the old
    "any ancestor" rule let a years-stale HANDOFF.md pass forever. Under
    the tightened equal-or-first-parent rule this must FAIL."""
    repo = _kstmp_repo("root-commit-stale")
    try:
        subprocess.run(["git", "checkout", "-b", "main"], cwd=repo, check=True)
        root_sha = _commit_file(repo, "a.txt", "a\n")
        _commit_file(repo, "b.txt", "b\n")
        _commit_file(repo, "c.txt", "c\n")
        (repo / "HANDOFF.md").write_text(_handoff_text(root_sha), encoding="utf-8")
        subprocess.run(["git", "add", "HANDOFF.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "handoff"], cwd=repo, check=True)
        findings, infos, errors = m._check_all(repo)
        assert any("main sha" in f.label.lower() for f in findings), findings
    finally:
        _force_rmtree(repo)


def test_ancestor_recorded_sha_is_short_prefix_of_live_passes(tmp_path):
    """A 7-char prefix of live main's own sha must still pass."""
    repo = _kstmp_repo("prefix-of-live")
    try:
        subprocess.run(["git", "checkout", "-b", "main"], cwd=repo, check=True)
        sha = _commit_file(repo, "a.txt", "a\n")
        subprocess.run(["git", "checkout", "-b", "work"], cwd=repo, check=True)
        (repo / "HANDOFF.md").write_text(_handoff_text(sha[:7]), encoding="utf-8")
        subprocess.run(["git", "add", "HANDOFF.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "handoff"], cwd=repo, check=True)
        findings, infos, errors = m._check_all(repo)
        assert not any("main sha" in f.label.lower() for f in findings), findings
    finally:
        _force_rmtree(repo)


def test_ancestor_recorded_sha_is_short_prefix_of_live_parent_passes(tmp_path):
    """A 7-char prefix of live main's FIRST PARENT must also pass, and
    must be reported with a git-verified INFO line, not UNVERIFIABLE --
    git proved this one, it did not merely fail to disprove it."""
    repo = _kstmp_repo("prefix-of-parent")
    try:
        subprocess.run(["git", "checkout", "-b", "main"], cwd=repo, check=True)
        sha_a = _commit_file(repo, "a.txt", "a\n")
        subprocess.run(["git", "checkout", "-b", "work"], cwd=repo, check=True)
        (repo / "HANDOFF.md").write_text(_handoff_text(sha_a[:7]), encoding="utf-8")
        subprocess.run(["git", "add", "HANDOFF.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "handoff"], cwd=repo, check=True)
        subprocess.run(["git", "checkout", "main"], cwd=repo, check=True)
        _commit_file(repo, "b.txt", "b\n")
        subprocess.run(["git", "checkout", "work"], cwd=repo, check=True)
        findings, infos, errors = m._check_all(repo)
        assert findings == [], findings
        assert any(i.prefix != "UNVERIFIABLE" for i in infos if sha_a[:7] in i.text), infos
        assert not any(i.prefix == "UNVERIFIABLE" and sha_a[:7] in i.text for i in infos), infos
    finally:
        _force_rmtree(repo)


def test_ancestor_shallow_clone_correct_first_parent_is_undeterminable_not_stale(tmp_path):
    """THE FIX TO THE SECOND FIX: measured by an independent reviewer in a
    real depth-1 shallow clone. The recorded value genuinely IS live
    main's first parent (a full clone proves it), but `main^1` cannot be
    resolved at depth 1 (`git rev-parse origin/main^1` -> "fatal:
    ambiguous argument"). The gate must NOT call this "stale main SHA" --
    that accuses a correct file of a lie the gate never actually proved.
    It must still exit non-zero (a shallow clone can never confirm the
    claim either), but under a distinct, honest reason."""
    origin = _kstmp_repo("shallow-correct-origin")
    shallow = _KSTMP_ROOT / "shallow-correct-clone"
    try:
        subprocess.run(["git", "checkout", "-b", "main"], cwd=origin, check=True)
        sha_parent = _commit_file(origin, "a.txt", "a\n")
        sha_tip = _commit_file(origin, "b.txt", "b\n")
        if shallow.exists():
            _force_rmtree(shallow)
        subprocess.run(
            ["git", "clone", "-q", "--depth", "1", "--branch", "main", f"file://{origin.as_posix()}", str(shallow)],
            check=True,
        )
        assert (
            subprocess.run(
                ["git", "rev-parse", "--is-shallow-repository"],
                cwd=shallow, capture_output=True, text=True, check=True,
            ).stdout.strip() == "true"
        )
        unresolvable = subprocess.run(
            ["git", "rev-parse", "origin/main^1"], cwd=shallow, capture_output=True, text=True, check=False,
        )
        assert unresolvable.returncode != 0, "test setup invalid: main^1 resolved at depth 1"
        (shallow / "HANDOFF.md").write_text(_handoff_text(sha_parent), encoding="utf-8")
        subprocess.run(["git", "add", "HANDOFF.md"], cwd=shallow, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=shallow, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=shallow, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "handoff"], cwd=shallow, check=True)

        findings, infos, errors = m._check_all(shallow)
        assert not any("stale" in f.label.lower() for f in findings), findings
        assert any(
            "main sha" in f.label.lower() and "undeterminable" in f.label.lower() and "shallow" in f.label.lower()
            for f in findings
        ), findings
    finally:
        _force_rmtree(origin)
        _force_rmtree(shallow)


@pytest.mark.parametrize("bad_value", ["TBD", "--help", "origin/main~50", "", "0"])
def test_ancestor_invalid_recorded_values_fail_without_calling_git(tmp_path, monkeypatch, bad_value):
    """Item 1 of the reviewer's prescription: the recorded value must be
    validated as 7-40 hex characters BEFORE git is ever consulted. None of
    these five probe values is valid hex of that length, so each must be
    a FAILURE and git must never be invoked to decide it."""
    repo = _kstmp_repo(f"invalid-{abs(hash(bad_value))}")
    try:
        subprocess.run(["git", "checkout", "-b", "main"], cwd=repo, check=True)
        _commit_file(repo, "a.txt", "a\n")
        (repo / "HANDOFF.md").write_text(_handoff_text(bad_value), encoding="utf-8")
        subprocess.run(["git", "add", "HANDOFF.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "handoff"], cwd=repo, check=True)

        real_run = subprocess.run
        calls = []

        def _tracking_run(cmd, *args, **kwargs):
            calls.append(cmd)
            return real_run(cmd, *args, **kwargs)

        monkeypatch.setattr(m.subprocess, "run", _tracking_run)
        findings, infos, errors = m._check_all(repo)
        assert any("main sha" in f.label.lower() for f in findings), findings
        # git must never be asked to resolve THIS invalid value.
        assert not any(bad_value and bad_value in " ".join(c) for c in calls), calls
    finally:
        _force_rmtree(repo)


def test_ancestor_missing_git_degrades_honestly(tmp_path, monkeypatch):
    """If the ancestry check itself cannot run at all (git unavailable),
    the low-level helper must return "unknown", following the same
    FileNotFoundError-tolerant pattern `_pr_state` already uses -- not
    raise, and not report a pass."""
    repo = _kstmp_repo("missing-git")
    try:
        subprocess.run(["git", "checkout", "-b", "main"], cwd=repo, check=True)
        sha_a = _commit_file(repo, "a.txt", "a\n")
        sha_b = _commit_file(repo, "b.txt", "b\n")

        def _raise(*args, **kwargs):
            raise FileNotFoundError("git not found")

        monkeypatch.setattr(m.subprocess, "run", _raise)
        result = m._merge_base_is_ancestor(repo, sha_a, sha_b)
        assert result is None
    finally:
        _force_rmtree(repo)


def test_table_row_split_across_two_lines_remains_undetected(tmp_path):
    """Documented evasion, not fixed: a table row is flushed as its own
    logical line and never joined with the next, so a label on one row
    and its value on the next land in unrelated logical lines. Joining
    table rows with arbitrary following lines would produce false
    positives across every table in the repo."""
    repo = _init_repo(tmp_path)
    _commit_md(
        repo,
        "NOTE.md",
        "| main SHA |\n9463214739b90a6de1ae0b384fdc8ac2b1e6e40c |\n",
    )
    assert m.check(repo) == []


# ---------------------------------------------------------------------------
# Open-PR post-merge class: the SECOND instance of the same structural bug
# the `main SHA:` field already fixed (reviews/22/independent-verifier.json
# finding 4). A PR listed as open in the generated block is the EXPECTED
# state, not a lie, exactly when that PR's own merge is what published the
# document -- i.e. its merge commit is live main or live main's first
# parent. Mirrors the `main SHA:` branch's rule precisely, via the same
# `_sha_matches` helper, rather than a second looser comparison.
# ---------------------------------------------------------------------------


def _handoff_text_with_pr(recorded_main_sha: str, pr_number: int, pr_desc: str) -> str:
    return (
        "# HANDOFF\n\n## In flight\n\n1. Work.\n\n"
        f"{m.BEGIN_MARKER}\n\n"
        "Generated: 2026-09-18 22:35 UTC\n"
        f"main SHA: {recorded_main_sha}\n\n"
        "Open PRs:\n"
        f"#{pr_number} {pr_desc}\n\n"
        "Deliverable proof state (from proof/):\n0/0 proven\n(none yet)\n\n"
        f"{m.END_MARKER}\n\n## Where to look\n\n- nowhere yet\n"
    )


def test_pr_merged_at_live_main_passes_with_git_verified_info(tmp_path, monkeypatch):
    """The exact bug reproduced on main right now: PR #22's own merge is
    what published this HANDOFF.md, so its merge commit IS live main.
    That must pass with a git-verified INFO, not fail as stale."""
    repo = _kstmp_repo("pr-merged-at-live-main")
    try:
        subprocess.run(["git", "checkout", "-b", "main"], cwd=repo, check=True)
        sha = _commit_file(repo, "a.txt", "a\n")
        subprocess.run(["git", "checkout", "-b", "work"], cwd=repo, check=True)
        (repo / "HANDOFF.md").write_text(
            _handoff_text_with_pr(sha, 22, "The state-claim gate could never pass after a merge (lwb-postmerge-gate)"),
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "HANDOFF.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "handoff"], cwd=repo, check=True)

        monkeypatch.setattr(m, "_pr_state", lambda repo, n: "MERGED")
        monkeypatch.setattr(m, "_pr_merge_commit", lambda repo, n: sha)

        findings, infos, errors = m._check_all(repo)
        assert findings == [], findings
        assert any(
            "22" in i.text and "live main itself" in i.text and i.prefix == "INFO (git-verified)"
            for i in infos
        ), infos
    finally:
        _force_rmtree(repo)


def test_pr_merged_at_live_main_first_parent_passes_with_git_verified_info(tmp_path, monkeypatch):
    """A squash merge of some OTHER PR landed after this PR's merge, so
    live main has advanced one commit past this PR's merge commit -- the
    merge commit is live main's first parent, not live main itself. Still
    the expected post-merge state, still an INFO, not a FAIL."""
    repo = _kstmp_repo("pr-merged-at-live-parent")
    try:
        subprocess.run(["git", "checkout", "-b", "main"], cwd=repo, check=True)
        sha_a = _commit_file(repo, "a.txt", "a\n")
        subprocess.run(["git", "checkout", "-b", "work"], cwd=repo, check=True)
        (repo / "HANDOFF.md").write_text(
            _handoff_text_with_pr(sha_a, 22, "Some PR (some-branch)"), encoding="utf-8"
        )
        subprocess.run(["git", "add", "HANDOFF.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "handoff"], cwd=repo, check=True)
        subprocess.run(["git", "checkout", "main"], cwd=repo, check=True)
        _commit_file(repo, "b.txt", "b\n")
        subprocess.run(["git", "checkout", "work"], cwd=repo, check=True)

        monkeypatch.setattr(m, "_pr_state", lambda repo, n: "MERGED")
        monkeypatch.setattr(m, "_pr_merge_commit", lambda repo, n: sha_a)

        findings, infos, errors = m._check_all(repo)
        assert findings == [], findings
        assert any(
            "22" in i.text and "first parent" in i.text and i.prefix == "INFO (git-verified)"
            for i in infos
        ), infos
    finally:
        _force_rmtree(repo)


def test_pr_merged_several_commits_back_fails_as_stale(tmp_path, monkeypatch):
    """A PR merged several commits before live main -- genuinely stale,
    not the post-merge special case. Its merge commit is neither live
    main nor live main's first parent, so it must still FAIL."""
    repo = _kstmp_repo("pr-merged-several-back")
    try:
        subprocess.run(["git", "checkout", "-b", "main"], cwd=repo, check=True)
        sha_a = _commit_file(repo, "a.txt", "a\n")
        sha_b = _commit_file(repo, "b.txt", "b\n")
        sha_c = _commit_file(repo, "c.txt", "c\n")
        subprocess.run(["git", "checkout", "-b", "work"], cwd=repo, check=True)
        (repo / "HANDOFF.md").write_text(
            _handoff_text_with_pr(sha_c, 9, "An old PR (old-branch)"), encoding="utf-8"
        )
        subprocess.run(["git", "add", "HANDOFF.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "handoff"], cwd=repo, check=True)

        monkeypatch.setattr(m, "_pr_state", lambda repo, n: "MERGED")
        monkeypatch.setattr(m, "_pr_merge_commit", lambda repo, n: sha_a)

        findings, infos, errors = m._check_all(repo)
        assert any(
            "stale open-PR listing" in f.label and "9" in f.text and "MERGED" in f.text
            for f in findings
        ), findings
    finally:
        _force_rmtree(repo)


def test_pr_closed_not_merged_fails_as_stale(tmp_path, monkeypatch):
    """A CLOSED (not merged) PR is stale regardless of any commit
    comparison -- unchanged behaviour, verified again under the new
    MERGED-branch code path to guard against a regression there."""
    repo = _kstmp_repo("pr-closed-not-merged")
    try:
        subprocess.run(["git", "checkout", "-b", "main"], cwd=repo, check=True)
        sha = _commit_file(repo, "a.txt", "a\n")
        subprocess.run(["git", "checkout", "-b", "work"], cwd=repo, check=True)
        (repo / "HANDOFF.md").write_text(
            _handoff_text_with_pr(sha, 7, "A closed PR (dead-branch)"), encoding="utf-8"
        )
        subprocess.run(["git", "add", "HANDOFF.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "handoff"], cwd=repo, check=True)

        monkeypatch.setattr(m, "_pr_state", lambda repo, n: "CLOSED")

        findings, infos, errors = m._check_all(repo)
        assert any(
            "stale open-PR listing" in f.label and "7" in f.text and "CLOSED" in f.text
            for f in findings
        ), findings
    finally:
        _force_rmtree(repo)


def test_pr_merged_but_merge_commit_unresolvable_fails_distinctly_not_as_stale(tmp_path, monkeypatch):
    """gh reports MERGED but gives no resolvable merge commit (shallow
    clone, degraded gh output, etc). This must exit non-zero -- the
    listing might genuinely be stale -- but must NOT be reported under
    the "stale" label, because that label asserts a proven lie and this
    case proves nothing either way. Mirrors the `main SHA:` shallow-clone
    branch's asymmetry."""
    repo = _kstmp_repo("pr-merge-commit-unresolvable")
    try:
        subprocess.run(["git", "checkout", "-b", "main"], cwd=repo, check=True)
        sha = _commit_file(repo, "a.txt", "a\n")
        subprocess.run(["git", "checkout", "-b", "work"], cwd=repo, check=True)
        (repo / "HANDOFF.md").write_text(
            _handoff_text_with_pr(sha, 22, "The state-claim gate (lwb-postmerge-gate)"), encoding="utf-8"
        )
        subprocess.run(["git", "add", "HANDOFF.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "handoff"], cwd=repo, check=True)

        monkeypatch.setattr(m, "_pr_state", lambda repo, n: "MERGED")
        monkeypatch.setattr(m, "_pr_merge_commit", lambda repo, n: None)

        findings, infos, errors = m._check_all(repo)
        assert any(
            "merge commit for listed PR could not be determined" in f.label and "22" in f.text
            for f in findings
        ), findings
        assert not any(
            "stale open-PR listing" in f.label and "22" in f.text for f in findings
        ), findings
    finally:
        _force_rmtree(repo)


def test_pr_merged_at_parent_in_shallow_clone_is_undeterminable_not_stale(tmp_path, monkeypatch):
    """THE THIRD OCCURRENCE OF THIS CLASS, caught by an independent
    reviewer. A CORRECT listing -- the PR's merge commit genuinely is live
    main's first parent -- must not be called "stale" merely because a
    shallow clone truncated `main^1` out of the visible history.

    The reviewer reproduced it in a real `--depth 1 --branch main` clone:
    #21, whose merge commit IS `main^1`, was reported
    `[stale open-PR listing in generated block] ... nor live main's first
    parent (None)` -- with the literal `None` in the message as the tell.
    The `main SHA:` branch already handles the same situation correctly;
    only this branch fell through to the accusation.

    Exit non-zero is CORRECT and must stay: a shallow clone may never
    silently pass. Only the reason must change, so the gate stops
    asserting what git has not established here.
    """
    repo = _kstmp_repo("pr-merged-parent-shallow")
    try:
        subprocess.run(["git", "checkout", "-b", "main"], cwd=repo, check=True)
        sha_a = _commit_file(repo, "a.txt", "a\n")
        subprocess.run(["git", "checkout", "-b", "work"], cwd=repo, check=True)
        (repo / "HANDOFF.md").write_text(
            _handoff_text_with_pr(sha_a, 21, "A correctly listed PR (b)"), encoding="utf-8"
        )
        subprocess.run(["git", "add", "HANDOFF.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "handoff"], cwd=repo, check=True)
        subprocess.run(["git", "checkout", "main"], cwd=repo, check=True)
        _commit_file(repo, "b.txt", "b\n")
        subprocess.run(["git", "checkout", "work"], cwd=repo, check=True)

        monkeypatch.setattr(m, "_pr_state", lambda repo, n: "MERGED")
        monkeypatch.setattr(m, "_pr_merge_commit", lambda repo, n: sha_a)
        # main^1 unresolvable, exactly as at depth 1, plus a shallow repo.
        real_rev_parse = m._rev_parse
        monkeypatch.setattr(
            m, "_rev_parse", lambda repo, rev: None if "^" in rev else real_rev_parse(repo, rev)
        )
        monkeypatch.setattr(m, "_is_shallow_repository", lambda repo: True)

        findings, infos, errors = m._check_all(repo)
        assert any(
            "undeterminable in a shallow clone" in f.label and "21" in f.text for f in findings
        ), findings
        assert not any(
            "stale open-PR listing" in f.label and "21" in f.text for f in findings
        ), findings
    finally:
        _force_rmtree(repo)


def test_pr_gh_unauthenticated_stays_info_and_passes(tmp_path, monkeypatch):
    """No regression on the already-covered degraded path: `gh`
    unavailable/unauthenticated (`_pr_state` returns None) must keep
    producing an UNVERIFIABLE info, not a failure -- CI runs with no gh
    auth today and must stay green on this path."""
    repo = _kstmp_repo("pr-gh-unauthenticated")
    try:
        subprocess.run(["git", "checkout", "-b", "main"], cwd=repo, check=True)
        sha = _commit_file(repo, "a.txt", "a\n")
        subprocess.run(["git", "checkout", "-b", "work"], cwd=repo, check=True)
        (repo / "HANDOFF.md").write_text(
            _handoff_text_with_pr(sha, 22, "The state-claim gate (lwb-postmerge-gate)"), encoding="utf-8"
        )
        subprocess.run(["git", "add", "HANDOFF.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "handoff"], cwd=repo, check=True)

        monkeypatch.setattr(m, "_pr_state", lambda repo, n: None)

        findings, infos, errors = m._check_all(repo)
        assert findings == [], findings
        assert any("could not be fully re-derived" in i.text for i in infos), infos
    finally:
        _force_rmtree(repo)

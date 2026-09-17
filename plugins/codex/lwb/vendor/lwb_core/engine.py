"""The pure (event, policy) -> Decision engine.

This module and everything it calls does NO I/O: no file reads, no stdin,
no environment variables, no clock. An adapter builds an `Event` and a
`Policy` from the outside world, calls `evaluate`, and turns the resulting
`Decision` back into its own hook protocol's exit code / JSON shape. That
split is what makes `tests/conformance` meaningful and what keeps a rule
testable without mocking a subprocess.

Rule registry: `RULES` is the list of rule modules the engine consults, in
order. A rule is a plain callable `(Event, RuleConfig) -> Optional[Finding]`;
returning None means "this rule has no opinion on this event". See
`rules/lwb_version.py` for the shape and `rules/__init__.py` for the
registry itself. The mutation test in tests/core proves the registry is
load-bearing: remove a rule from it and its deny disappears.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .config import Policy, RuleMode
from .events import Event
from .rules import RULES


@dataclass(frozen=True)
class Finding:
    """One rule's opinion on one event."""

    rule_id: str
    mode: RuleMode
    reason: str


@dataclass(frozen=True)
class Decision:
    """The engine's verdict for one event: the strictest finding wins.

    `permit` is True unless at least one rule fired in DENY mode. `warnings`
    collects reasons from every rule that fired in WARN mode, even when a
    later rule denies — an adapter may want to surface both. `findings`
    carries every non-None Finding, DENY and WARN alike, for adapters that
    want the full record (e.g. the ledger).
    """

    permit: bool = True
    deny_reason: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)


def evaluate(event: Event, policy: Policy) -> Decision:
    """Run every registered rule against `event` under `policy`. Never raises.

    Iteration order is `RULES` order. The first rule to produce a DENY
    finding sets `deny_reason` and short-circuits no further rule's WARN
    findings are lost, since every rule that already ran before the deny is
    still consulted — but rules after a deny are NOT evaluated, matching a
    hook protocol where the process would exit non-zero immediately.
    """
    findings: List[Finding] = []
    warnings: List[str] = []
    deny_reason: Optional[str] = None

    for rule in RULES:
        config = policy.rule_config(rule.rule_id)
        if config.mode is RuleMode.OFF:
            continue
        try:
            finding = rule.evaluate(event, config)
        except Exception as exc:  # noqa: BLE001 - a broken rule must not deny.
            # Fail-open at the rule level too: an exception inside a rule is
            # a bug in that rule, not grounds to block a dispatch. Record it
            # as a warning-shaped finding so adapters can log it.
            findings.append(
                Finding(
                    rule_id=rule.rule_id,
                    mode=RuleMode.WARN,
                    reason=f"rule '{rule.rule_id}' raised {exc.__class__.__name__}: {exc}",
                )
            )
            continue

        if finding is None:
            continue

        findings.append(finding)
        if finding.mode is RuleMode.DENY:
            deny_reason = finding.reason
            break
        if finding.mode is RuleMode.WARN:
            warnings.append(finding.reason)

    return Decision(
        permit=deny_reason is None,
        deny_reason=deny_reason,
        warnings=warnings,
        findings=findings,
    )

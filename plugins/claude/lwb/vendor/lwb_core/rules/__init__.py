"""The rule registry.

`RULES` is the ordered list of rule modules `engine.evaluate` consults. Each
entry must expose:

  - `rule_id: str` — the key a policy file's `"rules"` object uses to
    configure this rule.
  - `evaluate(event, config) -> Optional[Finding]` — pure, side-effect-free.

To add a rule: write it under `rules/`, import it here, and append it to
`RULES`. The mutation test `tests/core/test_engine_mutation.py` asserts that
removing `lwb_version` from this list makes its finding disappear from
`evaluate()`'s output for the walking-skeleton fixture — that is the proof
this registry is load-bearing rather than decorative.
"""

from __future__ import annotations

from . import lwb_proof_coverage, lwb_proof_integrity, lwb_proof_required, lwb_version

# Order matters only in that the engine stops at the first DENY. The no-op
# `lwb_version` is kept first so its version report is recorded in the
# ledger even on an event a later rule denies. `lwb_proof_coverage` and
# `lwb_proof_integrity` both import shared publish-detection helpers from
# `lwb_proof_required` (see each module's own docstring), so they are
# listed right after it -- proximity here is documentation, not a runtime
# dependency the engine enforces.
RULES = [
    lwb_version,
    lwb_proof_required,
    lwb_proof_coverage,
    lwb_proof_integrity,
]

__all__ = [
    "RULES",
    "lwb_proof_coverage",
    "lwb_proof_integrity",
    "lwb_proof_required",
    "lwb_version",
]

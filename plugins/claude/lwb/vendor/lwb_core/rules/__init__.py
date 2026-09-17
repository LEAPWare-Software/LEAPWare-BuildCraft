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

from . import lwb_version

RULES = [
    lwb_version,
]

__all__ = ["RULES", "lwb_version"]

"""lwb_version: the walking-skeleton rule -- a safe no-op.

Fires on every event, unconditionally, and reports this build's
`lwb_core.__version__` as a WARN-shaped finding. It never denies: even if
a policy file configures it to `"deny"`, this rule reports at WARN anyway
-- the no-op guarantee is enforced here, in the rule itself, not merely by
the shipped default. That is deliberate: it ships as a safe walking
skeleton so the whole (Event, Policy) -> Decision pipeline can be proven
end to end before BuildCraft's real SDLC gate rules (stage checks, role
lanes) are designed and built on top of it. See docs/rules/lwb-version.md
for the policy-author-facing description.
"""

from __future__ import annotations

from ..config import RuleConfig, RuleMode
from ..events import Event

rule_id = "lwb_version"

# Not `from .. import __version__`: lwb_core/__init__.py imports engine,
# which imports rules, which imports this module -- importing the package
# itself here would be a circular import. lwb_core/__init__.py re-exports
# the canonical `__version__`; that module is this string's one source of
# truth, kept in sync by tests/core/test_lwb_version.py.
_VERSION = "0.1.0"


def evaluate(event: Event, config: RuleConfig):
    """Always return a WARN Finding reporting the plugin version. Never denies.

    `config.mode` is already guaranteed non-OFF by the engine (it skips OFF
    rules before calling this). Unlike a normal rule, this one ignores
    `config.mode` for the purpose of severity -- it always reports at WARN,
    regardless of how a policy file configures it, so installing this
    walking skeleton can never itself block a dispatch.
    """
    from ..engine import Finding  # local import: engine imports this module.

    return Finding(
        rule_id=rule_id,
        mode=RuleMode.WARN,
        reason=f"lwb {_VERSION}: reporting only, no policy enforced yet",
    )

"""Policy loading and the fail-open contract.

A policy is plain data: `{"rules": {"<rule_id>": {"mode": "off"|"warn"|"deny", ...}}}`.
This module turns that dict into a `Policy` object the engine can query. It
does NOT read files — `load_policy_dict` takes a dict already parsed by an
adapter (json.load from a file, a bundled default, etc).

Fail-open contract (documented, not incidental): if the policy dict is
missing, malformed, or missing a rule's config entirely, that rule's mode
resolves to "off" and the condition is recorded so an adapter can log it.
BuildCraft never turns a broken or absent policy file into a deny — a config bug
must not be able to block every dispatch in a session. See
docs/policy.md#fail-open.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional


class RuleMode(str, Enum):
    OFF = "off"
    WARN = "warn"
    DENY = "deny"

    @classmethod
    def coerce(cls, value: Any) -> "RuleMode":
        """Return OFF for anything that isn't a recognized mode string.

        This is the fail-open boundary for a single rule's mode value:
        wrong type, unknown string, or None all resolve to OFF rather than
        raising, so a typo in a policy file degrades to "rule does nothing"
        instead of an unhandled exception surfacing as a denied dispatch.
        """
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            try:
                return cls(value.lower())
            except ValueError:
                return cls.OFF
        return cls.OFF


@dataclass(frozen=True)
class RuleConfig:
    mode: RuleMode = RuleMode.OFF
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Policy:
    rules: Mapping[str, RuleConfig] = field(default_factory=dict)
    #: True when the input dict was structurally broken (not just empty) and
    #: the fail-open path was taken. Adapters may log this; it never denies.
    degraded: bool = False
    degraded_reason: Optional[str] = None

    def rule_config(self, rule_id: str) -> RuleConfig:
        """Return the config for `rule_id`, defaulting to OFF if unconfigured.

        An absent rule entry is not an error: it means the policy author
        never mentioned this rule, and an unmentioned rule is off.
        """
        return self.rules.get(rule_id, RuleConfig())


def load_policy_dict(data: Any) -> Policy:
    """Build a `Policy` from an already-parsed dict. Never raises.

    Any shape that isn't `{"rules": {str: {"mode": str, ...}}}` degrades to
    an empty, all-OFF policy rather than raising, per the fail-open contract
    in this module's docstring.
    """
    if not isinstance(data, Mapping):
        return Policy(rules={}, degraded=True, degraded_reason="policy is not a JSON object")

    raw_rules = data.get("rules")
    if not isinstance(raw_rules, Mapping):
        return Policy(rules={}, degraded=True, degraded_reason="policy has no 'rules' object")

    rules: dict[str, RuleConfig] = {}
    degraded = False
    degraded_reason = None
    for rule_id, raw_cfg in raw_rules.items():
        if not isinstance(rule_id, str):
            degraded = True
            degraded_reason = degraded_reason or "a rule key is not a string"
            continue
        if not isinstance(raw_cfg, Mapping):
            rules[rule_id] = RuleConfig()
            degraded = True
            degraded_reason = degraded_reason or f"rule '{rule_id}' config is not an object"
            continue
        mode_value = raw_cfg.get("mode")
        mode = RuleMode.coerce(mode_value)
        # RuleMode.coerce() folds ANY unrecognized mode -- a typo'd string,
        # a number, a bool -- down to OFF, indistinguishable from a rule
        # deliberately configured off. An independent reviewer found this
        # meant a one-character typo (`"mode": "denied"` instead of
        # `"deny"`) silently disarmed a rule with no trace anywhere: not in
        # the ledger, not in `permissionDecisionReason`. `mode` unset
        # entirely is the ordinary, non-degraded case (an unmentioned rule
        # is off); anything ELSE present that did not coerce to a
        # recognized string is a policy-authoring mistake and must degrade
        # the whole policy so an adapter can surface it -- see
        # `bin/lwb_hook.py`'s `policy.degraded` handling.
        if mode_value is not None and not (
            isinstance(mode_value, str) and mode_value.lower() in ("off", "warn", "deny")
        ):
            degraded = True
            degraded_reason = degraded_reason or (
                f"rule '{rule_id}' has an unrecognized mode {mode_value!r}"
            )
        options = raw_cfg.get("options")
        if not isinstance(options, Mapping):
            options = {}
        rules[rule_id] = RuleConfig(mode=mode, options=options)

    return Policy(rules=rules, degraded=degraded, degraded_reason=degraded_reason)

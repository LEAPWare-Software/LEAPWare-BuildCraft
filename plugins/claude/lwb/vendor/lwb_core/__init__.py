"""lwb_core: the shared, adapter-agnostic decision engine for LEAPWare BuildCraft.

Runtime dependency policy: Python 3.10+ standard library ONLY. No third-party
imports anywhere under core/ or adapters/. Tests may use pytest (dev-only).

Nothing in this package performs I/O. Reading a hook event from stdin,
resolving a policy file from disk, and writing a decision back out are all
adapter concerns (see adapters/claude and adapters/codex). This package only
computes decisions from data already in memory.
"""

from .engine import evaluate
from .events import Event
from .config import Policy, RuleMode, load_policy_dict

__all__ = ["evaluate", "Event", "Policy", "RuleMode", "load_policy_dict"]

__version__ = "0.1.0"

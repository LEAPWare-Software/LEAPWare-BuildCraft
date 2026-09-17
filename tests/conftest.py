"""Put `core/` and the repo root on sys.path so tests import `lwb_core` and
`adapters.*` the same way `plugins/*/lwb/bin/lwb_hook.py`'s vendored copy
does, without requiring an editable install.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE_DIR = REPO_ROOT / "core"

for path in (str(CORE_DIR), str(REPO_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

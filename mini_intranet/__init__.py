"""mini-intranet: a small sample app for the Lapisite API (test environment only)."""

import sys
from pathlib import Path

# The official SDK is vendored (a copy, see vendor/README.md): make it importable as `lapisite`.
_VENDOR = str(Path(__file__).resolve().parent.parent / "vendor")
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)

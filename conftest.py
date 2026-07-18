"""Pytest bootstrap: make the repo root importable (contract_codec lives there)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

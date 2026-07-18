"""Pytest bootstrap: make the repo root importable (contract_codec, nature)."""

import sys
from pathlib import Path

# Repo root (this file lives at the root, not under tests/).
sys.path.insert(0, str(Path(__file__).resolve().parent))

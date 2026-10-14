"""Headless provider e2e gate: mock OpenAI, fixture matrix, and release verdict."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCHEMA_VERSION = 1
SUCCESS_RATE_THRESHOLD = 0.95

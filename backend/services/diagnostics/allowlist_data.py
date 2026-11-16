"""Shared allowlist loaded from allowlist.json. Both the client and the worker template use it."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_PATH = Path(__file__).with_name("allowlist.json")


@lru_cache(maxsize=1)
def allowlist() -> dict:
    data = json.loads(_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("diagnostics allowlist is not an object")
    return data


def PURPOSE() -> str:
    return str(allowlist()["purpose"])


PURPOSE = PURPOSE()
CONSENT_TEXT_VERSION = str(allowlist()["consent_text_version"])
SCHEMA = str(allowlist()["schema"])
FORBIDDEN_KEYS = frozenset(allowlist()["forbidden_keys"])
MANIFEST_KEYS = frozenset(allowlist()["manifest_keys"])
FILE_ROLES = frozenset(allowlist()["file_roles"])
ROLE_MAX_BYTES = {key: int(value) for key, value in allowlist()["role_max_bytes"].items()}

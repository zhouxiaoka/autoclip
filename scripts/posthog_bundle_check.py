"""Package checks for the desktop PostHog key and the values a release backend can read.

The key is never included in an error, a return value, or a log line.
"""
from __future__ import annotations

from pathlib import Path


def assert_binary_contains_posthog_key(binary: Path, key: str) -> None:
    """The release executable must contain the same non-empty project key the frontend uses."""
    value = (key or "").strip()
    if not value:
        raise AssertionError("desktop build has no PostHog key")
    if not binary.is_file():
        raise AssertionError("desktop binary is missing")
    if value.encode() not in binary.read_bytes():
        raise AssertionError("desktop binary does not contain the PostHog key")


def macos_desktop_binary(resources: Path) -> Path:
    binary = resources.resolve().parents[1] / "MacOS" / "autoclip-desktop"
    if not binary.is_file():
        raise AssertionError("desktop binary is missing")
    return binary


def windows_desktop_binary(resources: Path) -> Path:
    apps = [path for path in resources.parent.glob("*.exe") if "uninstall" not in path.name.lower()]
    if len(apps) != 1:
        raise AssertionError("desktop binary is missing")
    return apps[0]


def assert_packaged_telemetry_identity() -> None:
    """A release launcher sets production, and the app dir can hold an anonymous id.

    Call this only after AUTOCLIP_BUILD_ENVIRONMENT=production and AUTOCLIP_APP_DIR
    are already on the process. The id itself is not printed.
    """
    from backend.core.event_catalog import analytics_environment
    from backend.services.studio.qa.telemetry import _ANONYMOUS_ID, anonymous_distinct_id

    environment = analytics_environment()
    if environment != "production":
        raise AssertionError(f"packaged analytics_environment is {environment!r}")
    identity = anonymous_distinct_id()
    if _ANONYMOUS_ID.fullmatch(identity) is None:
        raise AssertionError("packaged backend did not produce an anonymous id")

"""Release-launcher values for the macOS bundle smoke.

`verify_macos_bundle.py` starts the bundled interpreter directly. The desktop
app does not: `BackendManager::start` injects `AUTOCLIP_APP_VERSION` from the
Cargo package version and `AUTOCLIP_BUILD_ENVIRONMENT=production` on a release
build (debug builds get `development` and do not report). The smoke has to
supply that same pair or the packaged backend correctly refuses to init.

This module does not add a bypass. Version comes from the built app's
Info.plist, and the environment is fixed to production because this script
checks the release bundle. pytest and a source tree still refuse inside
`init_sentry`, even when both values are present.
"""
from __future__ import annotations

import plistlib
from collections.abc import Mapping
from pathlib import Path

def release_launcher_env(resources: Path) -> dict[str, str]:
    # resources is App.app/Contents/Resources/resources; Info.plist is Contents/Info.plist.
    plist_path = resources.resolve().parents[1] / "Info.plist"
    if not plist_path.is_file():
        raise SystemExit(f"Bundle Info.plist not found: {plist_path}")
    with plist_path.open("rb") as handle:
        info = plistlib.load(handle)
    version = str(info.get("CFBundleShortVersionString") or "").strip()
    if not version or version.lower() == "unknown":
        raise SystemExit("Bundle version is missing; refusing to invent a Sentry release")
    return {
        "AUTOCLIP_APP_VERSION": version,
        "AUTOCLIP_BUILD_ENVIRONMENT": "production",
    }


def apply_release_launcher_env(base: Mapping[str, str], resources: Path) -> dict[str, str]:
    """Copy base and overwrite the two launcher keys. Inherited values cannot opt in."""
    env = dict(base)
    env.update(release_launcher_env(resources))
    return env

"""The macOS bundle smoke must reproduce the release launcher, not grow a bypass."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import macos_release_contract as contract


PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleShortVersionString</key><string>1.5.7</string>
</dict></plist>
"""


class ReleaseContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        contents = root / "AutoClip Desktop.app" / "Contents"
        self.resources = contents / "Resources" / "resources"
        self.resources.mkdir(parents=True)
        (contents / "Info.plist").write_text(PLIST, encoding="utf-8")

    def test_plist_version_and_production_are_the_only_keys(self):
        env = contract.release_launcher_env(self.resources)
        self.assertEqual(env, {
            "AUTOCLIP_APP_VERSION": "1.5.7",
            "AUTOCLIP_BUILD_ENVIRONMENT": "production",
        })

    def test_runner_env_cannot_choose_version_or_environment(self):
        with patch.dict(os.environ, {
            "AUTOCLIP_BUILD_ENVIRONMENT": "validation",
            "AUTOCLIP_APP_VERSION": "9.9.9",
            "AUTOCLIP_ENABLE_SENTRY": "1",
        }):
            env = contract.apply_release_launcher_env({
                "AUTOCLIP_BUILD_ENVIRONMENT": "development",
                "AUTOCLIP_APP_VERSION": "0.0.1",
                "SENTRY_DSN": "https://public@example.invalid/0",
            }, self.resources)
        self.assertEqual(env["AUTOCLIP_APP_VERSION"], "1.5.7")
        self.assertEqual(env["AUTOCLIP_BUILD_ENVIRONMENT"], "production")
        self.assertEqual(env["SENTRY_DSN"], "https://public@example.invalid/0")
        self.assertNotIn("AUTOCLIP_ENABLE_SENTRY", env)

    def test_missing_plist_or_unknown_version_refuses(self):
        (self.resources.parents[1] / "Info.plist").unlink()
        with self.assertRaises(SystemExit):
            contract.release_launcher_env(self.resources)
        (self.resources.parents[1] / "Info.plist").write_text(
            PLIST.replace("1.5.7", "unknown"), encoding="utf-8")
        with self.assertRaises(SystemExit):
            contract.release_launcher_env(self.resources)

    def test_smoke_calls_the_helper_and_adds_no_enable_flag(self):
        source = (Path(__file__).resolve().parents[1] / "verify_macos_bundle.py").read_text(encoding="utf-8")
        self.assertIn("apply_release_launcher_env", source)
        self.assertNotIn("AUTOCLIP_ENABLE_SENTRY", source)
        self.assertNotIn("AUTOCLIP_FORCE", source)


if __name__ == "__main__":
    unittest.main()

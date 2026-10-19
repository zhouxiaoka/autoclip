"""The desktop binary check reports presence only. It never echoes the project key."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import posthog_bundle_check as check

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = "phc_package_check_fixture"


class PosthogBundleCheckTests(unittest.TestCase):
    def test_present_key_passes_and_a_missing_key_does_not_echo_it(self):
        with tempfile.TemporaryDirectory() as temp:
            binary = Path(temp) / "autoclip-desktop"
            binary.write_bytes(b"prefix-" + FIXTURE.encode() + b"-suffix")
            check.assert_binary_contains_posthog_key(binary, FIXTURE)
            binary.write_bytes(b"no key here")
            with self.assertRaises(AssertionError) as raised:
                check.assert_binary_contains_posthog_key(binary, FIXTURE)
        self.assertNotIn(FIXTURE, str(raised.exception))
        with self.assertRaises(AssertionError) as empty:
            check.assert_binary_contains_posthog_key(binary, "  ")
        self.assertEqual(str(empty.exception), "desktop build has no PostHog key")

    def test_launcher_passes_the_frontend_key_without_logging_it(self):
        source = (ROOT / "src-tauri/src/backend_manager.rs").read_text(encoding="utf-8")
        self.assertIn('option_env!("VITE_PUBLIC_POSTHOG_KEY")', source)
        self.assertIn('cmd.env("AUTOCLIP_POSTHOG_KEY", key)', source)
        self.assertNotIn("println!", source[source.find("VITE_PUBLIC_POSTHOG_KEY"):source.find("VITE_PUBLIC_POSTHOG_KEY") + 400])
        for name in ("verify_macos_bundle.py", "verify_windows_install.py"):
            text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
            self.assertIn("assert_binary_contains_posthog_key", text)
            self.assertIn("assert_packaged_telemetry_identity", text)
            self.assertNotIn("print(key", text)
            self.assertNotIn("print(posthog", text.lower())
        workflow = (ROOT / ".github/workflows/desktop-build.yml").read_text(encoding="utf-8")
        self.assertGreaterEqual(workflow.count("VITE_PUBLIC_POSTHOG_KEY: ${{ secrets.VITE_PUBLIC_POSTHOG_KEY }}"), 4)


if __name__ == "__main__":
    unittest.main()

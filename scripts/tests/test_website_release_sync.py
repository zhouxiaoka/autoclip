"""官网同步脚本必须拒绝预发布，并只改当前版本槽位。"""

import importlib.util
import os
import subprocess
import tempfile
import unittest
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "website_sync_release",
    ROOT / "scripts" / "website" / "sync_release.py",
)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)

PAGE = """
<a href="https://github.com/zhouxiaoka/autoclip/releases/download/v1.5.8/AutoClip.Desktop_1.5.8_aarch64.dmg"></a>
<a href="https://github.com/zhouxiaoka/autoclip/releases/download/v1.5.8/AutoClip.Desktop_1.5.8_x64-setup.exe"></a>
"softwareVersion": "1.5.8"
<span data-i18n="hero.note">v1.5.8 · 开源</span>
'hero.note':'v1.5.8 · 开源',
"hero.note":"v1.5.8 · Open",
<p>当前版本 1.5.0，支持 Windows</p>
<p>v1.5.0 for Windows and Apple Silicon</p>
<span class="ver">v1.5.8 · 348 MB</span>
<span class="ver">v1.5.8 · 195 MB</span>
<a href="cases/autoclip-first-run/">AutoClip 1.5.0</a>
"""


def release(**extra):
    payload = {
        "tag_name": "v1.5.8",
        "draft": False,
        "prerelease": False,
        "published_at": "2026-11-02T12:15:50Z",
        "assets": [
            {"name": "AutoClip.Desktop_1.5.8_aarch64.dmg", "size": 1000, "browser_download_url": "https://example.test/mac"},
            {"name": "AutoClip.Desktop_1.5.8_x64-setup.exe", "size": 1000, "browser_download_url": "https://example.test/win"},
        ],
    }
    payload.update(extra)
    return payload


class WebsiteReleaseSync(unittest.TestCase):
    def test_prerelease_rc_and_api_failure_do_not_write(self):
        with self.assertRaises(SystemExit):
            sync.require_stable(release(tag_name="v1.5.9", prerelease=True), "v1.5.9")
        root = Path(tempfile.mkdtemp())
        (root / "index.html").write_text("UNTOUCHED", encoding="utf-8")

        def offline(*_args, **_kwargs):
            raise urllib.error.URLError("offline")

        with self.assertRaises(SystemExit) as caught:
            sync.fetch_release("v1.5.9", opener=offline)
        self.assertIn("页面保持原样", str(caught.exception))
        with self.assertRaises(SystemExit):
            sync.render(root, release(prerelease=True))
        self.assertEqual((root / "index.html").read_text(encoding="utf-8"), "UNTOUCHED")

    def test_stale_intro_follows_the_stable_version_and_history_stays(self):
        assets = {"mac": {"size_mb": 348}, "win": {"size_mb": 195}}
        updated = sync.patch_index(PAGE, "1.5.8", assets)
        self.assertIn("当前版本 1.5.8", updated)
        self.assertIn("v1.5.8 for Windows", updated)
        self.assertIn(">AutoClip 1.5.0<", updated)
        self.assertNotIn("当前版本 1.5.0", updated)

    def test_publish_guide_flag_does_not_overwrite_unless_the_homepage_patch_succeeds(self):
        install = ROOT / "scripts" / "website" / "install.sh"
        template = (ROOT / "scripts" / "website" / "guides" / "publish" / "index.html").read_text(encoding="utf-8")

        def run(flag):
            target = Path(tempfile.mkdtemp())
            (target / "index.html").write_text("<html>current homepage</html>", encoding="utf-8")
            page = target / "guides" / "publish" / "index.html"
            page.parent.mkdir(parents=True)
            page.write_text("SENTINEL-CURRENT-GUIDE", encoding="utf-8")
            env = os.environ.copy()
            env["SKIP_RELEASE_SYNC"] = "1"
            env["WITH_PUBLISH_GUIDE"] = flag
            env["LANG"] = "C.UTF-8"
            env["LC_ALL"] = "C.UTF-8"
            completed = subprocess.run(
                ["bash", str(install), str(target)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            return completed, page.read_text(encoding="utf-8")

        default, kept = run("0")
        self.assertEqual(default.returncode, 0, default.stderr)
        self.assertIn("未覆盖 guides/publish", default.stdout)
        self.assertEqual(kept, "SENTINEL-CURRENT-GUIDE")

        forced, still = run("1")
        self.assertNotEqual(forced.returncode, 0)
        self.assertIn("找不到插入点", forced.stderr + forced.stdout)
        self.assertEqual(still, "SENTINEL-CURRENT-GUIDE")
        self.assertNotIn(template[:40], still)

    def test_promote_workflow_does_not_notify_from_the_prerelease_build(self):
        workflow = (ROOT / ".github" / "workflows" / "promote-release.yml").read_text(encoding="utf-8")
        desktop = (ROOT / ".github" / "workflows" / "desktop-build.yml").read_text(encoding="utf-8")
        self.assertIn("isPrerelease", workflow)
        self.assertIn("event_type\\\":\\\"autoclip-release\\\"", workflow)
        self.assertNotIn("repos/zhouxiaoka/autoclip_intro/dispatches", desktop)


if __name__ == "__main__":
    unittest.main()

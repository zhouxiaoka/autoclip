"""W157-F7: bundled playwright + system Chrome / Edge, with a readable hint when no browser exists."""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from backend.services import packaging_runtime as runtime
from backend.services.studio import packaging_html as html

ROOT = Path(__file__).resolve().parents[2]
LOCALES = ROOT / 'frontend' / 'src' / 'i18n' / 'locales'


def _fake_exists(*present):
    wanted = {str(Path(p)) for p in present}
    return lambda path: str(path) in wanted


def test_windows_prefers_edge_channel_and_passes_its_path(monkeypatch):
    monkeypatch.setenv('PROGRAMFILES(X86)', r'C:\Program Files (x86)')
    edge = str(Path(r'C:\Program Files (x86)') / 'Microsoft' / 'Edge' / 'Application' / 'msedge.exe')
    found = runtime.find_system_browser('win32', exists=_fake_exists(edge), which=lambda _n: None)
    assert found == {'channel': 'msedge', 'executable': edge}


def test_mac_detects_chrome_in_user_applications(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    chrome = str(tmp_path / 'Applications' / 'Google Chrome.app/Contents/MacOS/Google Chrome')
    found = runtime.find_system_browser('darwin', exists=_fake_exists(chrome), which=lambda _n: None)
    assert found == {'channel': 'chrome', 'executable': chrome}
    monkeypatch.setattr(runtime, 'find_system_browser', lambda: found)
    kwargs = runtime.launch_kwargs()
    assert kwargs['channel'] == 'chrome' and kwargs['executable_path'] == chrome and kwargs['headless'] is True


def test_bundled_playwright_counts_as_installed_without_the_on_demand_dir(monkeypatch, tmp_path):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(runtime, '_data_dir', lambda: tmp_path)
    bundled = tmp_path / 'bundle' / 'site-packages' / 'playwright' / '__init__.py'
    monkeypatch.setattr(importlib.util, 'find_spec', lambda name: type('S', (), {'origin': str(bundled)})())
    monkeypatch.setattr(runtime, '_playwright_importable', lambda: True)
    monkeypatch.setattr(runtime, 'find_system_browser', lambda: {'channel': 'msedge', 'executable': 'C:/edge.exe'})
    assert not (tmp_path / 'packaging-runtime').exists()
    assert runtime.package_present() and runtime.is_installed()
    assert runtime.effective_template('editorial') == 'editorial'


def test_no_browser_gives_a_readable_hint_and_falls_back_to_classic(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, '_data_dir', lambda: tmp_path)
    monkeypatch.setattr(runtime, 'package_present', lambda: True)
    monkeypatch.setattr(runtime, '_playwright_importable', lambda: True)
    monkeypatch.setattr(runtime, 'find_system_browser', lambda: None)
    assert runtime.is_installed() is False and runtime.missing_browser() is True
    assert runtime.effective_template('street') == 'classic'
    job = html.prepare_overlay('p1', 'editorial', None, 1.0, features={'pkg_templates_v1': True})
    assert job.template == 'classic' and job.downgrade_reason == 'missing_runtime'
    assert runtime.downgrade_warning(job.downgrade_reason) == runtime.NO_BROWSER_WARNING
    assert runtime.downgrade_warning('over_budget') is None
    monkeypatch.setattr(runtime, 'package_present', lambda: False)
    assert runtime.downgrade_warning('missing_runtime') == runtime.NO_RUNTIME_WARNING


@pytest.mark.parametrize('key', [runtime.NO_BROWSER_WARNING, runtime.NO_RUNTIME_WARNING])
def test_hints_are_translated_in_all_eight_locales(key):
    files = sorted(LOCALES.glob('*.json'))
    assert len(files) == 8
    for file in files:
        value = json.loads(file.read_text(encoding='utf-8')).get(key)
        assert value, f'{file.name} lacks {key}'
        if file.stem != 'zh':
            assert value != key, file.name


def test_desktop_build_bundles_playwright_and_checks_it():
    common = (ROOT / 'scripts' / 'lib' / 'desktop_build_common.sh').read_text(encoding='utf-8')
    assert 'requirements-desktop.txt' in common and 'verify_playwright_bundled()' in common
    assert '"playwright"}' not in common  # no longer an on-demand-only import
    for script in ('build_macos_arm.sh', 'build_windows_x64.sh'):
        assert '\nverify_playwright_bundled\n' in (ROOT / 'scripts' / script).read_text(encoding='utf-8'), script
    desktop = (ROOT / 'requirements-desktop.txt').read_text(encoding='utf-8')
    assert runtime.PACKAGES[0] in desktop


def _real_browser():
    if importlib.util.find_spec('playwright') is None:
        return None
    return runtime.find_system_browser()


@pytest.mark.skipif(_real_browser() is None or shutil.which('ffmpeg') is None,
                    reason='needs playwright + a system Chrome/Edge + ffmpeg')
def test_real_render_produces_the_editorial_overlay_not_classic(monkeypatch, tmp_path):
    """Asserts what was rendered, not just what was requested."""
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(runtime, '_data_dir', lambda: tmp_path)
    (tmp_path / 'overlays').mkdir()
    monkeypatch.setattr(html, 'overlay_cache_path', lambda pid, tpl, fill: tmp_path / 'overlays' / f'{tpl}.mkv')
    assert runtime.is_installed()
    job = html.prepare_overlay('p1', 'editorial', None, 0.5, features={'pkg_templates_v1': True})
    assert job.downgraded is False, job
    assert job.template == 'editorial' and job.requested_template == 'editorial' and job.outcome == 'completed'
    assert job.path and job.path.is_file() and job.path.stat().st_size > 0
    # The overlay must carry real (non-transparent) editorial pixels: classic has no overlay at all.
    probe = subprocess.run(
        ['ffmpeg', '-v', 'error', '-i', str(job.path), '-vf', 'alphaextract', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
        capture_output=True, timeout=60, check=False)
    assert probe.returncode == 0, probe.stderr
    alpha = probe.stdout
    assert alpha and any(alpha), 'overlay is fully transparent'
    visible = sum(1 for b in alpha if b) / len(alpha)
    assert 0 < visible < 0.9, visible  # a caption/title layer, not an opaque full frame

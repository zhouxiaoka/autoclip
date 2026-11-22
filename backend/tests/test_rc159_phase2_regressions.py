"""Phase 2 regressions: bundled yt-dlp JS runtime (Windows/macOS) & 1.5.8/1.5.9 success_rate.sql cutoffs."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys

import pytest

from backend.tests.success_rate_sql import COHORT, PARAMS, SQL, figure, run_sql
from backend.utils import ffmpeg_utils

ROOT = Path(__file__).resolve().parents[2]
DAY = datetime(2026, 10, 12, 8, 0, 0)


def test_clean_machine_without_path_runtimes_gets_bundled_playwright_node_for_ytdlp(monkeypatch):
    """A clean Windows/macOS machine with no node/deno/bun/qjs on PATH must still hand yt-dlp a supported Node runtime."""
    import yt_dlp
    from yt_dlp.utils._jsruntime import NodeJsRuntime

    monkeypatch.setattr(ffmpeg_utils.shutil, 'which', lambda _name: None)
    opts = ffmpeg_utils.ytdlp_js_runtimes()
    node_path = (opts.get('js_runtimes') or {}).get('node', {}).get('path')
    assert node_path, f'expected bundled node runtime when PATH is empty, got {opts!r}'
    assert Path(node_path).is_file()
    info = NodeJsRuntime(node_path).info
    assert info is not None and info.supported, f'bundled node is not supported by yt-dlp: {info!r}'
    with yt_dlp.YoutubeDL({'quiet': True, **opts}) as ydl:
        assert ydl.params['js_runtimes']['node']['path'] == node_path


def test_windows_portable_python_discovers_bundled_playwright_node_exe(tmp_path):
    """Windows portable Python layout resolves Lib/site-packages/playwright/driver/node.exe."""
    exe = tmp_path / 'resources' / 'python' / 'python.exe'
    node_exe = tmp_path / 'resources' / 'python' / 'Lib' / 'site-packages' / 'playwright' / 'driver' / 'node.exe'
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b'')
    node_exe.parent.mkdir(parents=True)
    node_exe.write_bytes(b'')
    hits = {p.resolve() for p in ffmpeg_utils.bundled_candidates('node', executable=str(exe), platform_name='nt')}
    assert node_exe.resolve() in hits


def test_quickjs_runtime_detects_qjs_binary_name(monkeypatch):
    """yt-dlp's QuickJsRuntime invokes `qjs`, so PATH discovery must check `qjs` as well as `quickjs`."""
    monkeypatch.setattr(ffmpeg_utils, 'bundled_candidates', lambda *_args, **_kwargs: [])
    monkeypatch.setattr(ffmpeg_utils.shutil, 'which', lambda name: '/usr/local/bin/qjs' if name == 'qjs' else None)
    assert ffmpeg_utils.ytdlp_js_runtimes() == {'js_runtimes': {'quickjs': {'path': '/usr/local/bin/qjs'}}}


def test_verify_playwright_bundle_requires_node_driver_binary(tmp_path, monkeypatch):
    """verify_playwright_bundle.py must fail if playwright's driver lacks node / node.exe."""
    scripts_dir = str(ROOT / 'scripts')
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import verify_playwright_bundle as vpb

    assert vpb.check(None) == []
    fake_pkg = tmp_path / 'playwright'
    (fake_pkg / 'driver').mkdir(parents=True)
    (fake_pkg / 'driver' / 'README.md').write_text('stub', encoding='utf-8')
    fake_init = fake_pkg / '__init__.py'
    fake_init.write_text('', encoding='utf-8')
    fake_mod = type('M', (), {'__file__': str(fake_init)})()
    monkeypatch.setitem(sys.modules, 'playwright', fake_mod)
    monkeypatch.setitem(sys.modules, 'playwright.async_api', type('A', (), {'async_playwright': object()})())
    problems = vpb.check(None)
    assert any('node' in msg.lower() for msg in problems), problems


def test_success_rate_sql_gates_1_5_8_and_1_5_9_releases_and_figure_10():
    """Pre-release 1.5.8 / 1.5.9 production builds stay out of Figures 1-10 until their release timestamps are filled."""
    sql_text = (ROOT / 'docs/analytics/success_rate.sql').read_text(encoding='utf-8')
    for token, ver in (('{release_1_5_7}', '1.5.7'), ('{release_1_5_8}', '1.5.8'), ('{release_1_5_9}', '1.5.9')):
        assert token in sql_text, f'missing {token}'
        assert f"SELECT '{ver}' AS app_version, '20" not in sql_text

    rows = [
        # Pre-release 1.5.8 and 1.5.9 (before cutoff)
        ('u1', 'studio_generation_finished', 'p1', DAY - timedelta(minutes=30), {
            'analytics_environment': 'production', 'runtime': 'desktop', 'app_version': '1.5.8',
            'attempt_id': 'a-158-pre', 'flow_id': 'f-158-pre', 'outcome': 'completed',
        }),
        ('u2', 'studio_generation_finished', 'p2', DAY - timedelta(minutes=20), {
            'analytics_environment': 'production', 'runtime': 'desktop', 'app_version': '1.5.9',
            'attempt_id': 'a-159-pre', 'flow_id': 'f-159-pre', 'outcome': 'error',
            'error_code': 'service_restarted', 'restart_reason': 'crash',
            'crash_exit': 'sigsegv', 'crash_stage': 'render',
        }),
        # Post-release 1.5.8 and 1.5.9 (at/after cutoff)
        ('u3', 'studio_generation_finished', 'p3', DAY + timedelta(minutes=10), {
            'analytics_environment': 'production', 'runtime': 'desktop', 'app_version': '1.5.8',
            'attempt_id': 'a-158-live', 'flow_id': 'f-158-live', 'outcome': 'completed',
        }),
        ('u4', 'studio_generation_finished', 'p4', DAY + timedelta(minutes=15), {
            'analytics_environment': 'production', 'runtime': 'desktop', 'app_version': '1.5.9',
            'attempt_id': 'a-159-live-ok', 'flow_id': 'f-159-live-ok', 'outcome': 'completed',
        }),
        ('u5', 'studio_generation_finished', 'p5', DAY + timedelta(minutes=20), {
            'analytics_environment': 'production', 'runtime': 'desktop', 'app_version': '1.5.9',
            'attempt_id': 'a-159-live-crash', 'flow_id': 'f-159-live-crash', 'outcome': 'error',
            'error_code': 'service_restarted', 'restart_reason': 'crash',
            'crash_exit': 'sigsegv', 'crash_stage': 'render',
        }),
    ]

    # When release timestamps are filled, only post-release 1.5.8 and 1.5.9 rows count in Fig 5 and Fig 10.
    fig5 = {r['app_version']: r for r in run_sql(figure(5, sql_text, PARAMS), rows, cohort=COHORT)}
    assert set(fig5) == {'1.5.8', '1.5.9'}
    assert fig5['1.5.8']['ok'] == 1 and fig5['1.5.8']['q_all'] == 1
    assert fig5['1.5.9']['ok'] == 1 and fig5['1.5.9']['q_all'] == 2

    fig10 = run_sql(figure(10, sql_text, PARAMS), rows, cohort=COHORT)
    assert fig10 == [{'crash_exit': 'sigsegv', 'crash_stage': 'render', 'restarts': 1}]

    # When release_1_5_9 is blank '', all 1.5.9 rows are excluded from both Fig 5 and Fig 10.
    blank_159 = {**PARAMS, 'release_1_5_9': "''"}
    fig5_blank = {r['app_version']: r for r in run_sql(figure(5, sql_text, blank_159), rows, cohort=COHORT)}
    assert set(fig5_blank) == {'1.5.8'}
    fig10_blank = run_sql(figure(10, sql_text, blank_159), rows, cohort=COHORT)
    assert fig10_blank == []

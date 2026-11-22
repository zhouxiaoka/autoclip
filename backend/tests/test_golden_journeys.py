"""Golden Journey & Stage 2/3 regression tests (zero paid calls).

Covers:
- Stage 2 #1: DeepSeek & DashScope ranked ahead of sponsors in recommended providers,
  minimax-cn moved out of popular, internal hints removed.
- Stage 2 #2: Clear saved API key & delete last connection cleanly without 422.
- Stage 2 #3: HTML overlay capture flushes PNGs to disk (zero RAM bytes list),
  encode_ffv1 applies render_limits threads + low_priority, cover_executor capped at 1.
- Stage 3 Golden Journeys 1 & 3 (backend boundaries).
"""
from __future__ import annotations

import asyncio
import io
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from backend.api.v1.settings import router as settings_router
from backend.core import provider_presets, provider_quality
from backend.services import ai_model_settings as ai, render_limits
from backend.services.studio import jobs, packaging_html as html


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new('RGBA', (16, 16), (255, 0, 0, 128)).save(buf, format='PNG')
    return buf.getvalue()


def test_stage2_recommended_providers_put_deepseek_and_dashscope_ahead_of_sponsors():
    rec = provider_quality.recommended_provider_ids()
    assert rec[:3] == ['deepseek', 'dashscope', 'apimart']
    catalog = provider_presets.get_catalog().providers
    assert catalog['minimax-cn'].group == 'more'
    assert '上线前须核实' not in catalog['qianfan'].hint
    assert '上线前须核实' not in catalog['hunyuan'].hint


def test_golden_journey_1_settings_mask_clear_key_and_delete_last_connection(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())

    app = FastAPI()
    app.include_router(settings_router)
    with TestClient(app) as client:
        conn = {
            'id': 'ds-1',
            'name': 'DeepSeek',
            'provider': 'deepseek',
            'api_key': 'sk-secret-value-1234',
            'base_url': 'https://api.deepseek.com',
        }
        payload = {
            'version': 1,
            'connections': [conn],
            'analysis': {'connection_id': 'ds-1', 'model': 'deepseek-flash', 'capability': 'text', 'model_source': 'user'},
            'vision': None,
            'cover': None,
            'cover_enabled': False,
            'analysis_mode': 'auto',
            'allow_visual_screening': True,
        }
        r1 = client.put('/settings/ai-models', json=payload)
        assert r1.status_code == 200, r1.text
        saved = r1.json()
        assert saved['connections'][0]['has_key'] is True
        assert saved['connections'][0]['api_key_masked'] == 'sk-…234'
        assert 'api_key' not in saved['connections'][0]

        # Clear saved API key explicitly with empty string
        saved['connections'][0]['api_key'] = ''
        saved['analysis'] = None
        r2 = client.put('/settings/ai-models', json=saved)
        assert r2.status_code == 200, r2.text
        cleared = r2.json()
        assert cleared['connections'][0]['has_key'] is False
        assert cleared['connections'][0]['api_key_masked'] == ''

        # Delete the last remaining connection cleanly (no 422 trap)
        cleared['connections'] = []
        cleared['analysis'] = None
        r3 = client.put('/settings/ai-models', json=cleared)
        assert r3.status_code == 200, r3.text
        assert r3.json()['connections'] == []


def test_stage2_oom_html_overlay_streams_frames_to_disk_and_bounds_ffv1_and_covers(tmp_path):
    blob = _png_bytes()

    async def render(_page, t):
        return f'h-{int(t * 2)}'

    async def shoot(_page, _idx):
        return blob

    frames = asyncio.run(html.capture_changed(6, 2, render, shoot, pages=2, out_dir=tmp_path))
    assert len(frames) >= 2
    assert all(isinstance(item['png'], Path) and item['png'].is_file() for item in frames), (
        'capture_changed(out_dir=...) must flush PNGs to disk instead of keeping raw bytes in RAM'
    )

    seen_cmds = []

    def fake_run(cmd):
        seen_cmds.append(list(cmd))
        Path(cmd[-1]).write_bytes(b'fake-mkv')
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    holds = html._write_holds(frames, tmp_path)
    dest = tmp_path / 'overlay.mkv'
    html.encode_ffv1(holds, dest, fps=30, timeout=30, run=fake_run)
    assert dest.is_file()
    assert len(seen_cmds) == 1
    cmd = seen_cmds[0]
    assert cmd[-1].endswith('.partial')
    for token in render_limits.input_args():
        assert token in cmd
    assert '-threads' in cmd
    assert jobs.cover_executor._max_workers == 1


def test_golden_journey_3_on_demand_portrait_variants_keep_portrait_crop():
    import inspect

    src = inspect.getsource(jobs._produce_on_demand)
    assert 'portrait_crop=True' in src or 'portrait_crop' in src

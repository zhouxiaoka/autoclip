"""1.5.9 Pack C regressions: OpenCV YuNet lock, cover ffmpeg timeout, render translation fallback,
cancelled settlement, and #580 portrait 9:16 consistency."""
from __future__ import annotations

import io
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from backend.services import cover
from backend.services.studio import cover_design, framing, jobs, render, store, template_choice


def test_cover_design_acquires_framing_detector_lock(monkeypatch):
    buf = io.BytesIO()
    Image.new('RGB', (64, 64), (120, 130, 140)).save(buf, format='JPEG')
    jpeg_bytes = buf.getvalue()

    lock = threading.Lock()
    lock_held_during_detect = []

    class FakeDetector:
        def detect(self, _pixels):
            # Inside detect(), lock must already be held by caller (non-blocking acquire must return False)
            acquired = lock.acquire(blocking=False)
            if acquired:
                lock.release()
            lock_held_during_detect.append(not acquired)
            return 1, None

    class FakeCV2:
        IMREAD_COLOR = 1

        def imdecode(self, _arr, _flag):
            import numpy as np
            return np.zeros((64, 64, 3), dtype=np.uint8)

    monkeypatch.setattr(framing, '_detector_lock', lock)
    monkeypatch.setattr(framing, 'load_cv2', lambda: FakeCV2())
    monkeypatch.setattr(framing, 'MODEL', Path(__file__))  # exists() == True
    monkeypatch.setattr(framing, '_detector', lambda _cv2, _w, _h: FakeDetector())

    cover_design._face_and_sharpness(jpeg_bytes)
    assert lock_held_during_detect == [True], 'cover_design called framing._detector().detect() without _detector_lock'


def test_cover_extract_frame_jpeg_enforces_subprocess_timeout(tmp_path, monkeypatch):
    video = tmp_path / 'clip.mp4'
    video.write_bytes(b'0' * 16)
    captured = []

    def fake_run(cmd, **kwargs):
        captured.append(kwargs)
        Path(cmd[-1]).write_bytes(b'\xff\xd8\xff\xd9')
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    monkeypatch.setattr('subprocess.run', fake_run)
    monkeypatch.setattr('backend.utils.ffmpeg_utils.get_ffmpeg_path', lambda: 'ffmpeg')

    data = cover.extract_frame_jpeg(video, at_sec=1.0)
    assert data.startswith(b'\xff\xd8')
    assert captured and captured[0].get('timeout') is not None and captured[0]['timeout'] > 0
    assert captured[0].get('encoding') == 'utf-8'


def test_render_translate_hook_and_cues_falls_back_to_source_on_llm_error(monkeypatch):
    monkeypatch.setattr(render, 'text_json', lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('upstream 503')))
    entries = [{'start': 0.0, 'end': 2.0, 'text': '你好世界'}]
    warnings: list[str] = []

    hook = render._translate_hook_and_cues('en', '原始标题', entries, warnings)
    assert hook == '原始标题'
    assert entries[0]['text'] == '你好世界'
    assert warnings, 'expected graceful degradation warning when subtitle translation fails'


def test_settle_generation_settles_cancelled_variants_instead_of_hanging_rendering():
    data = {
        'analysis': {'status': 'running', 'phase': 'rendering', 'run_id': 'r1', 'attempt_id': 'a1', 'flow_id': 'f1'},
        'generation': {'status': 'rendering', 'attempt_id': 'a1', 'flow_id': 'f1'},
        'output_variants': [
            {'id': 'v1', 'status': 'cancelled', 'render_job_id': 'j1', 'attempt_id': 'a1'},
        ],
        'jobs': [
            {'job_id': 'j1', 'status': 'cancelled', 'error_code': 'cancelled'},
        ],
    }
    store.settle_generation(data)
    assert data['generation']['status'] == 'cancelled'
    assert data['generation'].get('error_code') == 'cancelled'


def test_on_demand_portrait_variant_preserves_9_16_crop_for_html_template(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))

    framing_calls = []

    def fake_apply_framing(project_id, raw, strategy_id, video, burned, cache, portrait_crop=False):
        framing_calls.append({'strategy_id': strategy_id, 'portrait_crop': portrait_crop})
        return {**raw, 'layout': 'crop' if portrait_crop else 'window'}, 'speaker'

    monkeypatch.setattr(jobs, 'source', lambda _pid: tmp_path / 'video.mp4')
    monkeypatch.setattr(jobs, '_source_has_burned_subtitles', lambda _pid, _v: False)
    monkeypatch.setattr(jobs, '_apply_framing', fake_apply_framing)
    monkeypatch.setattr(jobs, '_prefetch_packaging', lambda *a, **k: None)
    monkeypatch.setattr(jobs, '_apply_packaging', lambda _pid, v, _sid, _b, _c: v)
    monkeypatch.setattr(jobs, '_posts_for', lambda *a, **k: {})
    monkeypatch.setattr(jobs, '_dispatch_pending_variants', lambda _pid: None)

    pid = 'proj-580'
    store.directory(pid).mkdir(parents=True, exist_ok=True)
    store.write(pid, {
        'generation': {
            'status': 'rendering',
            'html_template': 'editorial',
            'features': {'pkg_templates_v1': True},
        },
        'drafts': [{
            'id': 'd4',
            'title': 'Fourth clip',
            'scenes': [{'id': 's1', 'start': 0.0, 'end': 30.0, 'label': 'clip'}],
            'revision': 1,
        }],
        'output_variants': [{
            'id': 'v4',
            'draft_id': 'd4',
            'strategy_id': 'douyin',
            'status': 'preparing',
        }],
        'jobs': [],
    })

    jobs._produce_on_demand(pid, 'v4')
    assert framing_calls == [{'strategy_id': 'douyin', 'portrait_crop': True}]
    saved = store.read(pid)
    assert saved['drafts'][0]['layout'] == 'crop'


def test_html_candidate_ids_supports_unscored_visual_drafts():
    from backend.services.studio import intelligence
    from backend.services.studio.models import Preferences, Scene

    events = [
        Scene(id=f'ev-{i}', start=float(i * 10), end=float(i * 10 + 8), label=f'Highlight {i}')
        for i in range(1, 5)
    ]
    visual_drafts = intelligence.make_drafts(events, Preferences(goal='highlight', aspect='portrait'))
    chosen = template_choice.html_candidate_ids(visual_drafts, limit=3)
    assert len(chosen) == 3
    assert chosen == {d['id'] for d in visual_drafts[:3]}

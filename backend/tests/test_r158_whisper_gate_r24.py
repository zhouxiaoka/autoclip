"""1.5.8 R24 (#231 conditions): the import gate lets an unreadable source through, and the pipeline then reports
source_unreadable (a) before any paid model call, (b) as a user/source cause the success rate excludes, and (c) on
the first failed state the page reads (the page copy itself is covered by frontend/tests/studio-results-status)."""
import re
import socket
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.core import event_catalog
from backend.services.studio import intelligence, jobs, readiness
from backend.tests.test_r158_whisper_gate_r19 import isolated, settings  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def unreadable(tmp_path, monkeypatch):
    broken = tmp_path / 'broken.mp4'
    broken.write_bytes(b'not a video at all' * 64)
    paid = []
    for name in ('vision_call', 'vision_call_at', 'text_json', 'analyze', 'make_drafts'):
        monkeypatch.setattr(intelligence, name, lambda *a, _n=name, **k: paid.append(_n))
    monkeypatch.setattr(intelligence, 'ready', lambda: True)  # a vision model is configured: screening would call it

    def no_network(self, *a, **k):
        paid.append('network')
        raise OSError('network disabled in this test')
    monkeypatch.setattr(socket.socket, 'connect', no_network)
    saved = {'analysis': {}, 'generation': {'auto_start': True}}
    writes = []

    def change(pid, fn):
        result = fn(saved)
        writes.append({k: dict(v) if isinstance(v, dict) else v for k, v in saved.items()})
        return result
    monkeypatch.setattr(jobs.store, 'change', change)
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'source', lambda pid: broken)
    monkeypatch.setattr(jobs, 'capture_studio_exception', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'ensure_project_thumbnail', lambda *a, **k: None)
    return SimpleNamespace(video=broken, paid=paid, saved=saved, writes=writes)


@pytest.mark.parametrize('mode', ['visual', 'auto'])
def test_r24_231a_unreadable_source_fails_before_any_paid_model_call(unreadable, mode):
    settings(mode)
    readiness.ensure_local_transcription_for_import(srt_available=False, video=unreadable.video, goal='auto')  # gate passes
    jobs._inspect('p1', SimpleNamespace(auto_start=True, goal='auto'), None, None)
    assert unreadable.saved['analysis']['error_code'] == 'source_unreadable'
    assert unreadable.paid == [], f'paid model / network calls before the failure: {unreadable.paid}'


def test_r24_231b_source_unreadable_is_a_user_cause_in_catalog_and_sql(unreadable):
    settings('visual')
    jobs._inspect('p1', SimpleNamespace(auto_start=True, goal='auto'), None, None)
    generation = unreadable.saved['generation']
    # studio_generation_finished reads generation.error_code (frontend/src/analytics/workflow.ts)
    assert generation['status'] == 'failed' and generation['error_code'] == 'source_unreadable'
    attribution = event_catalog.load_catalog()['attribution']
    assert 'source_unreadable' in attribution['user_caused_error_codes']
    for doc in ('docs/analytics/success_rate.sql', 'docs/analytics/TRACKING_PLAN.md'):
        text = (ROOT / doc).read_text(encoding='utf-8')
        exclusions = re.findall(r"error_code, ''\) NOT IN\s*\(([^)]*)\)", text)
        assert exclusions, doc
        for block in exclusions:
            assert "'source_unreadable'" in block, f'{doc}: the success rate must exclude source_unreadable'


def test_r24_231c_first_state_the_page_reads_is_the_coded_failure_not_a_running_screen(unreadable):
    settings('visual')
    jobs._inspect('p1', SimpleNamespace(auto_start=True, goal='auto'), None, None)
    # No production / rendering state is ever written for this source: the page goes straight to the failure.
    phases = [(w.get('analysis') or {}).get('phase') for w in unreadable.writes]
    assert 'production' not in phases
    final = unreadable.writes[-1]['analysis']
    assert final['status'] == 'failed' and final['phase'] == 'screening' and final['error_code'] == 'source_unreadable'
    assert '无法读取这个视频' in final['error']


# ---- #285: a broken video with a valid SRT fails before any paid text-model call
def test_r24_285_broken_video_with_valid_srt_fails_before_the_text_model(monkeypatch, tmp_path):
    import asyncio
    from backend.services import simple_pipeline_adapter as spa
    settings('subtitle')
    broken = tmp_path / 'broken.mp4'
    broken.write_bytes(b'not a video at all' * 64)
    srt = tmp_path / 'broken.srt'
    srt.write_text('1\n00:00:00,000 --> 00:00:05,000\nhello\n\n2\n00:00:05,000 --> 00:00:30,000\nworld\n', encoding='utf-8')
    paid = []
    monkeypatch.setattr(spa.SimplePipelineAdapter, '_preflight_llm', staticmethod(lambda: paid.append('preflight')))
    from backend.core import llm_manager
    monkeypatch.setattr(llm_manager, 'get_llm_manager', lambda *a, **k: paid.append('llm_manager'))
    result = asyncio.run(spa.SimplePipelineAdapter('r24-285', task_id='t-r24-285').process_project_sync(str(broken), str(srt)))
    assert result.get('error_code') == 'source_unreadable', result
    assert paid == [], paid

"""R3: resume from subtitle / step artifacts when pipeline_stamp matches."""
from __future__ import annotations

import json
from pathlib import Path

import asyncio

import pytest

from backend.services.studio import pipeline_resume as pr


def _video(tmp_path: Path, name='input.mp4', size=2048) -> Path:
    path = tmp_path / 'raw' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'0' * size)
    return path


def _srt(video: Path, text='1\n00:00:00,000 --> 00:00:01,000\nhi\n') -> Path:
    srt = video.parent / 'input.srt'
    srt.write_text(text, encoding='utf-8')
    return srt


def _meta(tmp_path: Path) -> Path:
    d = tmp_path / 'metadata'
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_step(meta: Path, step: str, payload=None):
    path = pr.step_artifact_path(meta, step)
    path.write_text(json.dumps(payload if payload is not None else [{'id': step}], ensure_ascii=False), encoding='utf-8')


def test_fresh_forces_none_and_clear_removes_artifacts(tmp_path, monkeypatch):
    video = _video(tmp_path)
    srt = _srt(video)
    meta = _meta(tmp_path)
    monkeypatch.setattr(pr, 'current_model_stamp', lambda prompt_files=None: {
        'provider': 'api88', 'model': 'm1', 'prompt_hash': 'abc',
    })
    pr.write_stamp(meta, video=video)
    for step, _ in pr.STEP_ARTIFACTS:
        _write_step(meta, step)

    decision = pr.decide_resume(video=video, srt=srt, metadata_dir=meta, fresh=True)
    assert decision['resumed_from'] == 'none'
    assert decision['skip_transcription'] is False

    pr.clear_pipeline_cache(meta, raw_dir=video.parent)
    assert not (meta / pr.STAMP_NAME).exists()
    assert not (meta / 'step1_outline.json').exists()
    assert not srt.exists()


def test_subtitle_reuse_when_source_matches_but_model_changed(tmp_path, monkeypatch):
    video = _video(tmp_path)
    srt = _srt(video)
    meta = _meta(tmp_path)
    monkeypatch.setattr(pr, 'current_model_stamp', lambda prompt_files=None: {
        'provider': 'old', 'model': 'm1', 'prompt_hash': 'abc',
    })
    pr.write_stamp(meta, video=video)
    _write_step(meta, 'step1')

    monkeypatch.setattr(pr, 'current_model_stamp', lambda prompt_files=None: {
        'provider': 'new', 'model': 'm2', 'prompt_hash': 'abc',
    })
    decision = pr.decide_resume(video=video, srt=srt, metadata_dir=meta, fresh=False)
    assert decision['skip_transcription'] is True
    assert decision['resumed_from'] == 'subtitle'
    assert decision['reuse_steps'] == frozenset()
    assert decision['start_step'] == 'step1'


def test_resume_from_step2_when_step1_present_and_stamp_matches(tmp_path, monkeypatch):
    video = _video(tmp_path)
    srt = _srt(video)
    meta = _meta(tmp_path)
    monkeypatch.setattr(pr, 'current_model_stamp', lambda prompt_files=None: {
        'provider': 'api88', 'model': 'm1', 'prompt_hash': 'abc',
    })
    pr.write_stamp(meta, video=video)
    _write_step(meta, 'step1', [{'outline': 'a'}])

    decision = pr.decide_resume(video=video, srt=srt, metadata_dir=meta)
    assert decision['skip_transcription'] is True
    assert decision['resumed_from'] == 'step2'
    assert decision['start_step'] == 'step2'
    assert decision['reuse_steps'] == frozenset({'step1'})


def test_all_steps_present_marks_done(tmp_path, monkeypatch):
    video = _video(tmp_path)
    srt = _srt(video)
    meta = _meta(tmp_path)
    monkeypatch.setattr(pr, 'current_model_stamp', lambda prompt_files=None: {
        'provider': 'api88', 'model': 'm1', 'prompt_hash': 'abc',
    })
    pr.write_stamp(meta, video=video)
    for step, _ in pr.STEP_ARTIFACTS:
        _write_step(meta, step, [{'ok': True}])

    decision = pr.decide_resume(video=video, srt=srt, metadata_dir=meta)
    assert decision['resumed_from'] == 'step4'
    assert decision['start_step'] == 'done'
    assert 'step4' in decision['reuse_steps']


def test_source_mtime_change_invalidates_srt(tmp_path, monkeypatch):
    video = _video(tmp_path)
    srt = _srt(video)
    meta = _meta(tmp_path)
    monkeypatch.setattr(pr, 'current_model_stamp', lambda prompt_files=None: {
        'provider': 'api88', 'model': 'm1', 'prompt_hash': 'abc',
    })
    pr.write_stamp(meta, video=video)
    # Change source size → fingerprint mismatch
    video.write_bytes(b'1' * 4096)
    decision = pr.decide_resume(video=video, srt=srt, metadata_dir=meta)
    assert decision['skip_transcription'] is False
    assert decision['resumed_from'] == 'none'



def test_adapter_skips_outline_when_step1_reusable(tmp_path, monkeypatch):
    """process_project_sync loads step1 instead of calling run_step1_outline."""
    from backend.services.simple_pipeline_adapter import SimplePipelineAdapter

    video = _video(tmp_path)
    srt = _srt(video)
    meta = _meta(tmp_path)
    project_dir = tmp_path
    (project_dir / 'output').mkdir(exist_ok=True)

    monkeypatch.setattr(pr, 'current_model_stamp', lambda prompt_files=None: {
        'provider': 'api88', 'model': 'm1', 'prompt_hash': 'abc',
    })
    pr.write_stamp(meta, video=video)
    _write_step(meta, 'step1', [{'id': '1', 'outline': 'kept'}])

    calls = {'step1': 0, 'step2': 0}

    def fake_step1(*a, **k):
        calls['step1'] += 1
        return [{'id': 'new'}]

    def fake_step2(*a, **k):
        calls['step2'] += 1
        path = meta / 'step2_timeline.json'
        data = [{'start': 0, 'end': 1}]
        path.write_text(json.dumps(data), encoding='utf-8')
        return data

    def fake_step3(*a, **k):
        path = meta / 'step3_high_score_clips.json'
        data = [{'id': 'c1', 'final_score': 0.9}]
        path.write_text(json.dumps(data), encoding='utf-8')
        return data

    def fake_step4(*a, **k):
        path = meta / 'step4_titles.json'
        data = [{'id': 'c1', 'generated_title': 't'}]
        path.write_text(json.dumps(data), encoding='utf-8')
        return data

    monkeypatch.setattr('backend.services.simple_pipeline_adapter.run_step1_outline', fake_step1)
    monkeypatch.setattr('backend.services.simple_pipeline_adapter.run_step2_timeline', fake_step2)
    monkeypatch.setattr('backend.services.simple_pipeline_adapter.run_step3_scoring', fake_step3)
    monkeypatch.setattr('backend.services.simple_pipeline_adapter.run_step4_title', fake_step4)
    monkeypatch.setattr('backend.core.path_utils.get_project_directory', lambda pid: project_dir)
    monkeypatch.setattr('backend.services.simple_progress.emit_progress', lambda *a, **k: None)
    monkeypatch.setattr('backend.services.simple_progress.clear_progress', lambda *a, **k: None)
    monkeypatch.setattr('backend.core.project_cancellation.checkpoint', lambda *a, **k: None)
    monkeypatch.setattr('backend.pipeline.concurrency.reset_limiter', lambda: None)

    class Ok:
        source_failure = None
        asr_failure = None
        ok = True
    monkeypatch.setattr('backend.services.studio.preflight.preflight', lambda *a, **k: Ok())

    adapter = SimplePipelineAdapter('proj', 'task')
    monkeypatch.setattr(adapter, '_prompt_files', lambda project_dir: {})
    monkeypatch.setattr(adapter, '_preflight_llm', lambda: None)
    monkeypatch.setattr(adapter, '_find_clips_in_one_pass', lambda *a, **k: None)

    class FakeSync:
        def sync_project_from_filesystem(self, *a, **k):
            return {'success': True}
    monkeypatch.setattr('backend.services.data_sync_service.DataSyncService', lambda db: FakeSync())
    monkeypatch.setattr('backend.core.database.SessionLocal', lambda: type('S', (), {'close': lambda self: None})())

    result = asyncio.run(adapter.process_project_sync(
        str(video), str(srt), clips_only=True, resume=True, fresh=False,
    ))
    assert result['status'] == 'succeeded'
    assert result['resumed_from'] == 'step2'
    assert calls['step1'] == 0
    assert calls['step2'] == 1

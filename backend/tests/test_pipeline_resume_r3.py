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
    # ASR-generated SRT: fresh must still delete it (P1 #6).
    pr.write_stamp(meta, video=video, extra={'srt_origin': 'asr'})
    for step, _ in pr.STEP_ARTIFACTS:
        _write_step(meta, step)

    decision = pr.decide_resume(video=video, srt=srt, metadata_dir=meta, fresh=True)
    assert decision['resumed_from'] == 'none'
    assert decision['skip_transcription'] is False

    pr.clear_pipeline_cache(meta, raw_dir=video.parent)
    assert not (meta / pr.STAMP_NAME).exists()
    assert not (meta / 'step1_outline.json').exists()
    assert not srt.exists()


def test_clear_keeps_attached_srt_on_fresh(tmp_path, monkeypatch):
    """P1 #6: user-attached / platform SRT must survive 「从头重做」."""
    video = _video(tmp_path)
    srt = _srt(video)
    meta = _meta(tmp_path)
    monkeypatch.setattr(pr, 'current_model_stamp', lambda prompt_files=None: {
        'provider': 'api88', 'model': 'm1', 'prompt_hash': 'abc',
    })
    pr.write_stamp(meta, video=video, extra={'srt_origin': 'attached'})
    for step, _ in pr.STEP_ARTIFACTS:
        _write_step(meta, step)

    pr.clear_pipeline_cache(meta, raw_dir=video.parent)
    assert not (meta / pr.STAMP_NAME).exists()
    assert not (meta / 'step1_outline.json').exists()
    assert srt.exists(), 'attached SRT must survive clear_pipeline_cache'


def test_clear_keeps_srt_when_origin_missing(tmp_path, monkeypatch):
    """P1 #6: missing srt_origin is treated as non-ASR → keep the file."""
    video = _video(tmp_path)
    srt = _srt(video)
    meta = _meta(tmp_path)
    monkeypatch.setattr(pr, 'current_model_stamp', lambda prompt_files=None: {
        'provider': 'api88', 'model': 'm1', 'prompt_hash': 'abc',
    })
    pr.write_stamp(meta, video=video)  # no srt_origin
    pr.clear_pipeline_cache(meta, raw_dir=video.parent)
    assert srt.exists()


def test_write_stamp_preserves_srt_origin(tmp_path, monkeypatch):
    video = _video(tmp_path)
    meta = _meta(tmp_path)
    monkeypatch.setattr(pr, 'current_model_stamp', lambda prompt_files=None: {
        'provider': 'api88', 'model': 'm1', 'prompt_hash': 'abc',
    })
    pr.write_stamp(meta, video=video, extra={'srt_origin': 'asr'})
    pr.write_stamp(meta, video=video)  # step refresh without extra
    stamp = pr.read_stamp(meta)
    assert stamp['srt_origin'] == 'asr'


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


def test_model_mismatch_clears_stale_steps_so_retry_is_not_done(tmp_path, monkeypatch):
    """P1 #7: after model change, leftover step2/3/4 must not make a later decide return done.

    Bug sequence: stamp_ok=False → restart step1 without clearing → step1 write_stamp
    (new model) → step2 fails → retry sees four files + matching stamp → start_step=done
    and serves the old model's step4_titles.json.
    """
    video = _video(tmp_path)
    srt = _srt(video)
    meta = _meta(tmp_path)
    monkeypatch.setattr(pr, 'current_model_stamp', lambda prompt_files=None: {
        'provider': 'old', 'model': 'A', 'prompt_hash': 'abc',
    })
    pr.write_stamp(meta, video=video, extra={'srt_origin': 'attached'})
    for step, _ in pr.STEP_ARTIFACTS:
        _write_step(meta, step, [{'model': 'A', 'step': step}])

    monkeypatch.setattr(pr, 'current_model_stamp', lambda prompt_files=None: {
        'provider': 'new', 'model': 'B', 'prompt_hash': 'abc',
    })
    first = pr.decide_resume(video=video, srt=srt, metadata_dir=meta, fresh=False)
    assert first['stamp_ok'] is False
    assert first['start_step'] == 'step1'
    assert first['skip_transcription'] is True
    assert srt.exists(), 'P1 #6: attached SRT must survive step invalidation'
    assert not (meta / 'step4_titles.json').exists()
    assert not (meta / 'step2_timeline.json').exists()
    assert (meta / pr.STAMP_NAME).exists(), 'stamp kept until next successful step rewrite'

    # Simulate step1 success under model B, then step2 raising (no step2 written).
    _write_step(meta, 'step1', [{'model': 'B', 'outline': 'new'}])
    pr.write_stamp(meta, video=video)

    second = pr.decide_resume(video=video, srt=srt, metadata_dir=meta, fresh=False)
    assert second['stamp_ok'] is True
    assert second['start_step'] != 'done'
    assert second['start_step'] == 'step2'
    assert second['reuse_steps'] == frozenset({'step1'})


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

def test_clips_only_step4_and_stamp_marks_done(tmp_path, monkeypatch):
    """P2 #11: Studio one-pass only writes step4; matching stamp → done."""
    video = _video(tmp_path)
    srt = _srt(video)
    meta = _meta(tmp_path)
    monkeypatch.setattr(pr, 'current_model_stamp', lambda prompt_files=None: {
        'provider': 'api88', 'model': 'm1', 'prompt_hash': 'abc',
    })
    pr.write_stamp(meta, video=video)
    _write_step(meta, 'step4', [{'id': 'c1', 'generated_title': 't'}])

    decision = pr.decide_resume(
        video=video, srt=srt, metadata_dir=meta, clips_only=True,
    )
    assert decision['stamp_ok'] is True
    assert decision['skip_transcription'] is True
    assert decision['start_step'] == 'done'
    assert decision['resumed_from'] == 'step4'
    assert decision['reuse_steps'] == frozenset({'step4'})


def test_clips_only_missing_step4_is_not_done(tmp_path, monkeypatch):
    """P2 #11: without step4, clips_only still resumes from subtitle / step1."""
    video = _video(tmp_path)
    srt = _srt(video)
    meta = _meta(tmp_path)
    monkeypatch.setattr(pr, 'current_model_stamp', lambda prompt_files=None: {
        'provider': 'api88', 'model': 'm1', 'prompt_hash': 'abc',
    })
    pr.write_stamp(meta, video=video)

    decision = pr.decide_resume(
        video=video, srt=srt, metadata_dir=meta, clips_only=True,
    )
    assert decision['stamp_ok'] is True
    assert decision['start_step'] != 'done'
    assert decision['start_step'] == 'step1'
    assert decision['resumed_from'] == 'subtitle'
    assert decision['reuse_steps'] == frozenset()


def test_clips_only_bad_stamp_clears_step4_not_done(tmp_path, monkeypatch):
    """P2 #11 + P1 #7: model mismatch under clips_only must not reuse old step4."""
    video = _video(tmp_path)
    srt = _srt(video)
    meta = _meta(tmp_path)
    monkeypatch.setattr(pr, 'current_model_stamp', lambda prompt_files=None: {
        'provider': 'old', 'model': 'A', 'prompt_hash': 'abc',
    })
    pr.write_stamp(meta, video=video, extra={'srt_origin': 'attached'})
    _write_step(meta, 'step4', [{'id': 'c1', 'generated_title': 'old'}])

    monkeypatch.setattr(pr, 'current_model_stamp', lambda prompt_files=None: {
        'provider': 'new', 'model': 'B', 'prompt_hash': 'abc',
    })
    decision = pr.decide_resume(
        video=video, srt=srt, metadata_dir=meta, clips_only=True,
    )
    assert decision['stamp_ok'] is False
    assert decision['start_step'] != 'done'
    assert decision['start_step'] == 'step1'
    assert decision['resumed_from'] == 'subtitle'
    assert not (meta / 'step4_titles.json').exists()
    assert srt.exists()


def test_clips_only_false_with_only_step4_is_not_done(tmp_path, monkeypatch):
    """Without clips_only, lone step4 still means first_missing_step=step1."""
    video = _video(tmp_path)
    srt = _srt(video)
    meta = _meta(tmp_path)
    monkeypatch.setattr(pr, 'current_model_stamp', lambda prompt_files=None: {
        'provider': 'api88', 'model': 'm1', 'prompt_hash': 'abc',
    })
    pr.write_stamp(meta, video=video)
    _write_step(meta, 'step4', [{'id': 'c1', 'generated_title': 't'}])

    decision = pr.decide_resume(
        video=video, srt=srt, metadata_dir=meta, clips_only=False,
    )
    assert decision['start_step'] == 'step1'
    assert decision['resumed_from'] == 'subtitle'


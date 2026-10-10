"""Shadow QA gate: each checker, the time budget, and an unchanged export."""
import hashlib
import json
import subprocess

import pytest

from backend.core import sentry_setup
from backend.services.studio import features, jobs, store
from backend.services.studio.models import QaReport
from backend.services.studio.qa import avsync, ending, face, jitter, loudness, record, report
from backend.utils.ffmpeg_utils import get_ffmpeg_path
from backend.utils.word_timing import write_word_timing


def _ctx(**overrides):
    values = dict(
        output=None, source=None, scenes=[], width=1080, height=1920, strategy_id='original',
        words=None, captions=False, title=False, packaged=False, title_y=0.12,
    )
    values.update(overrides)
    return report.Context(**values)


def _encode(path, *extra):
    subprocess.run([get_ffmpeg_path(), '-y', '-v', 'error', *extra, str(path)], check=True, timeout=30)


def test_avsync_threshold_and_buckets():
    assert avsync.judge_drift(0) == ('pass', 'lt40')
    assert avsync.judge_drift(40) == ('pass', 'lt40')
    assert avsync.judge_drift(-40) == ('pass', 'lt40')
    assert avsync.judge_drift(40.1) == ('fail', '40_80')
    assert avsync.judge_drift(80) == ('fail', '40_80')
    assert avsync.judge_drift(80.1) == ('fail', '80_200')
    assert avsync.judge_drift(200) == ('fail', '80_200')
    assert avsync.judge_drift(-250) == ('fail', 'gt200')


def test_avsync_media_fixtures(tmp_path):
    synced = tmp_path / 'synced.mp4'
    late = tmp_path / 'late.mp4'
    _encode(synced, '-f', 'lavfi', '-i', 'color=c=black:s=64x64:r=25:d=1',
            '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=1', '-shortest')
    _encode(late, '-f', 'lavfi', '-i', 'color=c=black:s=64x64:r=25:d=1',
            '-itsoffset', '0.12', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=1', '-shortest')
    assert avsync.check(_ctx(output=synced), 5) == ('pass', 'lt40')
    outcome, bucket = avsync.check(_ctx(output=late), 5)
    assert outcome == 'fail'
    assert bucket in {'80_200', 'gt200'}
    silent = tmp_path / 'silent.mp4'
    _encode(silent, '-f', 'lavfi', '-i', 'color=c=black:s=64x64:r=25:d=0.4')
    assert avsync.check(_ctx(output=silent), 5) == ('skip', 'no_audio')


def test_loudness_targets_peak_and_summary_text():
    assert loudness.judge_levels(-14.0, -1.5) == ('pass', 'in_target')
    assert loudness.judge_levels(-15.0, -1.0) == ('pass', 'in_target')
    assert loudness.judge_levels(-13.0, -2.0) == ('pass', 'in_target')
    assert loudness.judge_levels(-16.0, -2.0) == ('fail', 'quiet_1_3')
    assert loudness.judge_levels(-18.1, -2.0) == ('fail', 'quiet_gt3')
    assert loudness.judge_levels(-12.0, -2.0) == ('fail', 'loud_1_3')
    assert loudness.judge_levels(-10.0, -2.0) == ('fail', 'loud_gt3')
    assert loudness.judge_levels(-14.0, -0.9) == ('fail', 'peak')
    assert loudness.judge_levels(-10.0, -0.2) == ('fail', 'peak_and_level')
    quiet = 'I: -16.4 LUFS\nLRA: 4.0 LU\nThreshold: -26.0 LUFS\nPeak: -2.0 dBFS\n'
    hot = 'I: -16.4 LUFS\nLRA: 4.0 LU\nThreshold: -26.0 LUFS\nPeak: -0.4 dBFS\n'
    assert loudness.parse_summary(quiet) == (-16.4, -2.0)
    assert loudness.judge_levels(*loudness.parse_summary(quiet)) == ('fail', 'quiet_1_3')
    assert loudness.judge_levels(*loudness.parse_summary(hot)) == ('fail', 'peak_and_level')


def test_loudness_media_fixtures(tmp_path):
    quiet = tmp_path / 'quiet.m4a'
    loud = tmp_path / 'loud.m4a'
    _encode(quiet, '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=3',
            '-af', 'volume=-30dB', '-c:a', 'aac')
    _encode(loud, '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=3',
            '-af', 'volume=10dB', '-c:a', 'aac')
    quiet_levels = loudness.measure(quiet, 15)
    loud_levels = loudness.measure(loud, 15)
    assert loudness.judge_levels(*quiet_levels)[0] == 'fail'
    assert loudness.judge_levels(*loud_levels)[0] == 'fail'
    assert quiet_levels[0] < -14 < loud_levels[0]


def test_jitter_track_and_sampled_motion(monkeypatch):
    calm = jitter.judge_motion(0, 60, 0.1, 0.1)
    assert calm == ('pass', 'calm')
    width = 1000
    flashing = report.SceneSpan(0, 30, [(0.0, 0.0), (0.2, 0.2), (0.4, 0.0)])
    assert jitter.flashes(flashing.points, width) == 1
    assert jitter.check(_ctx(width=width, scenes=[flashing]), 1) == ('fail', 'flash')
    steady = report.SceneSpan(0, 30, [(0.0, 0.40), (10.0, 0.55), (20.0, 0.70)])
    assert jitter.check(_ctx(width=width, scenes=[steady]), 1) == ('pass', 'calm')

    def shaky(_path, _at, _timeout):
        return [(0.05, 0.0), (0.04, 0.0), (0.06, 0.0)]

    monkeypatch.setattr(jitter, '_sample_shifts', shaky)
    ctx = _ctx(width=1080, scenes=[report.SceneSpan(0, 2)])
    ctx.output = type('File', (), {'is_file': lambda self: True})()
    assert jitter.check(ctx, 1) == ('fail', 'rms')


def test_shift_estimator_sees_a_two_pixel_move():
    width, height = 16, 8

    def frame(column):
        raw = bytearray([20]) * (width * height)
        for y in range(height):
            raw[y * width + column] = 240
        return bytes(raw)

    assert jitter.estimate_shift(frame(4), frame(6), width, height) == (2.0, 0.0)
    assert jitter.estimate_shift(frame(4), frame(4), width, height) == (0.0, 0.0)


def test_ending_word_and_sentence_boundaries():
    words = [
        {'start': 0.0, 'end': 0.4, 'text': 'hello'},
        {'start': 0.4, 'end': 1.0, 'text': 'there.'},
        {'start': 1.2, 'end': 1.6, 'text': 'Next'},
    ]
    assert ending.judge_ending(words, 1.0, 0.0) == ('pass', 'complete')
    assert ending.judge_ending(words, 0.2, 0.0) == ('fail', 'mid_word')
    assert ending.judge_ending(words, 0.92, 0.0) == ('pass', 'complete')
    open_sentence = [
        {'start': 0.0, 'end': 1.0, 'text': 'there'},
        {'start': 1.2, 'end': 1.6, 'text': 'more'},
    ]
    assert ending.judge_ending(open_sentence, 1.0, 0.0) == ('fail', 'mid_sentence')
    assert ending.judge_ending(open_sentence, 1.0, 0.0)[1] != 'mid_word'
    paused = [
        {'start': 0.0, 'end': 1.0, 'text': 'there'},
        {'start': 1.8, 'end': 2.2, 'text': 'later'},
    ]
    assert ending.judge_ending(paused, 1.0, 0.0) == ('pass', 'complete')
    assert ending.judge_ending([], 1.0, 0.0) == ('skip', 'no_words')
    assert ending.check(_ctx(), 1) == ('skip', 'no_words')


def test_ending_uses_the_transcript_sidecar_and_drops_the_words(tmp_path, monkeypatch):
    srt = tmp_path / 'input.srt'
    srt.write_text('1\n00:00:00,000 --> 00:00:01,000\nhello there\n\n2\n00:00:01,200 --> 00:00:01,600\nmore\n', encoding='utf-8')
    write_word_timing(srt, [
        {'start': 0.0, 'end': 1.0, 'text': 'hello there', 'words': [
            {'start': 0.0, 'end': 0.4, 'text': 'hello'},
            {'start': 0.4, 'end': 1.0, 'text': 'there'},
        ]},
        {'start': 1.2, 'end': 1.6, 'text': 'more', 'words': [
            {'start': 1.2, 'end': 1.6, 'text': 'more'},
        ]},
    ])
    source = tmp_path / 'input.mp4'
    source.write_bytes(b'synthetic')
    monkeypatch.setattr('backend.services.publish_export.find_source_video', lambda _project: source)
    words = record._words(source)
    assert ending.judge_ending(words, 0.2, 0.0) == ('fail', 'mid_word')
    assert ending.judge_ending(words, 1.0, 0.0) == ('fail', 'mid_sentence')
    body = report.run_checks(
        report.Context(words=words, scenes=[report.SceneSpan(0.0, 1.0)]),
        (('ending', ending.check),),
    )
    dumped = json.dumps(body)
    assert 'hello' not in dumped and 'there' not in dumped and 'more' not in dumped
    assert body['checks'][0]['bucket'] == 'mid_sentence'


def test_face_overlap_buckets_and_detected_boxes(monkeypatch, tmp_path):
    assert face.judge_cover(0) == ('pass', 'none')
    assert face.judge_cover(0.09) == ('fail', 'lt10')
    assert face.judge_cover(0.10) == ('fail', '10_40')
    assert face.judge_cover(0.40) == ('fail', '10_40')
    assert face.judge_cover(0.41) == ('fail', 'gt40')
    clear = _ctx(captions=True)
    covered = _ctx(captions=True)
    rects = face.overlay_rects(1080, 1920, captions=True, title=False, packaged=False, title_y=0.12)
    assert face.covered_fraction((400, 400, 200, 200), rects) == 0
    assert face.covered_fraction((100, 1800, 80, 80), rects) > 0.4
    output = tmp_path / 'frame.mp4'
    output.write_bytes(b'not-decoded-here')

    def boxes(_path, _at, _w, _h, _timeout):
        return [(400.0, 400.0, 200.0, 200.0)]

    monkeypatch.setattr(face, 'detect_faces', boxes)
    monkeypatch.setattr('backend.services.studio.framing.is_installed', lambda: True)
    clear.output = output
    assert face.check(clear, 1) == ('pass', 'none')
    monkeypatch.setattr(face, 'detect_faces', lambda *_args: [(100.0, 1800.0, 80.0, 80.0)])
    covered.output = output
    assert face.check(covered, 1) == ('fail', 'gt40')
    assert face.check(_ctx(captions=False, title=False), 1) == ('pass', 'none')
    monkeypatch.setattr('backend.services.studio.framing.is_installed', lambda: False)
    assert face.check(covered, 1) == ('skip', 'no_detector')


def test_budget_skips_a_slow_checker_and_keeps_going():
    ticks = [0.0]

    def clock():
        return ticks[0]

    def slow(_ctx, _limit):
        ticks[0] = 5.0
        return 'fail', 'flash'

    def fine(_ctx, _limit):
        return 'pass', 'complete'

    body = report.run_checks(_ctx(), (('jitter', slow), ('ending', fine)), clock=clock)
    assert body['checks'][0]['checker'] == 'jitter'
    assert body['checks'][0]['outcome'] == 'skip'
    assert body['checks'][0]['bucket'] == 'timeout'
    assert body['checks'][1] == {
        'checker': 'ending', 'outcome': 'skip', 'bucket': 'budget', 'duration_ms': 0,
    }


def test_checker_exception_is_a_skip_and_a_sanitized_sentry_event(monkeypatch, tmp_path):
    captured = {}

    def explode(_ctx, _limit):
        raise RuntimeError(r'boom C:\secret\clip.mp4 transcript hello')

    def capture(error, phase):
        captured['error'] = error
        captured['phase'] = phase

    monkeypatch.setattr(report, 'capture_studio_exception', capture)
    body = report.run_checks(_ctx(), (('loudness', explode),))
    assert body['checks'][0]['outcome'] == 'skip'
    assert body['checks'][0]['bucket'] == 'error'
    assert str(captured['error']) == 'loudness'
    assert captured['phase'] == 'qa'
    assert 'secret' not in str(captured['error'])
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    event = {
        'tags': {'area': 'studio', 'phase': 'qa', 'error_code': 'unexpected', 'path': r'C:\secret\clip.mp4'},
        'exception': {'values': [{'type': 'QaCheckerError', 'value': r'C:\secret\clip.mp4 hello'}]},
    }
    clean = sentry_setup.before_send(event)
    assert clean['tags'] == {'area': 'studio', 'phase': 'qa', 'error_code': 'unexpected'}
    assert 'secret' not in json.dumps(clean)
    assert 'hello' not in json.dumps(clean)


def test_report_model_keeps_buckets_only():
    body = report.run_checks(_ctx(), record.RUNNERS)
    parsed = QaReport.model_validate(body)
    assert parsed.mode == 'shadow'
    assert [item.checker for item in parsed.checks] == list(report.CHECKERS)
    assert set(parsed.model_dump()) == {'schema_version', 'mode', 'duration_ms', 'checks'}
    with pytest.raises(Exception):
        QaReport.model_validate({**body, 'checks': [{**body['checks'][0], 'bucket': 'C:/secret'}]})


def test_feature_defaults_and_safe_mode_kill_switch():
    assert features.DEFAULTS['qa_gate_blocking'] == 'shadow'
    assert features.normalize_flag('qa_gate_blocking', 'blocking') == 'block'
    assert features.resolve_features(None)['qa_gate_blocking'] == 'shadow'
    assert features.resolve_features({'qa_gate_blocking': 'block'})['qa_gate_blocking'] == 'block'
    killed = features.resolve_features({'autoclip_safe_mode': True, 'qa_gate_blocking': 'block'})
    assert killed['qa_gate_blocking'] == 'off'
    forced = features.resolve_features({'autoclip_safe_mode': True}, env='qa_gate_blocking=block')
    assert forced['qa_gate_blocking'] == 'off'
    assert record.effective_mode({'qa_gate_blocking': 'block'}) == 'shadow'
    assert record.effective_mode({'qa_gate_blocking': 'off'}) == 'off'
    assert record.effective_mode({'autoclip_safe_mode': True, 'qa_gate_blocking': 'shadow'}) == 'off'
    assert features.flag_enabled(features.DEFAULTS, 'qa_gate_blocking') is False


def _project(tmp_path, monkeypatch, features_snapshot):
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    (tmp_path / 'privacy.json').write_text('{"crash_reports":false,"analytics":false}')
    monkeypatch.setattr(jobs, 'sync_project_completion', lambda _project_id: None)
    monkeypatch.setattr(jobs, '_design_covers', lambda *_args, **_kwargs: None)
    root = store.directory('qa-shadow')
    (root / 'raw').mkdir(parents=True)
    source = root / 'raw' / 'input.mp4'
    source.write_bytes(b'controlled original input')
    store.write('qa-shadow', {
        'drafts': [],
        'events': [],
        'jobs': [{'job_id': 'job-1', 'status': 'queued', 'instance': store.INSTANCE}],
        'output_variants': [{
            'id': 'v1', 'draft_id': 'd1', 'draft_revision': 1, 'strategy_id': 'original',
            'strategy_version': 1, 'status': 'running', 'render_job_id': 'job-1',
        }],
        'generation': {'status': 'rendering', 'auto_start': True, 'features': features_snapshot},
        'analysis': {'status': 'running', 'phase': 'rendering', 'run_id': 'flow', 'instance': store.INSTANCE},
    })
    return root, source


def test_shadow_render_writes_qa_and_leaves_the_export_bytes(tmp_path, monkeypatch):
    root, source = _project(tmp_path, monkeypatch, {'qa_gate_blocking': 'shadow'})
    output = root / 'output' / 'studio' / 'job-1.mp4'
    payload = b'rendered-bytes-v1'

    def fake_render(*_args, **_kwargs):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(payload)
        return {'path': str(output), 'width': 1080, 'height': 1920}

    monkeypatch.setattr(jobs, 'render_draft', fake_render)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    jobs._render('qa-shadow', object(), 'job-1')
    assert output.read_bytes() == payload
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    saved = store.read('qa-shadow')
    job = saved['jobs'][0]
    variant = saved['output_variants'][0]
    assert job['status'] == 'completed'
    assert job['result']['path'] == str(output)
    assert variant['status'] == 'completed'
    assert variant['qa']['mode'] == 'shadow'
    assert [item['checker'] for item in variant['qa']['checks']] == list(report.CHECKERS)
    assert job['qa'] == variant['qa']
    sidecar = json.loads(output.with_suffix('.qa.json').read_text(encoding='utf-8'))
    assert sidecar['mode'] == 'shadow'
    assert 'rendered-bytes' not in json.dumps(sidecar)
    assert output.read_bytes() == payload


def test_block_is_recorded_as_shadow_and_a_checker_crash_cannot_fail_the_export(tmp_path, monkeypatch):
    root, _source = _project(tmp_path, monkeypatch, {'qa_gate_blocking': 'block'})
    output = root / 'output' / 'studio' / 'job-1.mp4'
    payload = b'still-the-export'
    captured = []

    def fake_render(*_args, **_kwargs):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(payload)
        return {'path': str(output), 'width': 64, 'height': 64}

    def boom(*_args, **_kwargs):
        raise RuntimeError(r'C:\secret\clip.mp4')

    monkeypatch.setattr(jobs, 'render_draft', fake_render)
    monkeypatch.setattr(record, '_record', boom)
    monkeypatch.setattr(record, 'capture_studio_exception', lambda error, phase: captured.append((str(error), phase)))
    jobs._render('qa-shadow', object(), 'job-1')
    saved = store.read('qa-shadow')
    assert saved['jobs'][0]['status'] == 'completed'
    assert saved['output_variants'][0]['status'] == 'completed'
    assert 'qa' not in saved['output_variants'][0]
    assert output.read_bytes() == payload
    assert captured == [('runner', 'qa')]
    assert 'secret' not in captured[0][0]


def test_off_and_safe_mode_do_not_write_a_report(tmp_path, monkeypatch):
    root, _source = _project(tmp_path, monkeypatch, {'qa_gate_blocking': 'off'})
    output = root / 'output' / 'studio' / 'job-1.mp4'

    def fake_render(*_args, **_kwargs):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b'untouched')
        return {'path': str(output), 'width': 64, 'height': 64}

    monkeypatch.setattr(jobs, 'render_draft', fake_render)
    jobs._render('qa-shadow', object(), 'job-1')
    saved = store.read('qa-shadow')
    assert saved['jobs'][0]['status'] == 'completed'
    assert 'qa' not in saved['jobs'][0]
    assert 'qa' not in saved['output_variants'][0]
    assert not output.with_suffix('.qa.json').exists()
    assert output.read_bytes() == b'untouched'

    def arm_safe(data):
        data['jobs'].append({'job_id': 'job-2', 'status': 'queued', 'instance': store.INSTANCE})
        data['output_variants'].append({
            'id': 'v2', 'draft_id': 'd1', 'draft_revision': 1, 'strategy_id': 'original',
            'strategy_version': 1, 'status': 'running', 'render_job_id': 'job-2',
        })
        data['generation']['features'] = {'autoclip_safe_mode': True, 'qa_gate_blocking': 'shadow'}
        data['generation']['status'] = 'rendering'

    store.change('qa-shadow', arm_safe)
    second = root / 'output' / 'studio' / 'job-2.mp4'

    def render_second(*_args, **_kwargs):
        second.write_bytes(b'also-untouched')
        return {'path': str(second)}

    monkeypatch.setattr(jobs, 'render_draft', render_second)
    jobs._render('qa-shadow', object(), 'job-2')
    again = store.read('qa-shadow')
    assert again['jobs'][-1]['status'] == 'completed'
    assert 'qa' not in again['jobs'][-1]
    assert not second.with_suffix('.qa.json').exists()

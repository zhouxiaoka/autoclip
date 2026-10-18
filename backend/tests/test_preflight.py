"""Behavior tests for the public preflight entry."""
import asyncio
import json
import shutil
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.services import ai_model_settings as ai
from backend.services import whisper_runtime
from backend.services.studio import readiness
import ast

from backend.pipeline import media_precheck
"""#418 rewrite acceptance (design-retro.md, #418 section): invariants of the one preflight, checked through the
real entries. Every test drives a public entry (HTTP import / confirm / content pipeline / CLI / MCP) and asserts
the invariant there; none of them stubs the preflight itself."""

SRT = '1\n00:00:00,000 --> 00:00:02,000\nhi\n'
BROKEN = b'not a video at all' * 64


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    (tmp_path / 'privacy.json').write_text('{"analytics":false,"crash_reports":false}')
    monkeypatch.setattr(readiness, 'ensure_analysis_usable', lambda: None)


def settings(mode='subtitle'):
    ai.save(ai.ModelSettings(
        connections=[ai.Connection(id='a', name='A', provider='ollama', validation_status='ok')],
        analysis=ai.Assignment(connection_id='a', model='local-text', capability='text'),
        transcription=ai.Transcription(provider='whisper_local'), analysis_mode=mode))


def asr(monkeypatch, state):
    """'ready' | 'missing' (runtime not installed) | 'model_missing' | 'downloading'."""
    runtime = 'installed' if state != 'missing' else 'missing'
    monkeypatch.setattr(whisper_runtime, 'get_status', lambda *a, **k: {'status': runtime})
    check = {'ready': {'ok': True, 'code': 'whisper_installed'},
             'model_missing': {'ok': False, 'code': 'whisper_model_missing', 'repair': 'install_whisper', 'model': 'base'},
             'downloading': {'ok': False, 'code': 'whisper_model_downloading', 'repair': 'none', 'model': 'base'}}
    if state in check:
        monkeypatch.setattr(readiness, '_whisper_model', lambda name: dict(check[state]))


def media(path, seconds=40, audio=True):
    if not shutil.which('ffmpeg'):
        pytest.skip('ffmpeg required')
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', f'color=c=gray:s=160x90:d={seconds}']
    if audio:
        cmd += ['-f', 'lavfi', '-i', f'sine=frequency=440:duration={seconds}', '-shortest']
    subprocess.run(cmd + ['-pix_fmt', 'yuv420p', str(path)], check=True)
    return path


def broken(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(BROKEN)
    return path


def staging_empty(tmp_path):
    staging = tmp_path / 'import-staging'
    return not staging.exists() or not any(staging.iterdir())


def studio_import(monkeypatch, tmp_path, video_bytes, data=None, srt=False):
    from backend.api.v1 import studio as api
    created, inspected = [], []

    def _create(*a, **k):
        created.append(1)
        raise RuntimeError('stop after the preflight passed')
    monkeypatch.setattr(api.ProjectService, 'create_project', _create)
    monkeypatch.setattr(api.jobs, 'inspect_project', lambda *a, **k: inspected.append(1))
    app = FastAPI(); app.include_router(api.router)
    files = {'video': ('a.mp4', video_bytes, 'video/mp4')}
    if srt:
        files['subtitle'] = ('a.srt', SRT.encode(), 'application/x-subrip')
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post('/import', files=files, data={'auto_start': 'true', 'goal': 'auto', **(data or {})})
    return r, created, inspected


# ---------------------------------------------------------------- I1: unreadable first, before any paid call ---
@pytest.mark.real_media_probe
@pytest.mark.own_whisper_status
@pytest.mark.parametrize('with_srt', [False, True])
@pytest.mark.parametrize('asr_state', ['ready', 'missing'])
def test_i1_content_pipeline_broken_video_makes_zero_paid_calls(tmp_path, monkeypatch, with_srt, asr_state):
    """坏视频 × 有/无 SRT × ASR 就绪/未就绪 → source_unreadable, 0 paid calls (#285, #231a)."""
    settings('subtitle'); asr(monkeypatch, asr_state)
    from backend.services import simple_pipeline_adapter as mod
    monkeypatch.setattr(mod, 'clear_progress', lambda pid: None)
    monkeypatch.setattr(mod, 'emit_progress', lambda *a, **k: None)
    monkeypatch.setattr(mod.SimplePipelineAdapter, '_prompt_files', lambda self, d: {})
    adapter = mod.SimplePipelineAdapter('p-bad', 't-bad')
    paid = []
    monkeypatch.setattr(adapter, '_preflight_llm', lambda: paid.append('llm'))
    for name in ('run_step1_outline', 'run_step2_timeline', 'run_step3_scoring', 'run_step4_title'):
        monkeypatch.setattr(mod, name, lambda *a, _n=name, **k: paid.append(_n))

    async def transcribe(*a, **k):
        paid.append('asr')
    monkeypatch.setattr(adapter, '_generate_subtitle_automatically', transcribe)
    video = broken(tmp_path / 'in' / 'input.mp4')
    srt = ''
    if with_srt:
        (video.parent / 'input.srt').write_text(SRT, encoding='utf-8'); srt = str(video.parent / 'input.srt')
    result = asyncio.run(adapter.process_project_sync(str(video), srt, clips_only=True))
    assert result['status'] == 'failed'
    assert result.get('error_code') == 'source_unreadable', result
    assert paid == []


@pytest.mark.real_media_probe
@pytest.mark.own_whisper_status
@pytest.mark.parametrize('with_srt', [False, True])
@pytest.mark.parametrize('asr_state', ['ready', 'missing', 'downloading'])
def test_i1_studio_import_refuses_broken_video_directly_no_project_no_staging(tmp_path, monkeypatch, with_srt, asr_state):
    """#231c: the page gets source_unreadable at once (coded 422), not an install prompt and not a spinner;
    no project, no state, no staged file."""
    settings('auto'); asr(monkeypatch, asr_state)
    r, created, inspected = studio_import(monkeypatch, tmp_path, BROKEN, srt=with_srt)
    assert r.status_code == 422, r.text
    assert r.json()['detail']['code'] == 'source_unreadable'
    assert created == [] and inspected == [] and staging_empty(tmp_path)


@pytest.mark.real_media_probe
@pytest.mark.own_whisper_status
def test_i1_confirm_refuses_broken_video_before_any_install_prompt(tmp_path, monkeypatch):
    settings('subtitle'); asr(monkeypatch, 'missing')
    from backend.services.studio import jobs
    video = broken(tmp_path / 'raw' / 'input.mp4')
    state = {'plan': {'id': 'pl', 'recommended_analysis': 'subtitle', 'preferences': {}, 'source_duration': 60.0},
             'analysis': {'status': 'awaiting_confirmation'}}
    monkeypatch.setattr(jobs.store, 'read', lambda pid: state)
    monkeypatch.setattr(jobs, 'source', lambda pid: video)
    body = SimpleNamespace(plan_id='pl', analysis_mode=None, goals=['content'])
    with pytest.raises(ValueError) as caught:
        jobs.confirm_project('p', body)
    assert getattr(caught.value, 'code', None) == 'source_unreadable'
    assert not isinstance(caught.value, readiness.TranscriptionNotReady)


# --------------------------------------------------------------------- I2: CLI / MCP keep source_unreadable ---
@pytest.mark.real_media_probe
@pytest.mark.own_whisper_status
def test_i2_cli_json_keeps_source_unreadable(tmp_path, monkeypatch, capsys):
    settings('subtitle'); asr(monkeypatch, 'missing')
    from backend import cli
    from backend.services import local_runner
    video = broken(tmp_path / 'bad.mp4')
    args = SimpleNamespace(video=str(video), srt=None, name=None, category='default', min_score=None, no_db=True,
                           copy=True, json=True)
    outcome = {}
    rc = cli._cmd_run_body(args, outcome, lambda o: {'provider': 'x', 'model': 'y'}, local_runner.prepare_project,
                           lambda *a, **k: pytest.fail('pipeline ran'), lambda *a: None, 0)
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert rc != 0 and out['error_code'] == 'source_unreadable' and outcome['error_code'] == 'source_unreadable'


@pytest.mark.real_media_probe
@pytest.mark.own_whisper_status
def test_i2_mcp_job_keeps_source_unreadable(tmp_path, monkeypatch):
    settings('subtitle'); asr(monkeypatch, 'missing')
    from backend import mcp_server
    from backend.services import local_runner
    monkeypatch.setattr(local_runner, 'configure_llm', lambda o: {'provider': 'x'})
    monkeypatch.setattr(local_runner, 'run_pipeline', lambda *a, **k: pytest.fail('pipeline ran'))
    req = mcp_server._make_request(str(broken(tmp_path / 'bad.mp4')), None, None, 'default', None)
    job = mcp_server._run_job(req, None, False)
    assert job['status'] == 'failed' and job['error_code'] == 'source_unreadable'


# ------------------------------------------------------------------------ I3: at most one ffprobe per check ---
@pytest.mark.real_media_probe
@pytest.mark.own_whisper_status
def test_i3_one_ffprobe_and_the_decode_fallback_reuses_it(tmp_path, monkeypatch):
    """ffprobe answers without a duration: exactly one ffprobe, one ffmpeg decode, and the import proceeds."""
    settings('subtitle'); asr(monkeypatch, 'ready')
    real_run = subprocess.run
    calls = []

    def run(cmd, *a, **k):
        tool = Path(str(cmd[0])).name
        calls.append(tool)
        if tool.startswith('ffprobe'):
            return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps({'streams': [{'codec_type': 'video'}, {'codec_type': 'audio'}], 'format': {}}), stderr='')
        if tool.startswith('ffmpeg'):
            return subprocess.CompletedProcess(cmd, 0, stdout='', stderr='size=N/A time=00:00:42.00 bitrate=N/A')
        return real_run(cmd, *a, **k)
    monkeypatch.setattr(subprocess, 'run', run)
    from backend.api.v1 import transcription_gate
    video = broken(tmp_path / 'raw' / 'input.mp4')
    asyncio.run(transcription_gate.for_paths(video, None, sibling_srt=False))
    assert len([c for c in calls if 'ffprobe' in c]) == 1
    assert len([c for c in calls if 'ffmpeg' in c and 'ffprobe' not in c]) == 1


# --------------------------------------------------------------- I4: HTTP entries run it in the threadpool ---
@pytest.mark.real_media_probe
@pytest.mark.own_whisper_status
def test_i4_studio_import_probe_runs_off_the_event_loop(tmp_path, monkeypatch):
    settings('subtitle'); asr(monkeypatch, 'ready')
    seen = []
    real_run = subprocess.run

    def run(cmd, *a, **k):
        try:
            asyncio.get_running_loop(); seen.append('loop')
        except RuntimeError:
            seen.append('pool')
        return real_run(cmd, *a, **k)
    monkeypatch.setattr(subprocess, 'run', run)
    r, created, _ = studio_import(monkeypatch, tmp_path, BROKEN)
    assert r.status_code == 422 and seen and set(seen) == {'pool'}


# ----------------------------------------------------- I5: too short / no audio follow the actual route ---
@pytest.mark.real_media_probe
@pytest.mark.own_whisper_status
def test_i5_silent_source_blocks_on_subtitle_route_only(tmp_path, monkeypatch):
    asr(monkeypatch, 'ready')
    silent = media(tmp_path / 's.mp4', audio=False).read_bytes()
    settings('subtitle')
    r, _, _ = studio_import(monkeypatch, tmp_path, silent)
    assert r.status_code == 422 and r.json()['detail']['code'] == 'source_no_audio'
    from backend.services.studio import intelligence
    monkeypatch.setattr(intelligence, 'ready', lambda: True)
    settings('visual')
    r, created, _ = studio_import(monkeypatch, tmp_path, silent, {'goal': 'highlight'})
    assert created == [1], r.text  # visual route: the silent source passes the preflight


# ---------------------------------------------- I6: install codes (#281) and waiting codes stay distinct ---
@pytest.mark.real_media_probe
@pytest.mark.own_whisper_status
@pytest.mark.parametrize('state,code', [('missing', 'whisper_not_installed'), ('model_missing', 'whisper_model_missing'),
                                        ('downloading', 'whisper_model_downloading')])
def test_i6_readable_source_without_asr_gets_the_coded_install_state(tmp_path, monkeypatch, state, code):
    settings('subtitle'); asr(monkeypatch, state)
    r, created, _ = studio_import(monkeypatch, tmp_path, media(tmp_path / 'v.mp4').read_bytes())
    assert r.status_code == 422 and r.json()['detail']['code'] == code
    assert created == [] and staging_empty(tmp_path)


# ------------------------------------------------------- I7: "not probed" is never "probe failed" (tri-state) ---
@pytest.mark.real_media_probe
def test_i7_probe_states_are_distinct():
    from backend.services.studio import preflight
    assert preflight.NOT_PROBED.state is preflight.ProbeState.NOT_PROBED
    with pytest.raises(RuntimeError):
        preflight.classify_source(preflight.NOT_PROBED, srt_available=True, subtitle_route=True)
    unknown_audio = preflight.MaterialProbe(preflight.ProbeState.READABLE, Path('v'), 60.0, None)
    assert preflight.classify_source(unknown_audio, srt_available=False, subtitle_route=True) is None
    failed = preflight.MaterialProbe(preflight.ProbeState.UNREADABLE, Path('v'))
    assert preflight.classify_source(failed, srt_available=True, subtitle_route=False).code == 'source_unreadable'


# ------------------------------------------------- I3b (#351): planning reuses its own ffprobe, never a second ---
@pytest.mark.real_media_probe
@pytest.mark.own_whisper_status
def test_i3b_planning_recommend_missing_duration_one_ffprobe_then_decode(tmp_path, monkeypatch):
    """recommend(): its ffprobe answers without a duration -> one ffmpeg decode, not ffprobe -> ffprobe -> ffmpeg."""
    settings('subtitle'); asr(monkeypatch, 'ready')
    from backend.services.studio import planning
    from backend.services.studio.models import ImportOptions
    real_run, real_out = subprocess.run, subprocess.check_output
    calls = []

    def tool(cmd):
        return Path(str(cmd[0])).name

    def check_output(cmd, *a, **k):
        if tool(cmd).startswith('ffprobe'):
            calls.append('ffprobe')
            return json.dumps({'streams': [{'codec_type': 'video', 'width': 160, 'height': 90}], 'format': {}})
        return real_out(cmd, *a, **k)

    def run(cmd, *a, **k):
        name = tool(cmd)
        if name.startswith('ffprobe'):
            calls.append('ffprobe')
            return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps({'streams': [{'codec_type': 'video'}, {'codec_type': 'audio'}], 'format': {}}), stderr='')
        if name.startswith('ffmpeg'):
            calls.append('ffmpeg')
            return subprocess.CompletedProcess(cmd, 0, stdout='', stderr='size=N/A time=00:00:42.00 bitrate=N/A')
        return real_run(cmd, *a, **k)
    monkeypatch.setattr(subprocess, 'check_output', check_output)
    monkeypatch.setattr(subprocess, 'run', run)
    video = broken(tmp_path / 'p' / 'raw' / 'input.mp4')
    (video.parent / 'input.srt').write_text(SRT)
    try:
        planning.recommend(video, ImportOptions(goal='content', auto_start=False))
    except Exception:  # noqa: BLE001 - only the probe order before the first decode matters here
        pass
    first_decode = calls.index('ffmpeg')
    assert calls[:first_decode] == ['ffprobe'], calls


# --------------------------------------------- #352: for_project entries and MCP after-run code are guarded ---
@pytest.mark.real_media_probe
@pytest.mark.own_whisper_status
def test_i8_projects_process_endpoint_refuses_a_broken_project_source(tmp_path, monkeypatch):
    """POST /projects/{id}/process (the for_project preflight): an unreadable on-disk source is a coded 422 and
    processing is never started."""
    settings('subtitle'); asr(monkeypatch, 'ready')
    from backend.api.v1 import processing
    from backend.core.path_utils import get_project_raw_directory
    started = []
    app = FastAPI(); app.include_router(processing.router)
    app.dependency_overrides[processing.get_processing_service] = lambda: SimpleNamespace(process_project=lambda pid: started.append(pid) or {})
    broken(get_project_raw_directory('p418') / 'input.mp4')
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post('/projects/p418/process')
    assert r.status_code == 422 and r.json()['detail']['code'] == 'source_unreadable', r.text
    assert started == []


@pytest.mark.real_media_probe
@pytest.mark.own_whisper_status
def test_i9_mcp_job_keeps_the_pipeline_source_code_after_running(tmp_path, monkeypatch):
    """A failure the pipeline reports after it started (source_no_audio) stays that code on the MCP job."""
    from backend import mcp_server
    from backend.services import local_runner
    from backend.services.local_runner import RunRequest
    video = media(tmp_path / 'ok.mp4', seconds=40)
    monkeypatch.setattr(local_runner, 'configure_llm', lambda *a, **k: None)
    monkeypatch.setattr(local_runner, 'prepare_project', lambda req, link=False: video)
    monkeypatch.setattr(local_runner, 'run_pipeline', lambda req, v, on_progress=None: {
        'status': 'failed', 'error_code': 'source_no_audio', 'error': '这个视频没有声音'})
    req = RunRequest(video=video, project_id='mcp418')
    mcp_server._jobs[req.project_id] = {'status': 'queued'}
    job = mcp_server._run_job(req, None, False)
    assert job['status'] == 'failed' and job['error_code'] == 'source_no_audio'


@pytest.mark.real_media_probe
def test_i10_service_layer_never_imports_the_api_layer():
    """#354: the coded 422 shape lives in the API layer; services/studio/preflight.py has no backend.api import."""
    import ast
    src = Path(__file__).resolve().parents[1] / 'services' / 'studio' / 'preflight.py'
    names = []
    for node in ast.walk(ast.parse(src.read_text(encoding='utf-8'))):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
    assert not [n for n in names if n.startswith('backend.api')], names
"""preflight uses media_precheck through its public interface, never a private (_name) function."""

PREFLIGHT = Path(__file__).resolve().parents[1] / 'services' / 'studio' / 'preflight.py'


def test_preflight_uses_no_private_media_precheck_name():
    tree = ast.parse(PREFLIGHT.read_text(encoding='utf-8'))
    used = {node.attr for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'media_precheck'}
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and (node.module or '').endswith('media_precheck')
                for alias in node.names}
    private = sorted(name for name in used | imported if name.startswith('_'))
    assert not private, private
    assert 'ffmpeg_decode_duration' in used
    assert callable(media_precheck.ffmpeg_decode_duration)

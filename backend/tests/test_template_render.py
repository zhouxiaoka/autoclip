"""Top-3 HTML clips, classic downgrades, and an overlay used as ffmpeg input 1."""
import asyncio
import os
import subprocess
import time
from pathlib import Path

import pytest

from backend.services.studio import packaging_html as html
from backend.services.studio import store
from backend.services.studio.models import Draft, Packaging, Scene
from backend.services.studio.overlay_fill import build_fill, paint_fill
from backend.services.studio.template_choice import blocking_reason, html_candidate_ids, intel_mac_unverified, selected_template


def _drafts(scores):
    return [{'id': f'c{index}', '_auto_score': score} for index, score in enumerate(scores)]


def test_only_the_top_three_scored_clips_are_eligible():
    ids = html_candidate_ids(_drafts([1, 9, 3, 8, 2]))
    assert ids == {'c1', 'c2', 'c3'}
    assert html_candidate_ids([{'id': 'plain'}]) == set()
    assert selected_template({'html_template': 'street', 'features': {'pkg_templates_v1': True}}) == 'street'
    assert selected_template({'html_template': 'editorial', 'features': {'pkg_templates_v1': False}}) is None
    assert selected_template({'html_template': 'classic', 'features': {'pkg_templates_v1': True}}) is None
    assert selected_template({'html_template': 'editorial', 'features': {'pkg_templates_v1': True, 'autoclip_safe_mode': True}}) is None
    from backend.services.studio.template_choice import recorded_style, style_for_request, style_from_generation
    assert style_for_request('editorial', {'pkg_templates_v1': False}) == {'template': 'classic', 'requested_template': 'editorial'}
    assert style_for_request('street', {'pkg_templates_v1': True})['template'] == 'street'
    assert style_for_request(None) == {'template': 'classic', 'requested_template': 'classic'}
    with pytest.raises(ValueError):
        style_for_request('magazine')
    assert recorded_style('street', features={'pkg_templates_v1': False}) == {'template': 'classic', 'requested_template': 'street'}
    assert style_from_generation({'html_template': 'editorial', 'features': {'pkg_templates_v1': False}}) == {
        'template': 'classic', 'requested_template': 'editorial'}


def test_intel_mac_is_unverified_and_stays_classic():
    assert intel_mac_unverified('darwin', 'x86_64') is True
    assert intel_mac_unverified('darwin', 'arm64') is False
    assert intel_mac_unverified('win32', 'AMD64') is False
    assert blocking_reason({'pkg_templates_v1': True}, system='darwin', machine='x86_64', runtime_ready=True) == 'intel_mac_unverified'
    assert blocking_reason({'pkg_templates_v1': False}, system='linux', machine='x86_64', runtime_ready=True) == 'flag_off'
    assert blocking_reason({'pkg_templates_v1': True}, system='linux', machine='x86_64', runtime_ready=False) == 'missing_runtime'
    assert blocking_reason({'pkg_templates_v1': True}, system='linux', machine='x86_64', runtime_ready=True) is None


def test_fill_uses_packaging_fields_and_a_platform_safe_area():
    packaging = Packaging(version=2, template='editorial', audience_language='zh', title_lines=['钩子'], kicker='访谈',
                          cues=[{'start': 0.4, 'end': 1.0, 'text': '原话'}])
    fill = build_fill(packaging, 1.0, safe_area='douyin')
    assert build_fill(packaging, 1.0, fps=24, safe_area='douyin')['fps'] == 24
    assert fill['safe_area'] == 'douyin'
    assert fill['kicker'] == '访谈'
    assert fill['words'][0]['text'] == '原话'
    assert fill['stickers'] == []
    two = Packaging(version=2, template='editorial', audience_language='en', title_lines=['AI is a five-layer cake.', 'Energy is the bottom layer.'])
    # Each title line keeps its own line in the editorial headline.
    assert build_fill(two, 1.0)['hook']['text'] == 'AI is a five-layer cake.\nEnergy is the bottom layer.'


def test_issue_367_html_build_fill_honors_captions_switch():
    """P2/#396: HTML overlay fill ignored captions_enabled; ASS path already gated cues."""
    on = Packaging(version=2, template='editorial', audience_language='zh',
                   title_lines=['好的投资人'], cues=[{'start': 0.0, 'end': 1.0, 'text': '第一句'}])
    off = on.model_copy(update={'captions_enabled': False})
    filled_on = build_fill(on, 1.0)
    filled_off = build_fill(off, 1.0)
    assert filled_on['words'] and filled_on['words'][0]['text'] == '第一句'
    assert filled_off['words'] == []
    assert filled_off['title_lines'] == ['好的投资人']  # unpainted fill keeps the cover title
    assert filled_off['hook']['text'] == '好的投资人'
    # dict packaging (cache / older callers) must honor the flag too
    assert build_fill({'cues': [{'start': 0, 'end': 1, 'text': 'x'}], 'captions_enabled': False,
                       'title_lines': ['t']}, 1.0)['words'] == []
    painted_on = paint_fill(filled_on, on)
    painted_off = paint_fill(filled_off, off)
    assert painted_on['words'] and painted_on['title_lines'] == [] and painted_on['hook']['text'] == '' and painted_on['topic'] == ''
    assert painted_off['title_lines'] == [] and painted_off['hook']['text'] == '' and painted_off['topic'] == ''
    assert filled_on['title_lines'] == ['好的投资人']  # stripping the paint does not drop the cover title
    assert filled_off['title_lines'] == ['好的投资人']


def test_finished_clips_do_not_burn_the_cover_title():
    """Editorial, street, interview and podcast clips do not burn title_lines.

    The unpainted fill and the cover still keep them. Captions follow captions_enabled.
    Classic ASS has no Title, TitleAccent or Hook events, with captions on or off.
    """
    from backend.services.studio import packaging_render as pr
    from backend.services.studio.cover_design import title_lines_for
    scenes = [Scene(id='s', label='s', start=0, end=8)]
    cover_lines, accent = title_lines_for(
        {'title': 'post', 'packaging': {'title_lines': ['封面标题', '第二行'], 'title_accent_line': 0}},
        '', 'douyin',
    )
    assert cover_lines == ['封面标题', '第二行'] and accent == 0
    specs = [
        ('editorial', dict(template='interview_zh', audience_language='zh', title_lines=['好的投资人', '应该像飞行教练'], title_accent_line=1)),
        ('street', dict(template='interview_zh', audience_language='zh', title_lines=['街头一问', '七十秒'], title_accent_line=0)),
        ('editorial', dict(template='podcast_en', audience_language='en', title_lines=['A centred hook'])),
        ('street', dict(template='podcast_en', audience_language='en', title_lines=['Street question', 'Seventy seconds'])),
    ]
    for html_template, body in specs:
        on = Packaging(version=1, cues=[{'start': 0.4, 'end': 2.0, 'text': '字幕正文'}], **body)
        off = on.model_copy(update={'captions_enabled': False})
        filled_on = build_fill(on, 8, template=html_template)
        filled_off = build_fill(off, 8, template=html_template)
        assert filled_on['words'] and filled_off['words'] == []
        assert filled_on['title_lines'] == filled_off['title_lines'] == body['title_lines']
        assert filled_off['hook']['text'] == '\n'.join(body['title_lines'])
        for pack, filled in ((on, filled_on), (off, filled_off)):
            painted = paint_fill(filled, pack, html_template)
            assert painted['title_lines'] == [] and painted['hook_lines'] == [] and painted['topic'] == ''
            assert painted['hook']['text'] == ''
            assert filled['title_lines'] == body['title_lines']
        assert paint_fill(filled_on, on, html_template)['words']
        assert paint_fill(filled_off, off, html_template)['words'] == []
        for pack in (on, off):
            doc = pr.scene_ass(pack, scenes, 0)
            assert not any(token in doc for token in (',Title,', ',TitleAccent,', ',Hook,'))
            for line in body['title_lines']:
                assert line not in doc
        assert '字幕正文' in pr.scene_ass(on, scenes, 0)
        assert '字幕正文' not in pr.scene_ass(off, scenes, 0)
        titles_only = [line for line in pr.scene_ass(off, scenes, 0, titles_only=True).splitlines() if line.startswith('Dialogue:')]
        assert titles_only == []


def test_missing_runtime_and_over_budget_downgrade_without_raising(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setattr('backend.services.studio.template_choice.runtime_is_ready', lambda: False)
    missed = html.prepare_overlay('p1', 'editorial', None, 1.0, features={'pkg_templates_v1': True})
    assert missed.path is None and missed.downgrade_reason == 'missing_runtime' and missed.downgraded is True
    assert missed.template == 'classic' and missed.requested_template == 'editorial'
    assert missed.duration_ms >= 0

    calls = {'n': 0}

    def clock():
        calls['n'] += 1
        return 0.0 if calls['n'] == 1 else 100.0

    monkeypatch.setattr('backend.services.studio.template_choice.runtime_is_ready', lambda: True)
    over = html.prepare_overlay(
        'p1', 'street', None, 1.0, features={'pkg_templates_v1': True},
        capture=lambda count, _fps: [{'index': 0, 'count': count, 'png': b'png'}], clock=clock,
    )
    assert over.path is None and over.downgrade_reason == 'over_budget'
    assert html.budget_seconds() == 90


def test_changed_frames_are_cached_and_reused(tmp_path, monkeypatch):
    if not subprocess.run(['ffmpeg', '-version'], capture_output=True).returncode == 0:
        pytest.skip('ffmpeg unavailable')
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_TEMPLATE_BUDGET_SEC', '90')
    png = tmp_path / 'frame.png'
    subprocess.run([
        'ffmpeg', '-hide_banner', '-y', '-f', 'lavfi', '-i', 'color=c=red@0.4:s=16x16:d=0.04,format=rgba',
        '-frames:v', '1', '-update', '1', str(png),
    ], check=True, capture_output=True)
    blob = png.read_bytes()
    seen = {'n': 0}

    def capture(count, _fps):
        seen['n'] += 1
        return [{'index': 0, 'count': count, 'png': blob}]

    first = html.prepare_overlay('p1', 'editorial', None, 0.2, features={'pkg_templates_v1': True}, capture=capture)
    second = html.prepare_overlay('p1', 'editorial', None, 0.2, features={'pkg_templates_v1': True}, capture=capture)
    assert first.path and first.path.is_file() and second.path == first.path
    assert first.requested_template == 'editorial' and first.duration_ms >= 0
    assert seen['n'] == 1
    assert 'yuva444p' in html.ffv1_args()
    assert list(first.path.parent.glob('*.ffconcat')) == []
    assert list(first.path.parent.glob('*.partial')) == []


def test_overlay_is_the_second_ffmpeg_input(tmp_path, monkeypatch):
    if subprocess.run(['ffmpeg', '-version'], capture_output=True).returncode != 0:
        pytest.skip('ffmpeg unavailable')
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    root = store.directory('p1')
    root.mkdir(parents=True)
    (root / 'raw').mkdir()
    source = root / 'raw' / 'input.mp4'
    overlay = tmp_path / 'overlay.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=160x90:r=30:d=2', '-f', 'lavfi', '-i', 'sine=f=440:d=2', '-shortest', '-y', str(source)], check=True, capture_output=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=white@0.3:s=64x64:d=2,format=rgba', '-y', str(overlay)], check=True, capture_output=True)
    monkeypatch.setattr(html, 'prepare_overlay', lambda *args, **kwargs: html.OverlayJob(overlay, 'editorial', False, 'none', 'none', 'completed', requested_template='editorial', duration_ms=321))
    from backend.services import video_encoder
    from backend.services.studio.render import render_draft
    commands = []
    real = video_encoder.run_with_fallback

    def spy(build, run):
        commands.append(build('libx264'))
        return real(build, run)

    monkeypatch.setattr(video_encoder, 'run_with_fallback', spy)
    draft = Draft(id='d1', title='Short', scenes=[Scene(id='s1', start=0.0, end=0.4)], subtitles=False, original_audio=False, aspect='original', layout='fit')
    result = render_draft('p1', source, draft, 'job-html', lambda _p: None, html_template='editorial', features={'pkg_templates_v1': True})
    output = root / 'output' / 'studio' / 'job-html.mp4'
    assert output.is_file()
    assert result['template_render']['template'] == 'editorial'
    assert result['template_render']['requested_template'] == 'editorial'
    assert result['template_render']['duration_ms'] == 321
    assert result['template_render']['downgraded'] is False
    assert result['template_render']['failure_reason'] == 'none'
    inputs = [commands[0][index + 1] for index, token in enumerate(commands[0]) if token == '-i']
    assert Path(inputs[1]) == overlay

    classic = render_draft('p1', source, draft, 'job-classic', lambda _p: None, html_fallback='rank', requested_template='editorial', features={'pkg_templates_v1': True})
    assert (root / 'output' / 'studio' / 'job-classic.mp4').is_file()
    assert classic['template_render']['downgrade_reason'] == 'rank'
    assert classic['template_render']['downgraded'] is False
    assert classic['template_render']['outcome'] == 'skipped'
    assert classic['template_render']['template'] == 'classic'
    assert classic['template_render']['requested_template'] == 'editorial'
    assert 'secret' not in str(classic['template_render'])


def test_html_captions_off_does_not_burn_the_classic_title_over_the_face(tmp_path, monkeypatch):
    if subprocess.run(['ffmpeg', '-version'], capture_output=True).returncode != 0:
        pytest.skip('ffmpeg unavailable')
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    root = store.directory('p-title')
    root.mkdir(parents=True)
    source = _source(root)
    overlay = tmp_path / 'overlay.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=white@0.3:s=64x64:d=2,format=rgba', '-y', str(overlay)], check=True, capture_output=True)

    def fake_overlay(*args, **_kwargs):
        name = args[1]
        return html.OverlayJob(overlay, name, False, 'none', 'none', 'completed', requested_template=name, duration_ms=1)

    monkeypatch.setattr(html, 'prepare_overlay', fake_overlay)
    from backend.services import video_encoder
    from backend.services.studio.render import render_draft
    commands = []
    captured = {}
    real = video_encoder.run_with_fallback

    def spy(build, run):
        command = build('libx264')
        commands.append(command)
        graph = command[command.index('-filter_complex') + 1]
        if "ass='" in graph:
            start = graph.index("ass='") + len("ass='")
            path = graph[start:graph.index("'", start)].replace('\\:', ':').replace("\\'", "'")
            captured['ass'] = Path(path).read_text(encoding='utf-8')
        return real(build, run)

    monkeypatch.setattr(video_encoder, 'run_with_fallback', spy)

    def graph_of(draft, job_id, template):
        commands.clear()
        captured.clear()
        result = render_draft('p-title', source, draft, job_id, lambda _p: None, html_template=template, features={'pkg_templates_v1': True})
        assert result['template_render']['downgraded'] is False
        assert result['template'] == template
        assert len(commands) == 1
        return commands[0][commands[0].index('-filter_complex') + 1]

    scenes = [Scene(id='s1', start=0.0, end=0.4)]
    off = Draft(
        id='d-off', title='Short', scenes=scenes, subtitles=False, original_audio=False, aspect='original', layout='fit',
        packaging=Packaging(
            version=1, template='interview_zh', audience_language='zh', title_lines=['好的投资人'],
            captions_enabled=False, cues=[{'start': 0.0, 'end': 0.3, 'text': '字幕正文'}],
        ),
    )
    for template in ('editorial', 'street'):
        drafted = off.model_copy(update={'id': f'd-{template}'})
        graph = graph_of(drafted, f'job-{template}', template)
        assert 'ass=' not in graph and '[withtitle]' not in graph

    on = off.model_copy(update={
        'id': 'd-on',
        'packaging': off.packaging.model_copy(update={'captions_enabled': True}),
    })
    assert 'ass=' not in graph_of(on, 'job-on', 'editorial')


def _source(root: Path) -> Path:
    (root / 'raw').mkdir(exist_ok=True)
    source = root / 'raw' / 'input.mp4'
    if not source.is_file():
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=160x90:r=30:d=2', '-f', 'lavfi', '-i', 'sine=f=440:d=2', '-shortest', '-y', str(source)], check=True, capture_output=True)
    return source


def test_ffv1_uses_the_remaining_budget_instead_of_a_fixed_timeout(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_TEMPLATE_BUDGET_SEC', '40')
    seen = {}

    def capture(count, _fps):
        return [{'index': 0, 'count': count, 'png': b'png'}]

    def record(_holds, _dest, fps=30, *, timeout, run=None):
        seen['timeout'] = timeout
        seen['fps'] = fps
        raise html.OverlayEncodeError('encode')

    monkeypatch.setattr(html, 'encode_ffv1', record)
    job = html.prepare_overlay('p1', 'editorial', None, 0.2, features={'pkg_templates_v1': True}, capture=capture)
    assert job.failure_reason == 'encode'
    assert 0 < seen['timeout'] <= 40
    assert seen['timeout'] != 120


def test_a_hanging_capture_is_cut_by_the_whole_budget(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_TEMPLATE_BUDGET_SEC', '1')

    async def hang(_count, _fps):
        await asyncio.sleep(30)

    started = time.monotonic()
    job = html.prepare_overlay('p1', 'street', None, 1.0, features={'pkg_templates_v1': True}, capture=hang)
    elapsed = time.monotonic() - started
    assert job.path is None and job.downgrade_reason == 'over_budget' and job.downgraded is True
    assert job.requested_template == 'street' and job.template == 'classic'
    assert elapsed < 8
    assert job.duration_ms < 8000


def test_encode_failure_does_not_leave_a_reusable_cache(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_TEMPLATE_BUDGET_SEC', '30')

    def capture(count, _fps):
        return [{'index': 0, 'count': count, 'png': b'png'}]

    def boom(*_args, **_kwargs):
        raise html.OverlayEncodeError('encode')

    monkeypatch.setattr(html, 'encode_ffv1', boom)
    failed = html.prepare_overlay('p1', 'editorial', None, 0.2, features={'pkg_templates_v1': True}, capture=capture)
    folder = store.directory('p1') / 'output' / 'studio' / 'overlays'
    assert failed.path is None and failed.failure_reason == 'encode' and failed.requested_template == 'editorial'
    assert failed.template == 'classic' and failed.downgraded is True
    assert list(folder.glob('*.mkv')) == []
    assert list(folder.glob('*.partial')) == []


def test_a_corrupt_cache_is_recaptured_and_old_files_respect_the_cap(tmp_path, monkeypatch):
    if subprocess.run(['ffmpeg', '-version'], capture_output=True).returncode != 0:
        pytest.skip('ffmpeg unavailable')
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_OVERLAY_CACHE_BYTES', '100')
    png = tmp_path / 'frame.png'
    subprocess.run(['ffmpeg', '-hide_banner', '-y', '-f', 'lavfi', '-i', 'color=c=red@0.4:s=16x16:d=0.04,format=rgba', '-frames:v', '1', '-update', '1', str(png)], check=True, capture_output=True)
    blob = png.read_bytes()
    seen = {'n': 0}

    def capture(count, _fps):
        seen['n'] += 1
        return [{'index': 0, 'count': count, 'png': blob}]

    dest = html.overlay_cache_path(
        'p1', 'editorial', build_fill(None, 0.2, fps=30), frames=html.overlay_frame_count(0.2),
    )
    dest.write_bytes(b'not-a-movie')
    old = dest.parent / 'old.mkv'
    old.write_bytes(b'x' * 5000)
    os.utime(old, (1, 1))
    job = html.prepare_overlay('p1', 'editorial', None, 0.2, features={'pkg_templates_v1': True}, capture=capture)
    assert seen['n'] == 1
    assert job.path and job.path.is_file() and html._cache_usable(job.path)
    assert not old.exists()
    assert job.path.read_bytes()[:4] != b'not-'


def test_flag_off_ffmpeg_command_has_no_overlay_input(tmp_path, monkeypatch):
    if subprocess.run(['ffmpeg', '-version'], capture_output=True).returncode != 0:
        pytest.skip('ffmpeg unavailable')
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    root = store.directory('p1')
    root.mkdir(parents=True)
    source = _source(root)
    from backend.services import video_encoder
    from backend.services.studio.render import render_draft
    commands = []
    real = video_encoder.run_with_fallback

    def spy(build, run):
        commands.append(build('libx264'))
        return real(build, run)

    monkeypatch.setattr(video_encoder, 'run_with_fallback', spy)
    draft = Draft(id='d1', title='Short', scenes=[Scene(id='s1', start=0.0, end=0.4)], subtitles=False, original_audio=False, aspect='original', layout='fit')
    result = render_draft('p1', source, draft, 'job-off', lambda _p: None, html_template='editorial', features={'pkg_templates_v1': False})
    assert result['template_render']['downgrade_reason'] == 'flag_off'
    assert result['template_render']['downgraded'] is False
    assert result['template_render']['template'] == 'classic'
    assert result['template_render']['requested_template'] == 'editorial'
    assert result['template'] == 'classic' and result['requested_template'] == 'editorial'
    command = commands[0]
    inputs = [command[index + 1] for index, token in enumerate(command) if token == '-i']
    assert inputs == [str(source)]
    assert 'overlay=' not in ' '.join(command)


def test_an_html_failure_retries_classic_and_cancellation_still_aborts(tmp_path, monkeypatch):
    if subprocess.run(['ffmpeg', '-version'], capture_output=True).returncode != 0:
        pytest.skip('ffmpeg unavailable')
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    root = store.directory('p1')
    root.mkdir(parents=True)
    source = _source(root)
    overlay = tmp_path / 'overlay.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=white@0.3:s=64x64:d=2,format=rgba', '-y', str(overlay)], check=True, capture_output=True)
    monkeypatch.setattr(html, 'prepare_overlay', lambda *args, **kwargs: html.OverlayJob(overlay, 'editorial', False, 'none', 'none', 'completed', requested_template='editorial', duration_ms=10))
    from backend.core import project_cancellation
    from backend.services import video_encoder
    from backend.services.studio.render import render_draft
    calls = {'n': 0}
    real = video_encoder.run_with_fallback

    def spy(build, run):
        calls['n'] += 1
        if calls['n'] == 1:
            raise RuntimeError('filter blew up /tmp/secret.mp4')
        return real(build, run)

    monkeypatch.setattr(video_encoder, 'run_with_fallback', spy)
    draft = Draft(id='d1', title='Short', scenes=[Scene(id='s1', start=0.0, end=0.4)], subtitles=False, original_audio=False, aspect='original', layout='fit')
    result = render_draft('p1', source, draft, 'job-retry', lambda _p: None, html_template='editorial', features={'pkg_templates_v1': True})
    assert calls['n'] == 2
    assert result['template_render']['downgraded'] is True
    assert result['template_render']['template'] == 'classic'
    assert result['template_render']['requested_template'] == 'editorial'
    assert result['template_render']['downgrade_reason'] == 'capture'
    assert 'secret' not in str(result['template_render'])

    def cancel(_build, _run):
        raise project_cancellation.ProjectDeleted('p1')

    monkeypatch.setattr(video_encoder, 'run_with_fallback', cancel)
    with pytest.raises(project_cancellation.ProjectDeleted):
        render_draft('p1', source, draft, 'job-cancel', lambda _p: None, html_template='editorial', features={'pkg_templates_v1': True})


def test_job_duration_stays_the_whole_render_and_the_event_keeps_overlay_time(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    store.directory('p1').mkdir(parents=True)
    store.write('p1', {'drafts': [], 'jobs': [{'job_id': 'j1', 'status': 'queued', 'instance': store.INSTANCE}], 'generation': {'features': {'pkg_templates_v1': True}}})
    from backend.services.studio import jobs
    monkeypatch.setattr(jobs, 'source', lambda _project: 'video.mp4')
    monkeypatch.setattr(jobs, 'render_draft', lambda *_args, **_kwargs: {
        'template_render': {
            'template': 'editorial', 'requested_template': 'editorial', 'encoder': 'libx264',
            'downgraded': False, 'downgrade_reason': 'none', 'failure_reason': 'none',
            'outcome': 'completed', 'duration_ms': 321, 'os': 'linux', 'cpu_count': 2,
        },
    })
    monkeypatch.setattr(jobs, '_design_covers', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(jobs, '_sync_variant_status', lambda *_args, **_kwargs: None)
    jobs._render('p1', Draft(id='d1', title='Short', scenes=[Scene(id='s1', start=0.0, end=0.4)], subtitles=False), 'j1')
    saved = next(job for job in store.read('p1')['jobs'] if job['job_id'] == 'j1')
    assert saved['result']['template_render']['duration_ms'] == 321
    assert saved['duration_ms'] < 321

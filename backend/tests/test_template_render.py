"""Top-3 HTML clips, classic downgrades, and an overlay used as ffmpeg input 1."""
import subprocess
from pathlib import Path

import pytest

from backend.services.studio import packaging_html as html
from backend.services.studio import store
from backend.services.studio.models import Draft, Packaging, Scene
from backend.services.studio.overlay_fill import build_fill
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
    assert fill['safe_area'] == 'douyin'
    assert fill['kicker'] == '访谈'
    assert fill['words'][0]['text'] == '原话'
    assert fill['stickers'] == []


def test_missing_runtime_and_over_budget_downgrade_without_raising(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setattr('backend.services.studio.template_choice.runtime_is_ready', lambda: False)
    missed = html.prepare_overlay('p1', 'editorial', None, 1.0, features={'pkg_templates_v1': True})
    assert missed.path is None and missed.downgrade_reason == 'missing_runtime' and missed.downgraded is True

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
    assert seen['n'] == 1
    assert 'yuva444p' in html.ffv1_args()


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
    monkeypatch.setattr(html, 'prepare_overlay', lambda *args, **kwargs: html.OverlayJob(overlay, 'editorial', False, 'none', 'none', 'completed'))
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
    assert result['template_render']['downgraded'] is False
    assert result['template_render']['failure_reason'] == 'none'
    inputs = [commands[0][index + 1] for index, token in enumerate(commands[0]) if token == '-i']
    assert Path(inputs[1]) == overlay

    classic = render_draft('p1', source, draft, 'job-classic', lambda _p: None, html_fallback='rank', features={'pkg_templates_v1': True})
    assert (root / 'output' / 'studio' / 'job-classic.mp4').is_file()
    assert classic['template_render']['downgrade_reason'] == 'rank'
    assert classic['template_render']['template'] == 'classic'
    assert 'secret' not in str(classic['template_render'])

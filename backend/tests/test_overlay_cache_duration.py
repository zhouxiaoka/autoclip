"""Captions-off HTML overlays must not be reused across clips of different lengths.

paint_fill drops the title, and the hook length stops growing after about 2.4s, so two
clips of the same style then have the same painted fill. A cached overlay from the
shorter clip used to be reused, and ``shortest=1`` cut the longer one. The encode now
stops at the scene and repeats a short overlay's last frame. Mac smoke on 42c1e002:
a 57.9s editorial clip reused the project's 41s overlay.
"""
import subprocess
from types import SimpleNamespace

import pytest

from backend.services.studio import jobs, store
from backend.services.studio import packaging_html as html
from backend.services.studio.models import Draft, Packaging, Scene
from backend.services.studio.overlay_fill import build_fill, paint_fill


def _png(tmp_path):
    png = tmp_path / 'frame.png'
    subprocess.run(
        ['ffmpeg', '-hide_banner', '-y', '-f', 'lavfi', '-i', 'color=c=red@0.4:s=16x16:d=0.04,format=rgba',
         '-frames:v', '1', '-update', '1', str(png)],
        check=True, capture_output=True,
    )
    return png.read_bytes()


def _off(title, cue):
    return Packaging(
        template='interview_zh', audience_language='zh', title_lines=[title], captions_enabled=False,
        cues=[{'start': 0.4, 'end': 1.6, 'text': cue}],
    )


def _painted(packaging, duration, template):
    return paint_fill(build_fill(packaging, duration, fps=30, template=template), packaging)


@pytest.mark.parametrize('template', ['editorial', 'street'])
def test_captions_off_overlay_cache_keeps_each_clips_duration(tmp_path, monkeypatch, template):
    if subprocess.run(['ffmpeg', '-version'], capture_output=True, check=False).returncode != 0:
        pytest.skip('ffmpeg unavailable')
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_FLAGS', '')
    monkeypatch.setenv('AUTOCLIP_TEMPLATE_BUDGET_SEC', '90')
    blob = _png(tmp_path)
    short_pack = _off('短片标题', '第一条字幕')
    long_pack = _off('更长成片的标题', '另一条字幕')
    # #475: captions-off used to paint the same pixels past the hook, so only the frame count
    # kept a short overlay from being reused on a longer clip.
    # The fill now records the clip duration (`T`). That still must not collapse the two movies.
    short_fill, long_fill = _painted(short_pack, 3, template), _painted(long_pack, 5, template)
    assert short_fill['T'] == 3 and long_fill['T'] == 5
    assert short_fill != long_fill
    seen = []

    def capture(count, _fps):
        seen.append(count)
        return [{'index': 0, 'count': count, 'png': blob}]

    short = html.prepare_overlay(
        'p1', template, short_pack, 3, features={'pkg_templates_v1': True}, capture=capture,
    )
    long = html.prepare_overlay(
        'p1', template, long_pack, 5, features={'pkg_templates_v1': True}, capture=capture,
    )
    short_frames = html.overlay_frame_count(3)
    long_frames = html.overlay_frame_count(5)
    assert seen == [short_frames, long_frames]
    assert short.path != long.path
    assert html._overlay_duration(short.path) == pytest.approx(3, abs=0.1)
    assert html._overlay_duration(long.path) == pytest.approx(5, abs=0.1)

    # A finished movie of the wrong length, sitting on the longer clip's own cache name.
    long.path.write_bytes(short.path.read_bytes())
    assert html._overlay_duration(long.path) == pytest.approx(3, abs=0.1)
    again = html.prepare_overlay(
        'p1', template, long_pack, 5, features={'pkg_templates_v1': True}, capture=capture,
    )
    assert seen == [short_frames, long_frames, long_frames]
    assert again.path == long.path
    assert html._overlay_duration(again.path) == pytest.approx(5, abs=0.1)
    reused = html.prepare_overlay(
        'p1', template, long_pack, 5, features={'pkg_templates_v1': True}, capture=capture,
    )
    assert reused.path == long.path and seen == [short_frames, long_frames, long_frames]
    # Same length, different painted content stays a different movie.
    # Editorial captions-off clears the kicker; the folio issue is still painted.
    other = long_pack.model_copy(update={'issue': '另一期'})
    assert _painted(other, 5, template) != _painted(long_pack, 5, template)
    different = html.prepare_overlay(
        'p1', template, other, 5, features={'pkg_templates_v1': True}, capture=capture,
    )
    assert different.path != long.path
    assert seen[-1] == long_frames and len(seen) == 4


@pytest.mark.parametrize('template', ['editorial', 'street'])
def test_editor_reexport_captions_off_does_not_cut_the_longer_clip(tmp_path, monkeypatch, template):
    """The editor route renders through the same overlay cache as automatic production."""
    if subprocess.run(['ffmpeg', '-version'], capture_output=True, check=False).returncode != 0:
        pytest.skip('ffmpeg unavailable')
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_FLAGS', '')
    monkeypatch.setenv('AUTOCLIP_TEMPLATE_BUDGET_SEC', '90')
    root = store.directory('p1')
    raw = root / 'raw'
    raw.mkdir(parents=True)
    source = raw / 'input.mp4'
    subprocess.run(
        ['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=320x180:r=30:d=8',
         '-f', 'lavfi', '-i', 'sine=f=440:d=8', '-shortest', '-y', str(source)],
        check=True, capture_output=True,
    )
    blob = _png(tmp_path)
    requested = []

    async def capture(_template, _fill, frames, _fps, _capture):
        requested.append(frames)
        return [{'index': 0, 'count': frames, 'png': blob}]

    monkeypatch.setattr(html, '_bounded_capture', capture)
    monkeypatch.setattr('backend.services.studio.template_choice.runtime_is_ready', lambda: True)
    queued = []
    monkeypatch.setattr(jobs, 'render_executor', SimpleNamespace(submit=lambda fn, *args, **kwargs: queued.append((fn, args, kwargs))))

    def draft(draft_id, title, end, cue):
        return Draft(
            id=draft_id, title=title, revision=2, subtitles=False, original_audio=False, aspect='original',
            scenes=[Scene(id='s', start=0, end=end)],
            packaging=_off(title, cue),
        )

    short = draft('d-short', '短片标题', 3, '第一条字幕')
    long = draft('d-long', '更长成片的标题', 5, '另一条字幕')
    variant = {'html_template': template, 'strategy_id': 'xiaohongshu', 'branding': {'outro_enabled': False}}
    store.write('p1', {
        'schema_version': 2, 'drafts': [short.model_dump(), long.model_dump()], 'jobs': [], 'events': [],
        'analysis': None, 'output_variants': [],
        'generation': {'features': {'pkg_templates_v1': True}},
    })
    # Same arguments POST /studio/{id}/drafts/{draft_id}/export passes after reading the variant.
    for item in (short, long):
        jobs.export('p1', item, brand_outro=False, **jobs.template_export_kwargs(variant))
    assert len(queued) == 2
    for fn, args, kwargs in queued:
        fn(*args, **kwargs)

    saved = {job['draft_id']: job for job in store.read('p1')['jobs']}
    assert saved['d-short']['status'] == 'completed', saved['d-short'].get('error')
    assert saved['d-long']['status'] == 'completed', saved['d-long'].get('error')
    assert saved['d-short']['result']['template'] == template
    assert saved['d-long']['result']['template'] == template
    assert requested == [html.overlay_frame_count(3), html.overlay_frame_count(5)]
    short_video = root / 'output' / 'studio' / f"{saved['d-short']['job_id']}.mp4"
    long_video = root / 'output' / 'studio' / f"{saved['d-long']['job_id']}.mp4"
    assert html._overlay_duration(short_video) == pytest.approx(3, abs=0.5)
    assert html._overlay_duration(long_video) == pytest.approx(5, abs=0.5)


def test_a_fresh_overlay_shorter_than_the_clip_is_discarded(tmp_path, monkeypatch):
    if subprocess.run(['ffmpeg', '-version'], capture_output=True, check=False).returncode != 0:
        pytest.skip('ffmpeg unavailable')
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_FLAGS', '')
    monkeypatch.setenv('AUTOCLIP_TEMPLATE_BUDGET_SEC', '90')
    blob = _png(tmp_path)
    real = html.encode_ffv1

    def shrink(holds, dest, fps=30, timeout=30, run=None):
        real([(holds[0][0], 1)], dest, fps=fps, timeout=timeout, run=run)

    monkeypatch.setattr(html, 'encode_ffv1', shrink)
    job = html.prepare_overlay(
        'p1', 'editorial', _off('标题', '字幕'), 3,
        features={'pkg_templates_v1': True},
        capture=lambda count, _fps: [{'index': 0, 'count': count, 'png': blob}],
    )
    assert job.path is None
    assert job.failure_reason == 'encode' and job.downgraded is True
    folder = store.directory('p1') / 'output' / 'studio' / 'overlays'
    assert not list(folder.glob('*.mkv'))

"""HTML 9:16 crops must be framed on the output window, not the 4:3 interview window.

Douyin and Xiaohongshu classic templates frame a 1080x810 interview window. Editorial and street
cover the full 1080x1920 frame, then composite a transparent overlay. Reusing the 4:3 crop_x for
that narrower window slices an off-center speaker. The classic retry after an overlay failure
renders the same draft, so it needs the same 9:16 crop. Rank fallback stays on the interview window.
"""
import subprocess

import pytest
from PIL import Image, ImageDraw

from backend.services.studio import framing, jobs
from backend.services.studio.framing import layout_filter, window_fraction
from backend.services.studio.models import Scene
from backend.utils.ffmpeg_utils import get_ffmpeg_path

SOURCE = (960, 540)  # 16:9, same cover fraction as 1920x1080
PORTRAIT = (1080, 1920)
FACE = (0.64, 0.80)  # subject on the right third; center 0.72
MARKER = (0.64, 0.67)  # red stripe on the left edge of the face
CENTER = 0.72
PLATFORMS = ('douyin', 'xiaohongshu', 'tiktok', 'instagram_reels', 'youtube_shorts')
HTML_PLATFORMS = ('douyin', 'xiaohongshu')
PODCAST_PLATFORMS = ('tiktok', 'instagram_reels', 'youtube_shorts')


def _span(crop_x, fraction):
    left = crop_x * (1.0 - fraction)
    return left, left + fraction


def _covers(crop_x, fraction, box):
    left, right = _span(crop_x, fraction)
    return left <= box[0] + 1e-6 and right + 1e-6 >= box[1]


def _still(path):
    """A 16:9 frame: dark room, a face on the right third, a red stripe on the face's left edge."""
    width, height = SOURCE
    image = Image.new('RGB', SOURCE, (0x1A, 0x1A, 0x19))
    draw = ImageDraw.Draw(image)
    face_left = round(FACE[0] * width)
    face_right = round(FACE[1] * width)
    marker_right = round(MARKER[1] * width)
    top, bottom = 90, 450
    draw.rectangle([face_left, top, face_right, bottom], fill=(0xF6, 0xD7, 0xB8))
    draw.rectangle([face_left, top - 36, face_right - 18, top + 28], fill=(0x2A, 0x24, 0x20))
    eye = top + 70
    draw.ellipse([face_left + 46, eye, face_left + 64, eye + 18], fill=(0x1A, 0x1A, 0x19))
    draw.ellipse([face_left + 88, eye, face_left + 106, eye + 18], fill=(0x1A, 0x1A, 0x19))
    # Drawn last so the witness stripe is pure red, not blended with skin.
    draw.rectangle([face_left, top, marker_right, bottom], fill=(0xFF, 0x00, 0x33))
    image.save(path)


def _video(still, path):
    subprocess.run(
        [get_ffmpeg_path(), '-y', '-v', 'error', '-loop', '1', '-i', str(still),
         '-t', '1', '-r', '12', '-pix_fmt', 'yuv420p', str(path)],
        check=True, capture_output=True,
    )


def _red_pixels(still, crop_x, size):
    """Pixels of the witness stripe after the same cover-crop the renderer applies."""
    width, height = size
    proc = subprocess.run(
        [get_ffmpeg_path(), '-v', 'error', '-i', str(still),
         '-vf', (f'scale={width}:{height}:force_original_aspect_ratio=increase,'
                 f"crop={width}:{height}:x='(iw-ow)*{crop_x}':y=(ih-oh)/2"),
         '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
        check=True, capture_output=True,
    )
    raw = proc.stdout
    count = 0
    for index in range(0, len(raw), 3):
        red, green, blue = raw[index], raw[index + 1], raw[index + 2]
        if red > 220 and green < 50 and blue < 70:
            count += 1
    return count


def _clips():
    # Four scored clips: the top three are HTML candidates, the last is rank fallback.
    scores = (9, 8, 7, 1)
    clips = []
    for index, score in enumerate(scores):
        start = float(index * 10)
        clips.append({
            'id': f'c{index}',
            'title': f'Clip {index}',
            'scenes': [{'id': f'c{index}-s', 'label': 'S', 'start': start, 'end': start + 2.0}],
            jobs.SCORE_KEY: score,
        })
    return clips


def _arm(monkeypatch, video):
    monkeypatch.delenv('AUTOCLIP_FLAGS', raising=False)
    monkeypatch.setattr(jobs.store, 'read', lambda _pid, **_k: {'generation': {'portrait_style': 'auto'}})
    monkeypatch.setattr(jobs, '_source_has_burned_subtitles', lambda *_a, **_k: False)
    monkeypatch.setattr(jobs, '_content_drafts', lambda *_a, **_k: _clips())
    monkeypatch.setattr(jobs, '_prefetch_packaging', lambda *_a, **_k: None)
    monkeypatch.setattr(jobs, '_posts_for', lambda *_a, **_k: {})
    monkeypatch.setattr(jobs, '_apply_packaging', lambda _pid, value, *_a, **_k: value)
    monkeypatch.setattr(framing, 'is_installed', lambda: True)
    monkeypatch.setattr(framing, 'detect_cuts', lambda *_a, **_k: [])
    monkeypatch.setattr(framing, '_grab_shot', lambda _video, _start, _end, times, _folder, _key: [(at, (video, video)) for at in times])
    monkeypatch.setattr(framing, '_observe_pair', lambda _pair: {
        'frontal': [{'x': CENTER, 'w': 0.12, 'motion': 0.0, 'area': 1.0}],
        'turned': [],
    })


def _derive(video, template):
    generation = {'features': {'pkg_templates_v1': True}, 'output_captions': True}
    if template:
        generation['html_template'] = template
    drafts, variants, _events = jobs._initial_derive(
        'p1', {}, str(video), generation, list(PLATFORMS), {'outro_enabled': False}, [],
    )
    by_id = {draft['id']: draft for draft in drafts}
    indexed = {}
    for variant in variants:
        draft = by_id[variant['draft_id']]
        start = draft['scenes'][0]['start']
        indexed[(variant['strategy_id'], start)] = (draft, variant)
    return indexed


def _crop_used(draft):
    """crop_x baked into the classic picture filter. Overlay failure reuses this draft."""
    scene = draft['scenes'][0]
    graph = layout_filter(Scene.model_validate(scene), draft['crop_x'], *PORTRAIT)
    token = "(iw-ow)*"
    assert token in graph
    return float(graph.split(token, 1)[1].split("'", 1)[0])


@pytest.mark.parametrize('template', ['editorial', 'street'])
def test_html_9x16_crop_contains_an_off_center_face(tmp_path, monkeypatch, template):
    still = tmp_path / 'speaker.png'
    video = tmp_path / 'speaker.mp4'
    _still(still)
    _video(still, video)
    _arm(monkeypatch, video)
    html = _derive(video, template)
    classic = _derive(video, None)
    portrait_fraction = window_fraction(*SOURCE, *PORTRAIT)
    interview_fraction = window_fraction(*SOURCE, *jobs.INTERVIEW_WINDOW)

    html_starts = (0.0, 10.0, 20.0)
    rank_start = 30.0
    for start in (*html_starts, rank_start):
        for strategy_id in PODCAST_PLATFORMS:
            html_draft, html_variant = html[(strategy_id, start)]
            classic_draft, classic_variant = classic[(strategy_id, start)]
            assert html_draft['scenes'][0]['crop_x'] == classic_draft['scenes'][0]['crop_x']
            assert html_draft['scenes'][0]['crop_track'] == classic_draft['scenes'][0]['crop_track']
            assert html_draft['layout'] == classic_draft['layout'] == 'crop'
            assert 'html_template' not in classic_variant and 'html_fallback' not in classic_variant

    for strategy_id in HTML_PLATFORMS:
        classic_draft, classic_variant = classic[(strategy_id, 0.0)]
        assert classic_draft['layout'] == 'window'
        assert 'html_template' not in classic_variant
        classic_crop = classic_draft['scenes'][0]['crop_x']
        assert _covers(classic_crop, interview_fraction, FACE)
        # The fixture only discriminates when the 4:3 crop, reused as 9:16, misses the stripe.
        assert not _covers(classic_crop, portrait_fraction, MARKER)
        assert _red_pixels(still, classic_crop, PORTRAIT) == 0

        rank_draft, rank_variant = html[(strategy_id, rank_start)]
        assert rank_variant['html_fallback'] == 'rank'
        assert rank_variant['requested_template'] == template
        assert 'html_template' not in rank_variant
        assert rank_draft['layout'] == 'window'
        assert rank_draft['scenes'][0]['crop_x'] == classic[(strategy_id, rank_start)][0]['scenes'][0]['crop_x']
        assert rank_draft['scenes'][0]['crop_track'] == classic[(strategy_id, rank_start)][0]['scenes'][0]['crop_track']

    for start in html_starts:
        for strategy_id in HTML_PLATFORMS:
            draft, variant = html[(strategy_id, start)]
            assert variant['html_template'] == template
            assert variant['framing'] == 'speaker'
            assert draft['layout'] == 'crop'
            crop_x = draft['scenes'][0]['crop_x']
            classic_crop = classic[(strategy_id, start)][0]['scenes'][0]['crop_x']
            podcast_crop = html[('tiktok', start)][0]['scenes'][0]['crop_x']
            assert crop_x == podcast_crop
            assert crop_x != classic_crop
            assert _covers(crop_x, portrait_fraction, FACE)
            assert _covers(crop_x, portrait_fraction, (CENTER, CENTER))
            # Downgraded classic renders this draft through layout_filter and does not reframe.
            assert _crop_used(draft) == crop_x
            assert _red_pixels(still, _crop_used(draft), PORTRAIT) > 0

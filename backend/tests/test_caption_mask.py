"""Burned captions the audience cannot read are blurred out, and that version gets ours instead."""
import shutil
import subprocess

import pytest

from backend.services.studio import burned_subtitles, jobs, render, store


def _generation(language='zh', band=(0.82, 0.95)):
    return {'generation': {'source_has_burned_subtitles': True, 'burned_caption_language': language, 'burned_caption_band': list(band)}}


def test_only_english_versions_of_non_english_captions_are_masked(monkeypatch):
    monkeypatch.setattr(store, 'read', lambda _pid: _generation())
    assert jobs._caption_mask('p', 'tiktok') == [0.82, 0.95]
    assert jobs._caption_mask('p', 'youtube_long') == [0.82, 0.95]
    assert jobs._caption_mask('p', 'douyin') is None, 'Chinese captions are what a Douyin viewer reads'
    monkeypatch.setattr(store, 'read', lambda _pid: _generation(language='en'))
    assert jobs._caption_mask('p', 'tiktok') is None, 'English captions already suit TikTok'


def test_a_masked_version_is_framed_and_captioned_like_a_caption_free_source(monkeypatch):
    monkeypatch.setattr(store, 'read', lambda _pid: _generation())
    value = jobs._apply_packaging('p', {'id': 'd', 'title': 'x', 'scenes': [{'id': 's', 'label': 'x', 'start': 0.0, 'end': 90.0}]}, 'youtube_long', True, {})
    assert value['caption_mask'] == [0.82, 0.95]
    draft = jobs._apply_strategy(value, 'youtube_long', burned_subtitles=True)
    assert draft.subtitles is True and draft.caption_mask == (0.82, 0.95), 'our English captions replace the blurred ones'


def test_the_caption_band_comes_from_the_glyph_rows():
    width = burned_subtitles.BAND_WIDTH
    rows = range(120, 160)  # lower part of the sampled band
    mask = {y * width + x for y in rows for x in range(300, 700, 3)}
    top, bottom = burned_subtitles.caption_band([mask, mask, mask])
    assert 0.65 + 0.35 * 120 / 192 - 0.03 < top < 0.65 + 0.35 * 120 / 192
    assert 0.65 + 0.35 * 160 / 192 < bottom <= 1.0


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='ffmpeg not installed')
@pytest.mark.parametrize('graph', [
    '[0:v]scale=540:960:force_original_aspect_ratio=increase,crop=540:960[base]',
    '[0:v]split=2[bg][fg];[bg]scale=540:960,boxblur=10[b];[fg]scale=540:-2[f];[b][f]overlay=0:(H-h)/2[base]',
    None,
])
def test_the_masked_graph_runs_in_ffmpeg(tmp_path, graph):
    built, mapped = render._mask_captions(graph, (0.8, 0.95))
    out = tmp_path / 'frame.png'
    cmd = ['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc=size=1280x720:rate=30', '-filter_complex', built,
           '-map', mapped or '[base]', '-frames:v', '1', '-y', str(out)]
    assert subprocess.run(cmd, capture_output=True).returncode == 0
    assert out.stat().st_size > 0

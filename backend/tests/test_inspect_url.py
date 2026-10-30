"""F4: inspect_url metadata + preview_route mapping (mocked yt-dlp)."""
from __future__ import annotations

import pytest

from backend.services.studio import jobs, planning


def test_platform_subtitle_code_matches_language():
    # Same rule as legacy _fetch_platform_subtitles: code == language OR code base == language.
    assert jobs._platform_subtitle_code({'language': 'zh', 'subtitles': {'zh-CN': [{}], 'en': [{}]}}) == 'zh-CN'
    assert jobs._platform_subtitle_code({'language': 'en', 'subtitles': {'en-US': [{}]}}) == 'en-US'
    assert jobs._platform_subtitle_code({'language': 'zh-CN', 'subtitles': {'zh': [{}]}}) is None
    assert jobs._platform_subtitle_code({'language': 'ja', 'subtitles': {'en': [{}]}}) is None
    assert jobs._platform_subtitle_code({'subtitles': {'en': [{}]}}) is None


def test_info_has_audio_from_formats():
    assert jobs._info_has_audio({'formats': [{'vcodec': 'avc1', 'acodec': 'none'}, {'acodec': 'mp4a'}]}) is True
    assert jobs._info_has_audio({'formats': [{'vcodec': 'avc1', 'acodec': 'none'}]}) is False
    assert jobs._info_has_audio({'formats': []}) is None


def test_inspect_url_returns_meta(monkeypatch):
    captured = {}

    def fake_extract(url, options):
        captured['url'] = url
        captured['options'] = options
        return {
            'title': 'Demo Clip',
            'duration': 125.5,
            'language': 'zh',
            'subtitles': {'zh': [{'ext': 'srt'}]},
            'thumbnail': 'https://example.com/t.jpg',
            'formats': [
                {'height': 720, 'vcodec': 'avc1', 'acodec': 'none'},
                {'height': 1080, 'vcodec': 'avc1', 'acodec': 'mp4a'},
            ],
        }

    monkeypatch.setattr('backend.utils.download_recovery.extract_info_with_recovery', fake_extract)
    monkeypatch.setattr('backend.utils.ffmpeg_utils.get_ffmpeg_path', lambda: '/bin/ffmpeg')
    monkeypatch.setattr('backend.utils.ffmpeg_utils.ytdlp_js_runtimes', lambda: {})
    meta = jobs.inspect_url('https://www.youtube.com/watch?v=abc', browser='chrome')
    assert meta['title'] == 'Demo Clip'
    assert meta['duration'] == 125.5
    assert meta['has_manual_subtitle'] is True
    assert meta['max_height'] == 1080
    assert meta['thumbnail'] == 'https://example.com/t.jpg'
    assert meta['has_audio'] is True
    assert captured['options'].get('cookiesfrombrowser') == ('chrome',)
    assert captured['options'].get('skip_download') is True


@pytest.mark.parametrize(
    'duration,has_sub,has_audio,mode,expect_card,expect_warn',
    [
        (90, True, True, 'auto', 'platform_subtitle', False),
        (90, False, True, 'auto', 'local_transcription', False),
        (90, False, False, 'auto', 'visual', False),
        (8000, False, False, 'visual', 'visual', True),
        (8000, False, True, 'visual', 'local_transcription', True),
    ],
)
def test_preview_route_cards(duration, has_sub, has_audio, mode, expect_card, expect_warn):
    out = planning.preview_route(duration, has_sub, has_audio, mode)
    assert out['preview_route'] == expect_card
    assert out['warn_visual_too_long'] is expect_warn
    assert out['recommended_analysis'] in ('subtitle', 'visual')

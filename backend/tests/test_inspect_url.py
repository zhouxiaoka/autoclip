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
    assert captured['options'].get('socket_timeout') == jobs.INSPECT_SOCKET_TIMEOUT
    assert captured['options'].get('retries') == 0
    assert captured['options'].get('extractor_retries') == 0


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



def test_recovery_options_keeps_caller_socket_timeout():
    from backend.utils.download_recovery import recovery_options
    opts = recovery_options({'socket_timeout': 8, 'retries': 0, 'quiet': True})
    assert opts['socket_timeout'] == 8
    assert opts['retries'] == 0
    # Defaults still apply when omitted.
    assert recovery_options({'quiet': True})['socket_timeout'] == 30


def test_inspect_flight_key_normalizes_host_case():
    from backend.api.v1 import studio as studio_api
    a = studio_api.inspect_flight_key('https://WWW.YouTube.com/watch?v=abc', None)
    b = studio_api.inspect_flight_key('https://www.youtube.com/watch?v=abc', None)
    assert a == b
    assert studio_api.inspect_flight_key('https://www.youtube.com/watch?v=abc', 'chrome') != a


def test_await_inspect_same_url_singleflight(monkeypatch):
    """Concurrent same-URL inspects share one jobs.inspect_url call."""
    import asyncio
    import threading
    from backend.api.v1 import studio as studio_api

    calls = []
    release = threading.Event()
    entered = threading.Event()

    def fake_inspect(url, browser=None):
        calls.append((url, browser))
        entered.set()
        assert release.wait(timeout=2), 'release timed out'
        return {
            'title': 'Shared',
            'duration': 10.0,
            'has_manual_subtitle': False,
            'language': None,
            'max_height': None,
            'thumbnail': None,
            'has_audio': True,
        }

    monkeypatch.setattr(studio_api.jobs, 'inspect_url', fake_inspect)
    studio_api.clear_inspect_inflight()
    url = 'https://www.youtube.com/watch?v=same123'

    async def run():
        t1 = asyncio.create_task(studio_api.await_inspect_url(url, None, timeout=5))
        for _ in range(50):
            if entered.is_set():
                break
            await asyncio.sleep(0.05)
        assert entered.is_set(), 'leader never entered'
        t2 = asyncio.create_task(studio_api.await_inspect_url(url, None, timeout=5))
        await asyncio.sleep(0.05)
        assert len(calls) == 1
        release.set()
        r1, r2 = await asyncio.gather(t1, t2)
        assert r1 == r2
        assert r1['title'] == 'Shared'
        assert len(calls) == 1

    asyncio.run(run())
    studio_api.clear_inspect_inflight()


def test_await_inspect_different_urls_parallel(monkeypatch):
    """Different URLs each get their own in-flight job."""
    import asyncio
    import threading
    from backend.api.v1 import studio as studio_api

    barrier = threading.Barrier(2, timeout=2)
    calls = []

    def fake_inspect(url, browser=None):
        calls.append(url)
        barrier.wait()
        return {
            'title': url,
            'duration': 1.0,
            'has_manual_subtitle': False,
            'language': None,
            'max_height': None,
            'thumbnail': None,
            'has_audio': True,
        }

    monkeypatch.setattr(studio_api.jobs, 'inspect_url', fake_inspect)
    studio_api.clear_inspect_inflight()
    u1 = 'https://www.youtube.com/watch?v=aaa'
    u2 = 'https://www.youtube.com/watch?v=bbb'

    async def run():
        r1, r2 = await asyncio.gather(
            studio_api.await_inspect_url(u1, None, timeout=5),
            studio_api.await_inspect_url(u2, None, timeout=5),
        )
        assert r1['title'] == u1
        assert r2['title'] == u2
        assert len(calls) == 2

    asyncio.run(run())
    studio_api.clear_inspect_inflight()

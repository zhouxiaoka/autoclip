"""Exercise yt-dlp, fragmented MP4, FFmpeg and refusal of a missing middle segment offline."""
import functools
import subprocess
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi import HTTPException
from yt_dlp.extractor.twitch import TwitchVodIE

from backend.services import twitch_replay_media as media


def test_complete_fragmented_replay_and_missing_segment(tmp_path, monkeypatch):
    origin = tmp_path / 'origin'
    origin.mkdir()
    subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=176x144:r=12',
                    '-f', 'lavfi', '-i', 'sine=f=600', '-t', '6', '-c:v', 'libx264', '-g', '12', '-c:a', 'aac',
                    '-hls_time', '1', '-hls_segment_type', 'fmp4', '-hls_playlist_type', 'vod', 'archive.m3u8'],
                   cwd=origin, check=True, timeout=30)

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(origin))) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        def extract(_, url):
            assert url == 'https://www.twitch.tv/videos/123'
            return {'id': 'v123', 'title': 'Fixture', 'formats': [{
                'format_id': 'test', 'ext': 'mp4', 'vcodec': 'h264', 'acodec': 'aac', 'protocol': 'm3u8_native',
                'url': f'http://127.0.0.1:{server.server_port}/archive.m3u8',
            }]}
        monkeypatch.setattr(TwitchVodIE, '_real_extract', extract)
        staging = tmp_path / 'staging'
        try:
            result = media.stage('123', '6s', staging)
            assert media.probe_material(result).duration == pytest.approx(6, abs=.2)
            result.unlink()
            sorted(origin.glob('*.m4s'))[2].unlink()
            with pytest.raises(HTTPException) as refused:
                media.stage('123', '6s', staging)
            assert refused.value.detail == 'replay_download_failed'
            assert not list(staging.iterdir())
        finally:
            server.shutdown()

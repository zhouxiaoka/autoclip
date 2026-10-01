"""A source far below the resolution the video offers is re-downloaded with another YouTube client."""
from backend.services.studio import jobs
from backend.utils import download_recovery

INFO = {'formats': [{'height': 360, 'vcodec': 'avc1'}, {'height': 1080, 'vcodec': 'av01'}, {'height': None, 'vcodec': 'none'}]}


def test_a_360p_download_is_replaced_by_a_1080p_retry(monkeypatch, tmp_path):
    (tmp_path / 'input.mp4').write_bytes(b'360p')
    heights = {b'360p': 360, b'1080p': 1080}
    monkeypatch.setattr(jobs, '_video_height', lambda path: heights[path.read_bytes()])
    clients = []

    def fetch(url, options):
        clients.append(options['extractor_args']['youtube']['player_client'][0])
        open(options['outtmpl'].replace('%(ext)s', 'mp4'), 'wb').write(b'1080p')

    monkeypatch.setattr(download_recovery, 'download_with_recovery', fetch)
    assert jobs._ensure_source_resolution('https://www.youtube.com/watch?v=x', {'format': 'best'}, INFO, tmp_path) == 1080
    assert clients == ['web_safari'] and (tmp_path / 'input.mp4').read_bytes() == b'1080p'
    assert sorted(p.name for p in tmp_path.iterdir()) == ['input.mp4']


def test_good_or_non_youtube_sources_are_left_alone(monkeypatch, tmp_path):
    (tmp_path / 'input.mp4').write_bytes(b'x')
    monkeypatch.setattr(download_recovery, 'download_with_recovery', lambda *_: (_ for _ in ()).throw(AssertionError('no retry')))
    monkeypatch.setattr(jobs, '_video_height', lambda _p: 1080)
    assert jobs._ensure_source_resolution('https://www.youtube.com/watch?v=x', {}, INFO, tmp_path) == 1080
    monkeypatch.setattr(jobs, '_video_height', lambda _p: 360)
    assert jobs._ensure_source_resolution('https://www.bilibili.com/video/BV1', {}, INFO, tmp_path) == 360
    assert jobs._ensure_source_resolution('https://youtu.be/x', {}, {'formats': [{'height': 360, 'vcodec': 'avc1'}]}, tmp_path) == 360

"""Exercise concurrent legacy downloads without network, models or user data."""
import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace


def test_concurrent_downloads_ignore_stale_files_and_reach_whisper(tmp_path, monkeypatch):
    import yt_dlp
    from backend.api.v1 import youtube
    from backend.core import config, database, path_utils
    from backend.services import project_service
    from backend.services.auto_pipeline_service import auto_pipeline_service
    from backend.utils import speech_recognizer

    temp = tmp_path / 'temp'
    temp.mkdir()
    (temp / 'stale.mp4').write_bytes(b'wrong video')
    (temp / 'stale.srt').write_text('wrong subtitles')
    monkeypatch.setattr(config, 'get_data_directory', lambda: tmp_path)
    monkeypatch.setattr(path_utils, 'get_project_directory', lambda pid: tmp_path / 'projects' / pid)
    from backend.models.project import Project
    projects = {pid: Project(id=pid, name=pid, processing_config={}) for pid in ['one', 'two']}
    monkeypatch.setattr(project_service, 'ProjectService', lambda db: SimpleNamespace(get=projects.get))
    monkeypatch.setattr(database, 'SessionLocal', lambda: SimpleNamespace(commit=lambda: None, close=lambda: None))
    async def progress(*args): pass
    started = []
    async def start(pid):
        started.append(pid)
        return {'status':'started'}
    monkeypatch.setattr(youtube, 'update_project_download_progress', progress)
    monkeypatch.setattr(auto_pipeline_service, 'auto_start_pipeline', start)
    monkeypatch.setattr(youtube, 'download_tasks', {pid: SimpleNamespace() for pid in projects})
    barrier = threading.Barrier(2)
    folders = []
    class Downloader:
        def __init__(self, options): self.options = options
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def download(self, urls):
            folder = Path(self.options['outtmpl']).parent
            folders.append(folder)
            (folder / 'same-title.mp4').write_bytes(urls[0].encode())
            barrier.wait(timeout=10)
    monkeypatch.setattr(yt_dlp, 'YoutubeDL', Downloader)
    transcribed = []
    def transcribe(video, **kwargs):
        transcribed.append(video.read_bytes())
        result = video.with_suffix('.srt')
        result.write_text(video.read_text())
        return result
    monkeypatch.setattr(speech_recognizer, 'generate_subtitle_for_video', transcribe)
    async def run():
        await asyncio.gather(*(youtube.process_youtube_download_task(
            pid, SimpleNamespace(url=pid, browser=None, project_name=pid), pid
        ) for pid in projects))
    asyncio.run(run())
    assert len(set(folders)) == 2
    assert sorted(transcribed) == [b'one', b'two']
    assert sorted(started) == ['one', 'two']
    for pid in projects:
        assert youtube.download_tasks[pid].status == 'completed'
        raw = tmp_path / 'projects' / pid / 'raw'
        assert (raw / 'input.mp4').read_bytes() == pid.encode()
        assert (raw / 'input.srt').read_text() == pid
    assert (temp / 'stale.mp4').read_bytes() == b'wrong video'

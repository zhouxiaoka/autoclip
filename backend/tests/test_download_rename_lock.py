"""#410: yt-dlp rename hits a Windows sharing violation (WinError 32).

WinError 32 is errno EACCES. yt-dlp retries that errno, then raises DownloadError
"Unable to rename file: … Giving up after N retries". Stock yt-dlp uses N=3 and
sleeps ~10ms, which is the string in the report. recovery_options keeps the
retry inside that one download and waits longer. A second download() is not started.
"""
import errno
import time

import pytest
import yt_dlp
from yt_dlp.downloader.common import FileDownloader

from backend.utils import download_recovery as module

# The report's text. Linux formats the same errno as [Errno 13]; Windows as [WinError 32].
ISSUE_410 = (
    "ERROR: Unable to rename file: [WinError 32] The process cannot access the file "
    "because it is being used by another process: "
    r"'C:\\Users\\USER\\AppData\\Roaming\\AutoClip\\projects\\01e8b5f1-0275-42bb-b7f7-d143def6c426\\raw\\input.f299.mp4.part' "
    r"-> 'C:\\Users\\USER\\AppData\\Roaming\\AutoClip\\projects\\01e8b5f1-0275-42bb-b7f7-d143def6c426\\raw\\input.f299.mp4'. "
    "Giving up after 3 retries"
)


def _sharing_violation(src, dst):
    error = PermissionError(
        errno.EACCES,
        'The process cannot access the file because it is being used by another process',
    )
    error.winerror = 32
    error.filename = src
    error.filename2 = dst
    return error


def _patch_rename(monkeypatch, fails):
    sleeps = []
    calls = []
    monkeypatch.setattr(time, 'sleep', lambda seconds: sleeps.append(seconds))

    def replace(src, dst):
        calls.append((src, dst))
        if len(calls) <= fails:
            raise _sharing_violation(src, dst)

    monkeypatch.setattr('yt_dlp.downloader.common.os.replace', replace)
    return calls, sleeps


def _downloader(options):
    ydl = yt_dlp.YoutubeDL(options)
    return FileDownloader(ydl, ydl.params)


def test_stock_ytdlp_gives_up_on_a_sharing_violation_after_three_short_retries(monkeypatch):
    calls, sleeps = _patch_rename(monkeypatch, fails=99)
    with pytest.raises(yt_dlp.utils.DownloadError, match='Giving up after 3 retries') as caught:
        _downloader({'quiet': True, 'noprogress': True}).try_rename(
            'input.f299.mp4.part', 'input.f299.mp4')
    assert len(calls) == 4
    assert sleeps == [0.01, 0.01, 0.01]
    text = str(caught.value)
    assert 'Unable to rename file' in text
    assert 'input.f299.mp4.part' in text and 'input.f299.mp4' in text


def test_recovery_waits_out_a_transient_sharing_violation(monkeypatch):
    calls, sleeps = _patch_rename(monkeypatch, fails=3)
    _downloader(module.recovery_options({'quiet': True, 'noprogress': True})).try_rename(
        'clip.part', 'clip.mp4')
    assert len(calls) == 4
    assert sleeps == [0.01, 0.25, 0.01, 0.5, 0.01, 0.75]


def test_recovery_still_stops_after_eight_rename_retries(monkeypatch):
    calls, sleeps = _patch_rename(monkeypatch, fails=99)
    with pytest.raises(yt_dlp.utils.DownloadError, match='Giving up after 8 retries') as caught:
        _downloader(module.recovery_options({'quiet': True, 'noprogress': True})).try_rename(
            'clip.part', 'clip.mp4')
    assert len(calls) == 9
    backoff = [seconds for seconds in sleeps if seconds != 0.01]
    assert backoff == [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]
    assert sum(backoff) == 9
    assert 'clip.part' in str(caught.value)
    assert module.file_access_backoff(0) == 0.25
    assert module.FILE_ACCESS_RETRIES == 8


def test_a_finished_rename_failure_does_not_start_another_download(monkeypatch):
    calls = []

    class Downloader:
        def __init__(self, options):
            calls.append(dict(options))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def download(self, urls):
            raise yt_dlp.utils.DownloadError(ISSUE_410)

    monkeypatch.setattr(module.yt_dlp, 'YoutubeDL', Downloader)
    from backend.core.failure_codes import sentence, user_visible_error
    from backend.core.sentry_setup import UNREPORTED_STUDIO_ERROR_CODES, studio_error_code
    from backend.pipeline.failures import PipelineFailure
    with pytest.raises(PipelineFailure) as caught:
        module.download_with_recovery('https://www.youtube.com/watch?v=synthetic', {'quiet': True})
    error = caught.value
    assert error.code == module.FILE_LOCKED_CODE and error.stage == 'INGEST'
    assert error.__cause__ is None
    visible = user_visible_error(error)
    assert visible == sentence('file_locked')
    assert studio_error_code(error) == 'file_locked'
    assert 'file_locked' in UNREPORTED_STUDIO_ERROR_CODES
    leaked = ('WinError', 'Unable to rename', 'Giving up', '01e8b5f1', 'AppData', 'input.f299', 'yt-dlp')
    blob = visible + str(error)
    for piece in leaked:
        assert piece not in blob
    assert len(calls) == 1
    assert calls[0]['file_access_retries'] == module.FILE_ACCESS_RETRIES
    assert calls[0]['continuedl'] is True
    assert calls[0]['retry_sleep_functions']['file_access'] is module.file_access_backoff


def test_a_non_lock_rename_failure_stays_a_download_error(monkeypatch):
    class Downloader:
        def __init__(self, options):
            return None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def download(self, urls):
            raise yt_dlp.utils.DownloadError(
                'ERROR: Unable to rename file: [Errno 28] No space left on device')

    monkeypatch.setattr(module.yt_dlp, 'YoutubeDL', Downloader)
    with pytest.raises(yt_dlp.utils.DownloadError, match='No space left'):
        module.download_with_recovery('https://example.com/v', {'quiet': True})


def test_explicit_file_access_settings_are_not_replaced(monkeypatch):
    def custom(n):
        return 0.05

    seen = {}

    class Downloader:
        def __init__(self, options):
            seen.update(options)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def download(self, urls):
            return 0

    monkeypatch.setattr(module.yt_dlp, 'YoutubeDL', Downloader)
    assert module.download_with_recovery('https://example.com/v', {
        'quiet': True,
        'file_access_retries': 3,
        'retry_sleep_functions': {'file_access': custom},
    }) == 0
    assert seen['file_access_retries'] == 3
    assert seen['retry_sleep_functions']['file_access'] is custom

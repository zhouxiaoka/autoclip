"""Reproduce yt-dlp's typed browser-cookie exception chain without browser access."""
import pytest
import yt_dlp
from yt_dlp import cookies
from backend.utils import download_recovery as module


def install_downloader(monkeypatch, cookie_error, outcomes=()):
    actual = yt_dlp.YoutubeDL
    calls = []
    def read_cookie(*args, **kwargs):
        raise cookie_error
    monkeypatch.setattr(cookies, '_extract_chrome_cookies', read_cookie)
    class Downloader(actual):
        def download(self, urls):
            calls.append(dict(self.params))
            if self.params.get('cookiesfrombrowser'):
                self.cookiejar  # Real load_cookies -> CookieLoadError -> DownloadError / exc_info.
            index = len(calls) - 2
            if 0 <= index < len(outcomes):
                raise outcomes[index]
            return 0
    monkeypatch.setattr(module.yt_dlp, 'YoutubeDL', Downloader)
    return calls


@pytest.mark.parametrize('url', ['https://youtube.com/watch?v=synthetic', 'https://www.bilibili.com/video/synthetic', 'https://b23.tv/synthetic'])
def test_locked_browser_retries_public_video_without_cookie_access(monkeypatch, url):
    calls = install_downloader(monkeypatch, PermissionError('synthetic browser database locked'))
    options = {'cookiesfrombrowser': ('chrome',), 'quiet': True, 'no_warnings': True, 'continuedl': True}
    assert module.download_with_recovery(url, options) == 0
    assert len(calls) == 2
    assert 'cookiesfrombrowser' not in calls[1]
    assert calls[1]['continuedl'] is True and calls[1]['fragment_retries'] == 2
    assert options['cookiesfrombrowser'] == ('chrome',)


def test_anonymous_auth_failure_is_actionable_and_bounded(monkeypatch):
    calls = install_downloader(monkeypatch, PermissionError('synthetic private path must not appear'),
        [yt_dlp.utils.DownloadError('Sign in required: synthetic private response must not appear')])
    with pytest.raises(RuntimeError) as caught:
        module.download_with_recovery('https://youtube.com/watch?v=synthetic', {'cookiesfrombrowser': ('chrome',), 'quiet': True})
    assert len(calls) == 2
    assert '关闭浏览器' in str(caught.value)
    assert 'synthetic' not in str(caught.value)


@pytest.mark.parametrize('url,extra', [('https://private.invalid/video', {}), ('https://youtube.com/watch?v=synthetic', {'cookiefile': 'synthetic-cookie-file'})])
def test_custom_sites_and_explicit_cookie_files_are_not_anonymously_retried(monkeypatch, url, extra):
    calls = install_downloader(monkeypatch, PermissionError('synthetic denied'))
    with pytest.raises(RuntimeError) as caught:
        module.download_with_recovery(url, {'cookiesfrombrowser': ('chrome',), 'quiet': True, **extra})
    assert len(calls) == 1
    assert '关闭浏览器' in str(caught.value)


def test_other_cookie_errors_are_not_hidden_or_retried(monkeypatch):
    calls = install_downloader(monkeypatch, FileNotFoundError('synthetic missing profile'))
    with pytest.raises(yt_dlp.utils.DownloadError):
        module.download_with_recovery('https://youtube.com/watch?v=synthetic', {'cookiesfrombrowser': ('chrome',), 'quiet': True})
    assert len(calls) == 1


def test_unrelated_permission_error_is_not_cookie_recovery(monkeypatch):
    calls = []
    class Downloader:
        def __init__(self, options): calls.append(dict(options))
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def download(self, urls): raise PermissionError('synthetic output permission')
    monkeypatch.setattr(module.yt_dlp, 'YoutubeDL', Downloader)
    with pytest.raises(PermissionError, match='output permission'):
        module.download_with_recovery('https://youtube.com/watch?v=synthetic', {'cookiesfrombrowser': ('chrome',)})
    assert len(calls) == 1


def test_existing_subtitle_and_format_recovery_remains_bounded(monkeypatch):
    calls = install_downloader(monkeypatch, PermissionError('synthetic browser locked'),
        [yt_dlp.utils.DownloadError('Unable to download subtitles: HTTP Error 429'),
         yt_dlp.utils.DownloadError('HTTP Error 403: Forbidden')])
    assert module.download_with_recovery('https://youtube.com/watch?v=synthetic',
        {'cookiesfrombrowser': ('chrome',), 'writesubtitles': True, 'writeautomaticsub': True, 'quiet': True}) == 0
    assert len(calls) == 4
    assert all(not call.get('cookiesfrombrowser') for call in calls[1:])
    assert calls[2]['writesubtitles'] is False
    assert 'm3u8' in calls[3]['format']


def install_outcomes(monkeypatch, outcomes):
    calls = []
    class Downloader:
        def __init__(self, options): calls.append(dict(options))
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def download(self, urls):
            outcome = outcomes[len(calls) - 1]
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome
    monkeypatch.setattr(module.yt_dlp, 'YoutubeDL', Downloader)
    return calls


BILI_412 = ('ERROR: [BiliBili] 1yf8XzmEV8: Unable to download webpage: HTTP Error 412: Precondition Failed '
            '(caused by <HTTPError 412: Precondition Failed>)')


@pytest.mark.parametrize('url,message,status', [
    ('https://www.bilibili.com/video/BV1yf8XzmEV8/', BILI_412, 412),  # RC156 Win QA #9, datacenter IP
    ('https://private.invalid/video', 'ERROR: [generic] Unable to download webpage: HTTP Error 403: Forbidden', 403),
    ('https://b23.tv/synthetic', 'ERROR: Unable to download JSON metadata: HTTP Error 429: Too Many Requests', 429),
])
def test_site_refusal_is_source_blocked_with_translated_hint(monkeypatch, url, message, status):
    from backend.pipeline.failures import PipelineFailure
    from backend.core.sentry_setup import studio_error_code, studio_failure_context
    calls = install_outcomes(monkeypatch, [yt_dlp.utils.DownloadError(message)])
    with pytest.raises(PipelineFailure) as caught:
        module.download_with_recovery(url, {'quiet': True})
    error = caught.value
    assert len(calls) == 1  # no extra request against a site that is refusing this network
    assert error.code == 'source_blocked' and error.stage == 'INGEST' and error.http_status == status
    assert str(error) == module.SOURCE_BLOCKED_HINT
    assert error.__cause__ is None and error.__suppress_context__  # no yt-dlp text, URL or response
    for leaked in ('BiliBili', 'HTTP Error', 'Precondition', 'Forbidden', 'invalid', 'b23'):
        assert leaked not in str(error)
    assert studio_error_code(error) == 'source_blocked'
    assert studio_failure_context(error, 'screening') == {'failure_stage': 'ingest', 'http_status': status}


def test_youtube_403_still_retries_format_once_before_source_blocked(monkeypatch):
    from backend.pipeline.failures import PipelineFailure
    calls = install_outcomes(monkeypatch, [yt_dlp.utils.DownloadError('HTTP Error 403: Forbidden'),
                                           yt_dlp.utils.DownloadError('HTTP Error 403: Forbidden')])
    with pytest.raises(PipelineFailure) as caught:
        module.download_with_recovery('https://youtube.com/watch?v=synthetic', {'quiet': True})
    assert len(calls) == 2 and 'm3u8' in calls[1]['format']
    assert caught.value.code == 'source_blocked'

    calls = install_outcomes(monkeypatch, [yt_dlp.utils.DownloadError('HTTP Error 403: Forbidden'), 0])
    assert module.download_with_recovery('https://youtube.com/watch?v=synthetic', {'quiet': True}) == 0
    assert len(calls) == 2


@pytest.mark.parametrize('message', ['HTTP Error 404: Not Found', 'Video unavailable', 'HTTP Error 4120: synthetic'])
def test_other_download_errors_are_not_source_blocked(monkeypatch, message):
    calls = install_outcomes(monkeypatch, [yt_dlp.utils.DownloadError(message)])
    with pytest.raises(yt_dlp.utils.DownloadError):
        module.download_with_recovery('https://www.bilibili.com/video/synthetic', {'quiet': True})
    assert len(calls) == 1

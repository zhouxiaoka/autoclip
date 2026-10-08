"""Bounded media retries shared by legacy imports and Studio."""
import re
from urllib.parse import urlparse
import yt_dlp
from yt_dlp.cookies import CookieLoadError

from backend.pipeline.failures import PipelineFailure


COOKIE_ACCESS_HINT = '无法读取浏览器登录信息。请关闭浏览器后重试，或不选浏览器下载公开视频。原素材已保留。'
# 也是前端 i18n 的 key（8 个 locale），改动时同步 frontend/src/i18n/locales/*.json。
SOURCE_BLOCKED_HINT = '视频网站拒绝了这次下载（HTTP 403/412/429），常见于当前网络被网站风控或请求过于频繁。请稍后换个网络（如手机热点）重试，或在导入时选择已登录的浏览器读取 Cookie。'
SOURCE_BLOCKED_CODE = 'source_blocked'
# yt-dlp: "Unable to download webpage: HTTP Error 412: Precondition Failed"
_BLOCKED_HTTP_ERROR = re.compile(r'\bhttp error (403|412|429)\b')


def _browser_cookie_permission_failure(error):
    """Recognize yt-dlp's typed cookie wrapper, not arbitrary permission errors."""
    pending, seen = [error], set()
    cookie_failure = permission_failure = False
    while pending:
        current = pending.pop()
        if not isinstance(current, BaseException) or id(current) in seen:
            continue
        seen.add(id(current))
        cookie_failure |= isinstance(current, CookieLoadError)
        permission_failure |= isinstance(current, PermissionError)
        pending.extend((current.__cause__, current.__context__))
        info = getattr(current, 'exc_info', None)
        if isinstance(info, tuple) and len(info) > 1:
            pending.append(info[1])
    return cookie_failure and permission_failure


def download_with_recovery(url: str, options: dict):
    opts = {**options, 'socket_timeout': 30, 'retries': 2,
            'fragment_retries': 2, 'extractor_retries': 2,
            'concurrent_fragment_downloads': 1, 'skip_unavailable_fragments': False,
            'continuedl': True}
    youtube = urlparse(url).hostname in {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be'}
    public_site = youtube or urlparse(url).hostname in {'bilibili.com', 'www.bilibili.com', 'm.bilibili.com', 'b23.tv'}
    retried_subtitles = retried_format = retried_cookies = False
    while True:
        try:
            with yt_dlp.YoutubeDL(opts) as downloader:
                result = downloader.download([url])
            if result:
                raise RuntimeError('视频下载未完成，请检查网络后重试；已下载的分片将用于续传。')
            return result
        except (yt_dlp.utils.DownloadError, CookieLoadError) as error:
            if opts.get('cookiesfrombrowser') and _browser_cookie_permission_failure(error):
                # Browser cookies are optional for public media. Do not touch the
                # browser database, export credentials, or retry its locked file.
                if public_site and not opts.get('cookiefile') and not retried_cookies:
                    retried_cookies = True
                    opts.pop('cookiesfrombrowser')
                    continue
                raise RuntimeError(COOKIE_ACCESS_HINT) from None
            text = str(error).lower()
            if not retried_subtitles and ('subtitle' in text or 'subtitles' in text) and (opts.get('writesubtitles') or opts.get('writeautomaticsub')):
                retried_subtitles = True
                opts.update(writesubtitles=False, writeautomaticsub=False)
                continue
            if youtube and not retried_format and any(code in text for code in ('http error 403', 'http error 500', 'requested format is not available')):
                retried_format = True
                opts['format'] = 'bestvideo[height<=1080][protocol*=m3u8]+bestaudio[protocol*=m3u8]/best[height<=1080][protocol*=m3u8]/best[ext=mp4]/best'
                continue
            if retried_cookies:
                raise RuntimeError(COOKIE_ACCESS_HINT) from None
            blocked = _BLOCKED_HTTP_ERROR.search(text)
            if blocked:
                # The site refused this network/client (e.g. Bilibili 412 risk control on
                # datacenter IPs). Expected and actionable: a stable code and a translated
                # hint, never yt-dlp's English text, URL or response.
                raise PipelineFailure('INGEST', SOURCE_BLOCKED_HINT, code=SOURCE_BLOCKED_CODE,
                                      http_status=int(blocked[1])) from None
            raise

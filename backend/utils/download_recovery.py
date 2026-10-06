"""Bounded media retries shared by legacy imports and Studio."""
from urllib.parse import urlparse
import yt_dlp
from yt_dlp.cookies import CookieLoadError


COOKIE_ACCESS_HINT = '无法读取浏览器登录信息。请关闭浏览器后重试，或不选浏览器下载公开视频。原素材已保留。'


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
            raise

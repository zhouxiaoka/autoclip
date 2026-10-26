"""Bounded media retries shared by legacy imports and Studio."""
import re
from urllib.parse import urlparse
import yt_dlp
from yt_dlp.cookies import CookieLoadError

from backend.pipeline.failures import PipelineFailure

# yt-dlp 默认 file_access_retries=3，且不设 file_access 的 retry sleep，
# 两次尝试之间只在 warn 里睡约 10ms。Windows 杀毒/索引锁住
# .part → 成片 的 rename 时是 WinError 32（errno EACCES），30ms 内经常放不掉，
# 于是报 “Giving up after 3 retries”（#410）。把这一次下载里的 rename 拉长到
# 最多 8 次、合计约 9 秒；调用方显式传入的次数或 sleep 不覆盖。
FILE_ACCESS_RETRIES = 8


COOKIE_ACCESS_HINT = '无法读取浏览器登录信息。请关闭浏览器后重试，或不选浏览器下载公开视频。原素材已保留。'
# 也是前端 i18n 的 key（8 个 locale），改动时同步 frontend/src/i18n/locales/*.json。
SOURCE_BLOCKED_HINT = '视频网站拒绝了这次下载（HTTP 403/412/429），常见于当前网络被网站风控或请求过于频繁。请稍后换个网络（如手机热点）重试，或在导入时选择已登录的浏览器读取 Cookie。'
SOURCE_BLOCKED_CODE = 'source_blocked'
# 找不到片源。也是前端 i18n 的 key，改动时同步 locales。不要带 URL、状态码或 yt-dlp 原文。
SOURCE_NOT_FOUND_HINT = '找不到这个视频，它可能已被删除或链接不正确。请核对链接，或换一个视频后重试。'
SOURCE_NOT_FOUND_CODE = 'source_not_found'
# 私密、地区/年龄限制、版权或人机验证。仍用 source_blocked，但不用 403/412/429 那句（这里没有那些状态码）。
SOURCE_ACCESS_HINT = '这个视频当前无法访问，可能是私密、地区或年龄限制，或网站要求登录确认。请换一个公开视频，或在导入时选择已登录的浏览器读取 Cookie。'
# 这一次下载里的 rename 已经用完 file_access 预算。用户句只来自 failure_messages.json。
FILE_LOCKED_CODE = 'file_locked'
# yt-dlp: "Unable to download webpage: HTTP Error 412: Precondition Failed"
# 4120 不是 412：状态码后面必须是词边界。
_BLOCKED_HTTP_ERROR = re.compile(r'\bhttp error (403|412|429)\b')
_ACCESS_BLOCKED = re.compile(
    r"sign in to confirm you.?re not a bot"
    r"|not a bot"
    r"|private video"
    r"|video is private"
    r"|not available in your country"
    r"|geo[- ]restrict"
    r"|copyright"
    r"|age[- ]restricted"
    r"|confirm your age"
    r"|members[- ]only"
    r"|join this channel"
)
_NOT_FOUND = re.compile(
    r"\bhttp error (404|410)\b"
    r"|video unavailable"
    r"|has been removed"
    r"|does not exist"
    r"|no longer available"
    r"|account associated with this video has been terminated"
)


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


def file_access_backoff(n=0) -> float:
    """Seconds to wait before file-access retry ``n`` (0-based). Eight retries sum to 9s."""
    return min(2.0, 0.25 * (int(n) + 1))


def recovery_options(options: dict) -> dict:
    """yt-dlp options for one download, including the Windows rename-lock budget."""
    opts = {**options, 'socket_timeout': 30, 'retries': 2,
            'fragment_retries': 2, 'extractor_retries': 2,
            'concurrent_fragment_downloads': 1, 'skip_unavailable_fragments': False,
            'continuedl': True}
    opts.setdefault('file_access_retries', FILE_ACCESS_RETRIES)
    sleeps = dict(opts.get('retry_sleep_functions') or {})
    sleeps.setdefault('file_access', file_access_backoff)
    opts['retry_sleep_functions'] = sleeps
    return opts


def download_with_recovery(url: str, options: dict):
    opts = recovery_options(options)
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
            kind = _link_failure(text)
            if kind:
                code, hint = kind
                raise PipelineFailure('INGEST', hint, code=code) from None
            if _rename_locked(text):
                # yt-dlp already spent file_access_retries. Do not start another
                # download, and do not keep the path or the English WinError text.
                from backend.core.failure_codes import sentence
                raise PipelineFailure('INGEST', sentence(FILE_LOCKED_CODE), code=FILE_LOCKED_CODE) from None
            raise


def _rename_locked(text: str) -> bool:
    """A rename that lost to a sharing lock, after yt-dlp's own retries.

    Other rename failures (missing file, full disk) stay unclassified here.
    """
    if 'unable to rename file' not in text:
        return False
    return any(phrase in text for phrase in (
        'winerror 32',
        'being used by another process',
        'sharing violation',
    ))


def _link_failure(text: str):
    """A missing or gated link that is not HTTP 403/412/429.

    Access rules win over the generic "video unavailable" phrase. Nothing here
    copies the extractor text, the URL, or a site status into the user sentence.
    """
    if _ACCESS_BLOCKED.search(text):
        return SOURCE_BLOCKED_CODE, SOURCE_ACCESS_HINT
    if _NOT_FOUND.search(text):
        return SOURCE_NOT_FOUND_CODE, SOURCE_NOT_FOUND_HINT
    return None

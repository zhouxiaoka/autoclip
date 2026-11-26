"""Closed classification of downloader error text. No yt_dlp import.

The contract checks run without the downloader installed. Production download
still lives in download_recovery and imports these same tables.
"""
from __future__ import annotations

import re

SOURCE_BLOCKED_CODE = 'source_blocked'
SOURCE_NOT_FOUND_CODE = 'source_not_found'
SOURCE_UNSUPPORTED_CODE = 'source_unsupported'
FILE_LOCKED_CODE = 'file_locked'
# Shown for a download-stage ``connection`` (timeout, DNS, reset). Not the model-service
# sentence: that one stays on failure_messages['connection'] for model calls. This string
# is also the i18n key in all eight frontend locales.
INGEST_CONNECTION_MESSAGE = '下载视频时网络超时或中断。请检查网络后重试，或换一个视频链接。'
# 4120 不是 412：状态码后面必须是词边界。
_BLOCKED_HTTP_ERROR = re.compile(r'\bhttp error (403|412|429)\b')
_ACCESS_BLOCKED = re.compile(
    r"sign in to confirm you.?re not a bot"
    r"|sign in to view"
    r"|not a bot"
    r"|use --cookies"
    r"|cookies-from-browser"
    r"|private video"
    r"|video is private"
    r"|not available in your country"
    r"|geo[- ]restrict"
    r"|copyright"
    r"|age[- ]restricted"
    r"|confirm your age"
    r"|members[- ]only"
    r"|join this channel"
    r"|this live event will begin"
    r"|premieres in"
)
_NOT_FOUND = re.compile(
    r"\bhttp error (404|410)\b"
    r"|video(?: is)? unavailable"
    r"|has been removed"
    r"|does not exist"
    r"|no longer available"
    r"|truncated id"
    r"|incomplete youtube id"
    r"|account associated with this video has been terminated"
)
_LOGIN_REQUIRED = (
    'sign in to confirm', 'sign in to view', 'not a bot', 'login required', 'login_required',
    'use --cookies', 'cookies-from-browser', 'private video', 'members-only', 'members only',
)
_UNSUPPORTED = ('unsupported url', 'no video formats', 'no video formats found')
_CONNECTION = (
    'unable to download webpage', 'unable to download video data', 'did not get any data blocks',
    'giving up after', 'fragment not found', 'http error 500', 'http error 502', 'http error 503', 'http error 504',
    'connection reset', 'connection refused', 'connection aborted', 'remote end closed',
    'incomplete read', 'broken pipe', 'eof occurred in violation of protocol', 'urlopen error',
    'transport error', 'network is unreachable', 'failed to resolve', 'temporary failure in name resolution',
    'ssl:', '[ssl', 'ssl error', 'certificate_verify_failed', 'ssl.ssleoferror',
    'getaddrinfo', 'proxy', 'name or service not known', 'nodename nor servname',
)
_TIMEOUT = ('timed out', 'timeout', 'read timed out')
_FRAME = (
    'ffmpeg', 'postprocess',
    'merging formats', 'error merging', 'merge the formats', 'ffmpeg merge', 'unable to merge',
)
_NOT_FOUND_PHRASES = (
    'video is unavailable', 'video unavailable', 'has been removed', 'does not exist',
    'http error 404', '404: not found', '404 not found', 'status code 404',
)
_DNS = ('getaddrinfo', 'name or service not known', 'nodename nor servname')


def _rename_locked(text: str) -> bool:
    """A rename or fragment append that lost to a Windows sharing lock, after yt-dlp's own retries."""
    if not any(op in text for op in ('unable to rename file', 'unable to open for writing', 'append_fragment')):
        return False
    return any(phrase in text for phrase in (
        'winerror 32',
        'being used by another process',
        'sharing violation',
    ))


def observe_download_failure(text: str) -> dict:
    """Closed token for a downloader error. Never returns the input, a URL, or a host.

    Same order as the download path: HTTP block, access/not-found regexes, then the
    phrase table. ``timeout`` and ``dns`` share the ``connection`` code so a later
    capture can tell a slow network from a missed unavailable/sign-in phrase.
    """
    lowered = (text or '').lower()
    if _BLOCKED_HTTP_ERROR.search(lowered):
        return {'token': 'http_block', 'code': SOURCE_BLOCKED_CODE}
    if _ACCESS_BLOCKED.search(lowered):
        return {'token': 'sign_in', 'code': SOURCE_BLOCKED_CODE}
    if _NOT_FOUND.search(lowered):
        return {'token': 'unavailable', 'code': SOURCE_NOT_FOUND_CODE}
    if _rename_locked(lowered):
        return {'token': 'file_locked', 'code': FILE_LOCKED_CODE}
    if any(phrase in lowered for phrase in _LOGIN_REQUIRED):
        return {'token': 'sign_in', 'code': SOURCE_BLOCKED_CODE}
    if any(phrase in lowered for phrase in _NOT_FOUND_PHRASES):
        return {'token': 'unavailable', 'code': SOURCE_NOT_FOUND_CODE}
    if any(phrase in lowered for phrase in _FRAME):
        return {'token': 'frame', 'code': 'frame_extract_failed'}
    if any(phrase in lowered for phrase in _DNS):
        return {'token': 'dns', 'code': 'connection'}
    if any(phrase in lowered for phrase in _TIMEOUT):
        return {'token': 'timeout', 'code': 'connection'}
    if any(phrase in lowered for phrase in _CONNECTION):
        return {'token': 'connection', 'code': 'connection'}
    if any(phrase in lowered for phrase in _UNSUPPORTED):
        return {'token': 'unsupported', 'code': SOURCE_UNSUPPORTED_CODE}
    return {'token': 'unmatched', 'code': None}

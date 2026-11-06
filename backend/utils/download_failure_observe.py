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
    r"|video(?: is)? unavailable"
    r"|has been removed"
    r"|does not exist"
    r"|no longer available"
    r"|account associated with this video has been terminated"
)
_LOGIN_REQUIRED = (
    'sign in to confirm', 'not a bot', 'login required', 'private video', 'members-only', 'members only',
)
_UNSUPPORTED = ('unsupported url', 'no video formats', 'no video formats found')
_CONNECTION = (
    'unable to download webpage', 'connection reset',
    'ssl:', '[ssl', 'ssl error', 'certificate_verify_failed', 'ssl.ssleoferror',
    'getaddrinfo', 'proxy', 'name or service not known', 'nodename nor servname',
)
_TIMEOUT = ('timed out', 'timeout')
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
    """A rename that lost to a sharing lock, after the downloader's own retries."""
    if 'unable to rename file' not in text:
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

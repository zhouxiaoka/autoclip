"""Pluggable viral video source adapters: YouTube (Apify / yt-dlp), Bilibili, and local folders."""
from __future__ import annotations

import json
import logging
import math
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = 15.0
USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
)


@dataclass
class CandidateVideo:
    id: str
    platform: str  # 'youtube' | 'bilibili' | 'local'
    track: str
    title: str
    url: str
    author: str = ''
    views: int = 0
    likes: int = 0
    duration_sec: float = 0.0
    thumbnail_url: str = ''
    local_path: str = ''
    query: str = ''
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def engagement_score(self) -> float:
        """Log-scaled popularity + like-ratio score for cross-platform ranking."""
        v = max(1, int(self.views))
        like_ratio = min(0.25, max(0.0, self.likes / v)) if self.likes > 0 else 0.03
        return round(math.log10(v) * (1.0 + like_ratio * 4.0), 3)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d['engagement_score'] = self.engagement_score
        return d


def _http_json(url: str, *, headers: dict[str, str] | None = None, payload: dict[str, Any] | None = None, timeout: float = HTTP_TIMEOUT) -> Any:
    req_headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}
    if headers:
        req_headers.update(headers)
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    if data is not None:
        req_headers.setdefault('Content-Type', 'application/json')
    req = urllib.request.Request(url, data=data, headers=req_headers, method='POST' if data is not None else 'GET')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8', errors='replace'))


def fetch_youtube_apify(
    queries: list[str],
    *,
    track: str,
    limit_per_query: int = 5,
    actor: str = 'streamers~youtube-scraper',
    token: str | None = None,
) -> list[CandidateVideo]:
    """Fetch trending YouTube Shorts via Apify synchronous dataset run.

    Requires ``APIFY_TOKEN`` env var (or explicit ``token``). Never hardcode credentials.
    """
    api_token = (token or os.getenv('APIFY_TOKEN') or '').strip()
    if not api_token:
        logger.info('APIFY_TOKEN not set; skipping YouTube Apify source')
        return []
    endpoint = (
        f'https://api.apify.com/v2/acts/{urllib.parse.quote(actor, safe="~")}'
        f'/run-sync-get-dataset-items?token={urllib.parse.quote(api_token)}'
    )
    payload = {
        'searchQueries': queries,
        'maxResults': 0,
        'maxResultsShorts': max(1, int(limit_per_query)),
    }
    try:
        items = _http_json(endpoint, payload=payload, timeout=90.0)
    except Exception as exc:
        logger.warning('Apify YouTube fetch failed: %s', exc)
        return []

    out: list[CandidateVideo] = []
    for raw in items if isinstance(items, list) else []:
        if not isinstance(raw, dict):
            continue
        vid = str(raw.get('id') or raw.get('videoId') or '').strip()
        url = str(raw.get('url') or (f'https://www.youtube.com/shorts/{vid}' if vid else '')).strip()
        title = str(raw.get('title') or '').strip()
        if not url or '/results?' in url or not title:
            continue
        out.append(CandidateVideo(
            id=vid or url.rsplit('/', 1)[-1],
            platform='youtube',
            track=track,
            title=title,
            url=url,
            author=str(raw.get('channelName') or raw.get('author') or '').strip(),
            views=int(raw.get('viewCount') or raw.get('views') or 0),
            likes=int(raw.get('likes') or 0),
            duration_sec=_parse_duration(raw.get('duration')),
            thumbnail_url=str(raw.get('thumbnailUrl') or raw.get('thumbnail') or '').strip(),
            query=str(raw.get('searchQuery') or '').strip(),
        ))
    return out


def fetch_youtube_ytdlp(
    queries: list[str],
    *,
    track: str,
    limit_per_query: int = 5,
    max_duration_sec: float = 120.0,
) -> list[CandidateVideo]:
    """Free zero-token YouTube search fallback using yt-dlp --flat-playlist."""
    out: list[CandidateVideo] = []
    seen: set[str] = set()
    for q in queries:
        cmd = [
            'yt-dlp', '--dump-json', '--flat-playlist', '--no-warnings', '--skip-download',
            f'ytsearch{max(1, int(limit_per_query))}:{q}',
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning('yt-dlp search failed for %r: %s', q, exc)
            continue
        if proc.returncode != 0:
            continue
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            vid = str(raw.get('id') or '').strip()
            if not vid or vid in seen:
                continue
            dur = float(raw.get('duration') or 0.0)
            if max_duration_sec > 0 and dur > max_duration_sec:
                continue
            seen.add(vid)
            thumbs = raw.get('thumbnails') or []
            thumb = str(thumbs[-1].get('url') or '') if isinstance(thumbs, list) and thumbs else str(raw.get('thumbnail') or '')
            url = str(raw.get('url') or f'https://www.youtube.com/watch?v={vid}')
            out.append(CandidateVideo(
                id=vid,
                platform='youtube',
                track=track,
                title=str(raw.get('title') or '').strip(),
                url=url,
                author=str(raw.get('channel') or raw.get('uploader') or '').strip(),
                views=int(raw.get('view_count') or 0),
                likes=int(raw.get('like_count') or 0),
                duration_sec=dur,
                thumbnail_url=thumb,
                query=q,
            ))
    return out


def fetch_bilibili_search(
    queries: list[str],
    *,
    track: str,
    limit_per_query: int = 5,
    max_duration_sec: float = 180.0,
) -> list[CandidateVideo]:
    """Fetch high-view Bilibili videos via public search API (sorted by clicks)."""
    out: list[CandidateVideo] = []
    seen: set[str] = set()
    headers = {
        'User-Agent': USER_AGENT,
        'Referer': 'https://search.bilibili.com/',
        'Cookie': os.getenv('BILIBILI_COOKIE', 'buvid3=autoclip-discovery'),
    }
    for q in queries:
        qs = urllib.parse.urlencode({
            'search_type': 'video',
            'keyword': q,
            'order': 'click',
            'page': 1,
            'page_size': max(5, int(limit_per_query) * 2),
        })
        url = f'https://api.bilibili.com/x/web-interface/search/type?{qs}'
        try:
            body = _http_json(url, headers=headers, timeout=15.0)
        except Exception as exc:
            logger.warning('Bilibili search failed for %r: %s', q, exc)
            continue
        results = ((body.get('data') or {}).get('result')) if isinstance(body, dict) else None
        if not isinstance(results, list):
            continue
        added = 0
        for raw in results:
            if not isinstance(raw, dict):
                continue
            bvid = str(raw.get('bvid') or '').strip()
            if not bvid or bvid in seen:
                continue
            dur = _parse_duration(raw.get('duration'))
            if max_duration_sec > 0 and dur > max_duration_sec:
                continue
            seen.add(bvid)
            title = _strip_html(str(raw.get('title') or ''))
            pic = str(raw.get('pic') or '').strip()
            if pic.startswith('//'):
                pic = 'https:' + pic
            out.append(CandidateVideo(
                id=bvid,
                platform='bilibili',
                track=track,
                title=title,
                url=f'https://www.bilibili.com/video/{bvid}',
                author=str(raw.get('author') or '').strip(),
                views=int(raw.get('play') or 0),
                likes=int(raw.get('like') or raw.get('favorites') or 0),
                duration_sec=dur,
                thumbnail_url=pic,
                query=q,
            ))
            added += 1
            if added >= limit_per_query:
                break
    return out


def scan_local_folder(folder: Path, *, track: str = 'local') -> list[CandidateVideo]:
    """Load local .mp4/.mov/.mkv/.webm reference clips (reusable for user-facing Style Clone)."""
    exts = {'.mp4', '.mov', '.mkv', '.webm'}
    out: list[CandidateVideo] = []
    if not folder.is_dir():
        return out
    for p in sorted(folder.iterdir()):
        if not p.is_file() or p.suffix.lower() not in exts:
            continue
        dur = _probe_duration(p)
        out.append(CandidateVideo(
            id=p.stem,
            platform='local',
            track=track,
            title=p.stem,
            url=p.resolve().as_uri(),
            author='local',
            views=100_000,
            likes=5_000,
            duration_sec=dur,
            local_path=str(p.resolve()),
        ))
    return out


def _strip_html(s: str) -> str:
    import re
    return re.sub(r'<[^>]+>', '', s).strip()


def _parse_duration(val: Any) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    text = str(val or '').strip()
    if not text:
        return 0.0
    if text.isdigit():
        return float(text)
    parts = text.split(':')
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return 0.0
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    return 0.0


def _probe_duration(path: Path) -> float:
    try:
        out = subprocess.check_output(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(path)],
            text=True, timeout=10,
        )
        return float(out.strip())
    except Exception:
        return 0.0

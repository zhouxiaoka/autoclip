"""Per-platform post copy for one clip: title, description and tags, in one model call.

The output card ships with everything needed to publish, so nobody types a description on the
publish page. Each platform has its own rules (length, tag count, tone); the model writes for all
selected platforms of a clip at once and the rules are enforced here, never trusted. Anything
missing or malformed falls back to the clip title, so a post is never blocked on copy.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PostRules:
    language: str
    title_max: int
    description_max: int
    tags: tuple[int, int]
    style: str


# Product defaults. Hard title limits follow the platforms' upload forms as we know them
# (Xiaohongshu 20, Bilibili 80, YouTube 100); re-check when a platform changes its form.
# Shorter descriptions and tag counts are an editorial choice, not platform limits.
RULES = {
    'douyin': PostRules('zh', 30, 300, (3, 5), '抖音：标题像一句钩子，口语、有冲突或悬念；描述一两句补充看点，结尾可抛问题引导评论'),
    'xiaohongshu': PostRules('zh', 20, 600, (5, 8), '小红书：标题像笔记标题，有获得感；描述分 2–4 小段写要点与个人感受，可少量 emoji'),
    'bilibili': PostRules('zh', 80, 250, (5, 10), 'B站：标题信息完整、可带人物与核心观点；描述交代出处与看点，克制不浮夸'),
    'tiktok': PostRules('en', 100, 300, (3, 5), 'TikTok: punchy hook as the title, one-line caption, casual tone'),
    'instagram_reels': PostRules('en', 100, 400, (5, 10), 'Instagram Reels: hook line plus a short caption with one takeaway'),
    'youtube_shorts': PostRules('en', 100, 300, (3, 5), 'YouTube Shorts: clear searchable title, short description naming the guest and topic'),
    'youtube_long': PostRules('en', 100, 800, (5, 10), 'YouTube: descriptive searchable title; description summarises the segment and credits the source'),
    'original': PostRules('zh', 60, 300, (3, 5), '通用：标题概括核心观点，描述交代出处'),
}
TAG_CHARS = 20

PROMPT = (
    '你是短视频运营编辑。根据这段视频的字幕 lines 与参考标题 title_hint，为 platforms 里的每个平台写发布文案。'
    'rules 给出每个平台的语言、标题字数上限、描述字数上限、话题数量与风格。'
    '要求：忠于原文，不编造事实和数据，不夸大；标题与描述用该平台要求的语言；tags 是不带 # 的话题词，具体到人物、领域或观点，'
    '不要「干货」「必看」这类泛词；source 是素材出处（节目或频道名），描述里自然提一次出处。'
    '只返回 JSON：{"posts":{"平台id":{"title":"...","description":"...","tags":["..."]}}}'
)


def _clean(text: Any) -> str:
    import html
    return re.sub(r'\s+', ' ', re.sub(r'[*_`]+', '', html.unescape(str(text or '')))).strip()


def _fit(text: str, limit: int) -> str:
    """Cut to `limit` characters at a sentence or phrase end when possible."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    stops = [cut.rfind(mark) for mark in '。！？!?.；;，, ']
    best = max(stops)
    return (cut[:best + 1] if best >= limit * 0.6 else cut).rstrip('，,;； ')


def _tags(raw: Any, rules: PostRules) -> list[str]:
    tags, seen = [], set()
    for item in raw if isinstance(raw, list) else []:
        tag = re.sub(r'[#\s]+', '', _clean(item))[:TAG_CHARS]
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            tags.append(tag)
    return tags[:rules.tags[1]]


FOREIGN_FOR_EN = re.compile(r'[\u3040-\u30ff\u3400-\u9fff]')


def fallback(title: str, platform: str) -> dict[str, Any]:
    rules = RULES.get(platform, RULES['original'])
    text = _clean(title)
    if rules.language == 'en' and FOREIGN_FOR_EN.search(text):
        text = ''  # never a Chinese title on an English platform; the user fills it in
    return {'title': _fit(text, rules.title_max), 'description': '', 'tags': []}


def build_posts(title: str, lines: list[str], platforms: list[str], *, source: str = '',
                call: Callable[[str, dict], dict] | None = None) -> dict[str, dict[str, Any]]:
    """{platform: {'title','description','tags'}}; never raises for model problems."""
    platforms = [p for p in dict.fromkeys(platforms) if p in RULES]
    posts = {platform: fallback(title, platform) for platform in platforms}
    text = ' '.join(lines)[:6000]
    if not platforms or not text.strip():
        return posts
    if call is None:
        from backend.services.studio.intelligence import text_json as call
    payload = {'title_hint': title, 'source': source[:120], 'lines': text, 'platforms': platforms,
               'rules': {p: {'language': r.language, 'title_max': r.title_max, 'description_max': r.description_max,
                             'tags': f'{r.tags[0]}-{r.tags[1]}', 'style': r.style} for p in platforms for r in [RULES[p]]}}
    for attempt in range(2):
        try:
            result = call(PROMPT, payload)
            raw = (result or {}).get('posts') if isinstance(result, dict) else None
            if not isinstance(raw, dict):
                raise ValueError('posts missing')
            mixed = []
            for platform in platforms:
                item = raw.get(platform) if isinstance(raw.get(platform), dict) else {}
                rules = RULES[platform]
                post_title = _fit(_clean(item.get('title')), rules.title_max)
                description = _fit(_clean(item.get('description')), rules.description_max)
                tags = _tags(item.get('tags'), rules)
                if rules.language == 'en':
                    # English platforms are English only: a Chinese title is retried, never posted.
                    if FOREIGN_FOR_EN.search(post_title):
                        mixed.append(platform)
                        continue
                    description = '' if FOREIGN_FOR_EN.search(description) else description
                    tags = [tag for tag in tags if not FOREIGN_FOR_EN.search(tag)]
                if post_title:
                    posts[platform] = {'title': post_title, 'description': description, 'tags': tags}
            if mixed and attempt == 0:
                raise ValueError(f'{"、".join(mixed)} 的标题必须是英文，不能有中文')
            return posts
        except Exception as error:  # noqa: BLE001 - copy falls back to the clip title
            logger.warning('Post copy rejected (attempt %d): %s', attempt + 1, type(error).__name__)
            payload = {**payload, 'previous_error': f'上一次返回不合格：{error}。请严格按格式重新返回。'}
    return posts

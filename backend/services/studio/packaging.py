"""Generate automatic template packaging for one draft: title, captions, nameplates, tags.

One text-model call per piece of content and audience language. Only the subtitle rows the draft
uses are sent (the same boundary as render-time translation). Every field returned by the model is
validated; anything malformed falls back to the source subtitles and the draft title so output is
never blocked on packaging.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from backend.services.studio.models import Packaging

logger = logging.getLogger(__name__)

CJK = re.compile(r'[㐀-鿿]')
LATIN = re.compile(r'[A-Za-z]')
TITLE_LIMIT = {'zh': 12, 'en': 36}
TAG_LIMIT = 10
MAX_TAGS = 5

PROMPT = (
    '你是短视频包装编辑。根据 lines（已按时间排序的原字幕，每行有 id）为这段访谈做包装，返回 JSON：\n'
    '{"title_lines":["...","..."],"accent_line":1,"translations":["..."],'
    '"speakers":[{"line":0,"name":"...","role":"..."}],"tags":[{"line":0,"text":"..."}],'
    '"highlights":[{"line":0,"word":"..."}]}\n'
    '规则：title_lines 用 audience_language 写 1–2 行，每行不超过 title_limit 个字符，概括最抓人的观点，不编造；'
    'accent_line 是需要强调的那一行下标。translate 为 true 时 translations 必须与 lines 一一对应翻译成 audience_language，'
    '口语化、去掉口头禅，不添加事实；为 false 时返回空数组。'
    'speakers 只填写在 lines 或 known_names 中明确出现过的人名，role 写其公开身份（不确定就留空），line 是此人第一次说话的行；'
    '不确定就返回空数组，绝不猜测身份。'
    'tags 仅当 template 为 interview_zh 时给出 2–5 个编辑点评（中文，每个不超过 10 个字，如“教科书级”），line 指向被点评的行；'
    'highlights 仅当 template 为 podcast_en 时给出，每 3–4 行最多一个，word 必须是该行（翻译后）里出现的单个关键词。'
)


def source_language(texts: list[str]) -> str:
    joined = ''.join(texts)
    cjk, latin = len(CJK.findall(joined)), len(LATIN.findall(joined))
    if cjk >= max(10, latin * 0.5):
        return 'zh'
    if latin >= 20 and cjk < latin * 0.05:
        return 'en'
    return 'other'


def draft_lines(entries: list[dict[str, Any]], scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Subtitle rows used by the draft, clipped to its scenes, in source seconds."""
    from backend.pipeline.quality import to_seconds
    lines = []
    for scene in scenes:
        for entry in entries:
            start, end = to_seconds(entry['start_time']), to_seconds(entry['end_time'])
            text = str(entry.get('text') or '').strip()
            if not text or end <= scene['start'] or start >= scene['end']:
                continue
            lines.append({'start': max(start, scene['start']), 'end': min(end, scene['end']), 'text': text})
    return lines


def _fallback_title(draft: dict[str, Any], language: str) -> list[str]:
    import textwrap
    text = (draft.get('hook') or draft.get('title') or '').strip()
    # Word boundaries for Latin text; CJK has no spaces, so long runs are split by length.
    return textwrap.wrap(text, width=TITLE_LIMIT[language], break_long_words=True)[:2] if text else []


def _names_allowed(name: str, haystack: str) -> bool:
    parts = [p for p in re.split(r'\s+', name.strip()) if p]
    return bool(parts) and all(p.lower() in haystack for p in parts[:1])


def build_packaging(draft: dict[str, Any], lines: list[dict[str, Any]], strategy, *, burned: bool = False,
                    known_names: str = '', call: Callable[[str, dict], dict] | None = None) -> dict[str, Any]:
    """Packaging dict for `Draft.packaging`; never raises for model problems."""
    template, audience = strategy.template, strategy.audience_language
    src = source_language([line['text'] for line in lines])
    translate = src != audience and not burned
    base = {'template': template, 'audience_language': audience, 'source_language': src, 'burned_captions': burned}
    fallback = {**base, 'title_lines': _fallback_title(draft, audience), 'fallback': True,
                'cues': [] if burned else [{'start': l['start'], 'end': l['end'], 'text': l['text'][:200], 'original': ''} for l in lines]}
    if not lines:
        return Packaging.model_validate(fallback).model_dump()
    if call is None:
        from backend.services.studio.intelligence import text_json as call
    try:
        payload = {'template': template, 'audience_language': audience, 'translate': translate,
                   'title_limit': TITLE_LIMIT[audience], 'title_hint': draft.get('title', ''),
                   'known_names': known_names[:300], 'lines': [{'id': i, 'text': l['text']} for i, l in enumerate(lines)]}
        result = call(PROMPT, payload)
        return Packaging.model_validate(_validated(result, lines, base, translate, burned, known_names, draft)).model_dump()
    except Exception as error:  # noqa: BLE001 - packaging must never block output
        logger.warning('Packaging fell back: %s', type(error).__name__)
        return Packaging.model_validate(fallback).model_dump()


def _line(result_item: dict, lines: list) -> int | None:
    index = result_item.get('line') if isinstance(result_item, dict) else None
    return index if isinstance(index, int) and 0 <= index < len(lines) else None


def _validated(result, lines, base, translate, burned, known_names, draft):
    if not isinstance(result, dict):
        raise TypeError('packaging response is not an object')
    audience = base['audience_language']
    titles = [t.strip() for t in result.get('title_lines') or [] if isinstance(t, str) and t.strip()][:2]
    if not titles or any(len(t) > TITLE_LIMIT[audience] + 2 for t in titles):
        titles = _fallback_title(draft, audience)
    accent = result.get('accent_line') if result.get('accent_line') in (0, 1) else len(titles) - 1
    cues = []
    if not burned:
        translations = result.get('translations') or []
        if translate and (len(translations) != len(lines) or not all(isinstance(t, str) and 0 < len(t.strip()) <= 200 for t in translations)):
            raise ValueError('translations do not match lines')
        for i, line in enumerate(lines):
            text = translations[i].strip() if translate else line['text'][:200]
            cues.append({'start': line['start'], 'end': line['end'], 'text': text, 'original': line['text'][:300] if translate else ''})
    haystack = (' '.join(line['text'] for line in lines) + ' ' + known_names + ' ' + draft.get('title', '')).lower()
    speakers, seen = [], set()
    for item in result.get('speakers') or []:
        index, name = _line(item, lines), str((item or {}).get('name') or '').strip()
        if index is None or not name or len(name) > 40 or name.lower() in seen or not _names_allowed(name, haystack):
            continue
        seen.add(name.lower())
        speakers.append({'at': lines[index]['start'], 'name': name, 'role': str(item.get('role') or '').strip()[:60]})
    tags = []
    if base['template'] == 'interview_zh':
        for item in (result.get('tags') or [])[:MAX_TAGS]:
            index, text = _line(item, lines), str((item or {}).get('text') or '').strip()
            if index is not None and 0 < len(text) <= TAG_LIMIT:
                tags.append({'at': lines[index]['start'] + .2, 'text': text})
    highlights = []
    if base['template'] == 'podcast_en':
        for item in result.get('highlights') or []:
            index, word = _line(item, lines), str((item or {}).get('word') or '').strip()
            target = cues[index]['text'] if index is not None and cues else ''
            if index is not None and word and len(word) <= 30 and word.lower() in target.lower():
                highlights.append({'at': lines[index]['start'], 'text': word})
    return {**base, 'title_lines': titles, 'title_accent_line': min(accent, max(0, len(titles) - 1)),
            'cues': cues, 'speakers': speakers[:8], 'tags': tags, 'highlights': highlights[:40]}

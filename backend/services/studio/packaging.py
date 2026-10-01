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
KANA = re.compile(r'[぀-ヿ]')


def foreign_for(audience: str, text: str) -> bool:
    """Text an English-platform viewer cannot read: any Chinese or Japanese characters."""
    return audience == 'en' and bool(CJK.search(text or '') or KANA.search(text or ''))


def _items(value) -> list[dict]:
    # Model lists sometimes hold bare strings or come back as one object: keep only the objects.
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
LATIN = re.compile(r'[A-Za-z]')
TITLE_LIMIT = {'zh': 12, 'en': 36}
TAG_LIMIT = 10
MAX_TAGS = 5
MAX_SEGMENT_LINES = 12  # translated sentences may span short ASR rows; reject only paragraph-sized lumps

PROMPT = (
    '你是短视频包装编辑。根据 lines（已按时间排序的原字幕，常被切成半句，每行有 id）为这段访谈做包装，返回 JSON：\n'
    '{"title_lines":["...","..."],"accent_line":1,"segments":[{"from":0,"to":2,"text":"..."}],'
    '"speakers":[{"line":0,"name":"...","role":"..."}],"tags":[{"line":0,"text":"..."}],'
    '"highlights":[{"line":0,"word":"..."}]}\n'
    '规则：title_lines 用 audience_language 写 1–2 行，每行不超过 title_limit 个字符，概括最抓人的观点，不编造；'
    '两行合起来必须是完整的一句话或两个完整短语，宁短勿长，不要写到一半、不要破折号续半句，不用 markdown 或 HTML 符号；'
    'accent_line 是需要强调的那一行下标（0 或 1）。'
    'segments 把 lines 按完整句子重新分段：from/to 是连续的行 id 区间，按顺序首尾相接、覆盖全部行、不重叠；'
    '每段只含 1–2 句话、最多覆盖 4 行，不要把大段内容合成一段；'
    'translate 为 true 时 text 是该段翻译成 audience_language 的口语化译文（去掉口头禅，不添加事实）；'
    'translate 为 false 时字幕直接用原文，segments 返回空数组 []，不要复述原文。'
    'speakers 只填写在 lines 或 known_names 中明确出现过的人名，role 写其公开身份（不确定就留空），line 是此人第一次说话的行；'
    '不确定就返回空数组，绝不猜测身份。'
    'tags 仅当 template 为 interview_zh 时给出 2–4 个编辑点评（中文每个不超过 10 个字，英文不超过 30 个字符），必须具体点出这一句最有冲击力的内容，'
    '文字使用 audience_language（英文平台不得写中文）；例如“七分钟干完三个月”“以退为进”；禁止“逻辑清晰”“直击核心”“干货满满”这类泛泛评价；line 指向被点评的行。'
    'highlights 仅当 template 为 podcast_en 时给出，每 3–4 行最多一个，word 必须是该行（翻译后）里出现的单个关键词。'
    '另外返回 "mood"：按这段内容本身的情绪选一个——calm（冷静理性的分析）、serious（严肃、风险、警示）、'
    'bold（强观点、冲突、爆点）、warm（真诚、感动、个人经历）、playful（轻松、幽默、有趣）。'
)

# Content looks: the mood decides which palettes and styles fit; a seed from the content picks
# among them, so different clips look different while one clip looks the same on every platform.
MOOD_LOOKS = {
    'calm': (('azure', 'mint', 'lilac'), {'interview_zh': ('classic', 'spotlight'), 'podcast_en': ('cinematic', 'boxed')}),
    'serious': (('azure', 'amber'), {'interview_zh': ('classic', 'boxed'), 'podcast_en': ('cinematic', 'boxed')}),
    'bold': (('lemon', 'coral'), {'interview_zh': ('boxed', 'classic'), 'podcast_en': ('pop', 'boxed')}),
    'warm': (('amber', 'rose'), {'interview_zh': ('spotlight', 'classic'), 'podcast_en': ('boxed', 'cinematic')}),
    'playful': (('rose', 'lemon', 'mint'), {'interview_zh': ('boxed', 'spotlight'), 'podcast_en': ('pop', 'boxed')}),
}


def choose_look(template: str, mood: object, seed: str, avoid: tuple[str, ...] = ()) -> dict[str, str | None]:
    """{'mood', 'palette', 'style'} for this content; no valid mood keeps the golden default look.

    `avoid` = palettes already used by the other clips of this batch: pick a fresh one when the
    mood allows, so a batch the model calls all "bold" still does not repeat one colour.
    """
    import random
    if mood not in MOOD_LOOKS:
        return {'mood': None, 'palette': None, 'style': None}
    palettes, styles = MOOD_LOOKS[mood]
    pick = random.Random(f'{seed}:{mood}')
    fresh = [p for p in palettes if p not in avoid] or list(palettes)
    return {'mood': mood, 'palette': pick.choice(fresh), 'style': pick.choice(styles[template])}


def _clean(text: str) -> str:
    """Model text as plain words: decode HTML entities, drop markdown emphasis."""
    import html
    return re.sub(r'[*_`#]+', '', html.unescape(text)).strip()


def _seed(lines: list[dict[str, Any]]) -> str:
    return f"{lines[0]['start']:.1f}-{lines[-1]['end']:.1f}" if lines else ''


def source_language(texts: list[str]) -> str:
    joined = ''.join(texts)
    cjk, latin = len(CJK.findall(joined)), len(LATIN.findall(joined))
    if len(KANA.findall(joined)) >= max(5, cjk * 0.1):
        return 'other'  # Japanese: kanji alone must not pass for Chinese
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
            from backend.services.studio.caption_layout import timed_screens, width
            # Paragraph cues need pages on their source clock, just like landscape subtitles.
            # This also avoids silently losing their tail to PackagingCue's 600-character cap.
            pages = timed_screens(text, start, end, 24) if len(text) > 600 or (end - start > 8 and width(text) > 48) else [(start, end, text, '')]
            for a, b, page, _ in pages:
                a, b = max(a, scene['start']), min(b, scene['end'])
                if b > a:
                    lines.append({'start': a, 'end': b, 'text': page.replace('\\N', ' ')})
    return lines


def _fallback_title(draft: dict[str, Any], language: str) -> list[str]:
    import textwrap
    text = _clean(draft.get('hook') or draft.get('title') or '')
    # Width follows the title's own language: an English title on a Chinese platform is not cut at 12.
    own = 'zh' if source_language([text]) == 'zh' else 'en'
    wrap = lambda t: textwrap.wrap(t, width=TITLE_LIMIT[own], break_long_words=True)  # noqa: E731
    # Keep whole clauses: two lines of the first clauses read better than a line cut mid-phrase.
    clauses = [c for c in re.split(r'(?<=[，。：；！？、,:;!?—])', text) if c.strip()]
    kept = ''
    for clause in clauses:
        if len(wrap(kept + clause)) > 2:
            break
        kept += clause
    kept = kept.rstrip('，、：；,:;— ') or text
    return wrap(kept)[:2] if text else []


def _names_allowed(name: str, haystack: str) -> bool:
    parts = [p for p in re.split(r'\s+', name.strip()) if p]
    return bool(parts) and all(p.lower() in haystack for p in parts[:1])


def build_packaging(draft: dict[str, Any], lines: list[dict[str, Any]], strategy, *, burned: bool = False,
                    burned_language: str | None = None, known_names: str = '', call: Callable[[str, dict], dict] | None = None,
                    avoid_palettes: tuple[str, ...] = ()) -> dict[str, Any]:
    """Packaging dict for `Draft.packaging`; never raises for model problems."""
    template, audience = strategy.template, strategy.audience_language
    src = source_language([line['text'] for line in lines])
    # Captions already in the picture replace ours only when the audience reads them: Chinese
    # captions on a Chinese talk need nothing more for Douyin but English ones for TikTok; English
    # captions on a Japanese talk (read from the frame, else assumed to follow the speech) are
    # enough for TikTok, while Douyin still needs Chinese.
    captions = not burned or (burned_language or src) != audience
    translate = captions and src != audience
    base = {'template': template, 'audience_language': audience, 'source_language': src, 'burned_captions': burned}
    # Never mix languages: a fallback shows only what is already in the audience's language.
    fallback_title = [line for line in _fallback_title(draft, audience) if not foreign_for(audience, line)]
    fallback = {**base, 'title_lines': fallback_title, 'fallback': True,
                'cues': [] if not captions or translate else [{'start': l['start'], 'end': l['end'], 'text': l['text'][:600], 'original': ''} for l in lines]}
    if not lines:
        return Packaging.model_validate(fallback).model_dump()
    if call is None:
        from backend.services.studio.intelligence import text_json as call
    payload = {'template': template, 'audience_language': audience, 'translate': translate,
               'title_limit': TITLE_LIMIT[audience], 'title_hint': draft.get('title', ''),
               'known_names': known_names[:300], 'lines': [{'id': i, 'text': l['text']} for i, l in enumerate(lines)]}
    # Short ASR rows make the segment contract easy to break once; a second try with the reason
    # usually fixes it, and losing the whole package (captions included) costs far more.
    for attempt in range(2):
        try:
            result = call(PROMPT, payload)
            return Packaging.model_validate(_validated(result, lines, base, translate, burned, known_names, draft, avoid_palettes, captions)).model_dump()
        except (ValueError, TypeError) as error:
            logger.warning('Packaging response rejected (attempt %d): %s', attempt + 1, error)
            payload = {**payload, 'previous_error': f'上一次返回不合格：{error}。请严格按规则重新返回。'}
        except Exception as error:  # noqa: BLE001 - packaging must never block output
            logger.warning('Packaging fell back: %s', type(error).__name__)
            break
    if translate:
        # Last resort for foreign-language audiences: plain line-by-line translation, so the
        # version still gets captions in its own language instead of none (or the source's).
        fallback['cues'] = _translated_rows(lines, audience, call)
    return Packaging.model_validate(fallback).model_dump()


def _translated_rows(lines: list[dict[str, Any]], audience: str, call) -> list[dict[str, Any]]:
    language = {'zh': '简体中文', 'en': 'English'}[audience]
    try:
        result = call(f'把 lines 逐条翻译成{language}，口语自然，保持条数与顺序，不添加事实。返回 {{"lines":["..."]}}',
                      {'lines': [line['text'] for line in lines]})
        rows = (result or {}).get('lines') if isinstance(result, dict) else None
        if not isinstance(rows, list) or len(rows) != len(lines) or not all(isinstance(r, str) and r.strip() for r in rows):
            return []
        return [{'start': l['start'], 'end': l['end'], 'text': _clean(r)[:600], 'original': ''} for l, r in zip(lines, rows)]
    except Exception as error:  # noqa: BLE001
        logger.warning('Row translation failed: %s', type(error).__name__)
        return []


def _line(result_item: dict, lines: list) -> int | None:
    index = result_item.get('line') if isinstance(result_item, dict) else None
    return index if isinstance(index, int) and 0 <= index < len(lines) else None


def _segments(raw, lines, translate):
    """Sentence cues from model segments: contiguous, ordered, covering every line exactly once.

    Source subtitles are often cut mid-sentence, so the model regroups lines into sentences; each
    cue spans its lines' times and keeps their joined original text for bilingual captions.
    """
    if not isinstance(raw, list) or not raw:
        raise ValueError('segments missing')
    cues, expected = [], 0
    for item in raw:
        item = item if isinstance(item, dict) else {}
        start, end = item.get('from'), item.get('to')
        text = _clean(str(item.get('text') or ''))
        if not (isinstance(start, int) and isinstance(end, int)) or start != expected or end < start or end >= len(lines):
            raise ValueError('segments are not contiguous')
        if end - start >= MAX_SEGMENT_LINES:
            raise ValueError('segment spans too many lines')
        if not text or len(text) > 600:
            raise ValueError('segment text invalid')
        original = ' '.join(line['text'] for line in lines[start:end + 1])
        cues.append({'start': lines[start]['start'], 'end': lines[end]['end'], 'text': text,
                     'original': original[:900] if translate else '', 'lines': (start, end)})
        expected = end + 1
    if expected != len(lines):
        raise ValueError('segments do not cover every line')
    return cues


def _validated(result, lines, base, translate, burned, known_names, draft, avoid_palettes=(), captions=None):
    if not isinstance(result, dict):
        raise TypeError('packaging response is not an object')
    audience = base['audience_language']
    raw_titles = result.get('title_lines')
    raw_titles = [raw_titles] if isinstance(raw_titles, str) else raw_titles if isinstance(raw_titles, list) else []
    titles = [_clean(t) for t in raw_titles if isinstance(t, str) and _clean(t)][:2]
    if audience == 'zh' and any(KANA.search(t) for t in titles):
        titles = []  # a Japanese title on a Chinese platform: use the draft title instead
    if any(foreign_for(audience, t) for t in titles):
        titles = []  # a Chinese title on an English platform: never shown; the fallback below is filtered too
    limit = TITLE_LIMIT[audience]
    if titles and any(len(t) > limit + 2 for t in titles):
        # Models often return one long line: keep their wording when it fits two lines, breaking
        # Chinese at punctuation / natural joints and Latin at spaces, never through a word.
        from backend.services.studio.caption_layout import lines_for
        joined = ('' if audience == 'zh' else ' ').join(titles)
        cap = 16 if audience == 'zh' else 40
        chars = min(cap, max(limit, len(joined) / 2 + 4))  # balanced two lines with slack for word boundaries
        # lines_for works in display width (CJK 1, Latin 0.55); convert the character budget.
        rewrapped = lines_for(joined, chars if audience == 'zh' else chars * 0.55)
        titles = rewrapped if 0 < len(rewrapped) <= 2 and all(len(t) <= cap for t in rewrapped) else []
    if not titles:
        titles = [line for line in _fallback_title(draft, audience) if not foreign_for(audience, line)]
    accent = result.get('accent_line') if result.get('accent_line') in (0, 1) else len(titles) - 1
    cues = []
    if captions if captions is not None else (not burned or translate):
        if translate:
            cues = _segments(result.get('segments'), lines, translate)  # invalid translation: whole package falls back
            if any(foreign_for(audience, cue['text']) for cue in cues):
                raise ValueError('English captions contain Chinese or Japanese text')
        else:
            # Same language: the source rows are what is actually said and carry the tightest timing.
            # Merged sentence segments spread word timing over 20 s+ and drift from the audio.
            cues = [{'start': l['start'], 'end': l['end'], 'text': l['text'][:600], 'original': '', 'lines': (i, i)}
                    for i, l in enumerate(lines)]
        if burned or audience == 'en':
            for cue in cues:
                # Burned: the picture already carries a caption, never stack a third line.
                # English: its templates show English only, so the source text is not kept either.
                cue['original'] = ''
    haystack = (' '.join(line['text'] for line in lines) + ' ' + known_names + ' ' + draft.get('title', '')).lower()
    speakers, seen = [], set()
    for item in _items(result.get('speakers')):
        index, name = _line(item, lines), str(item.get('name') or '').strip()
        if index is None or not name or len(name) > 40 or name.lower() in seen or not _names_allowed(name, haystack):
            continue
        if foreign_for(audience, name):
            continue  # a nameplate the audience cannot read is worse than none
        role = str(item.get('role') or '').strip()[:60]
        seen.add(name.lower())
        speakers.append({'at': lines[index]['start'], 'name': name, 'role': '' if foreign_for(audience, role) else role})
    tags = []
    if base['template'] == 'interview_zh':
        for item in _items(result.get('tags'))[:MAX_TAGS]:
            index, text = _line(item, lines), str(item.get('text') or '').strip()
            if index is not None and 0 < len(text) <= (TAG_LIMIT if audience == 'zh' else 30) and not foreign_for(audience, text):
                tags.append({'at': lines[index]['start'] + .2, 'text': text})
    highlights = []
    if base['template'] == 'podcast_en':
        for item in _items(result.get('highlights')):
            index, word = _line(item, lines), str(item.get('word') or '').strip()
            cue = next((c for c in cues if index is not None and c['lines'][0] <= index <= c['lines'][1]), None)
            if cue and word and len(word) <= 30 and word.lower() in cue['text'].lower():
                highlights.append({'at': cue['start'], 'text': word})
    for cue in cues:
        cue.pop('lines', None)
    look = choose_look(base['template'], result.get('mood'), _seed(lines), avoid_palettes)
    return {**base, **look, 'title_lines': titles, 'title_accent_line': min(accent, max(0, len(titles) - 1)),
            'cues': cues, 'speakers': speakers[:8], 'tags': tags, 'highlights': highlights[:40]}

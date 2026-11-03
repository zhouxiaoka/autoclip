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



def _term_present(term: str, text: str) -> bool:
    return bool(re.search(r'(?<![A-Za-z0-9_])' + re.escape(term) + r'(?![A-Za-z0-9_])', text, re.IGNORECASE))


def _protected_terms(draft: dict[str, Any], lines: list[dict[str, Any]], audience: str) -> list[str]:
    # A mixed Chinese title already retains terms the editor chose not to translate.
    # Protect only those also present as complete words in the actual source rows;
    # never infer a person's identity or force an English headline to remain English.
    title = str(draft.get('title') or '')
    if audience != 'zh' or not CJK.search(title):
        return []
    source = ' '.join(str(line.get('text') or '') for line in lines)
    return list(dict.fromkeys(term for term in re.findall(r'[A-Z][A-Za-z0-9_+-]{1,39}', title)
                             if _term_present(term, source)))


def _check_preserved_terms(source: str, target: str, terms: list[str]) -> None:
    if any(_term_present(term, source) and not _term_present(term, target) for term in terms):
        # Keep source words out of log messages; the model receives the separate term list.
        raise ValueError('translation changed a protected original name or term')


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
    'protected_terms 是已在原字幕和中文标题中出现的专名或术语；标题和译文提到它们时保留原文拼写，不能改成地名或猜测音译。'
    'translate 为 false 时字幕直接用原文，segments 返回空数组 []，不要复述原文。'
    'speakers 只填写在 lines 或 known_names 中明确出现过的人名，role 写其公开身份（不确定就留空），line 是此人第一次说话的行；'
    'name 用 audience_language 写给观众看的名字：中文受众写黄仁勋，不要写 Jensen Huang。'
    '不确定就返回空数组，绝不猜测身份。'
    'tags 仅当 template 为 interview_zh 时给出 2–4 个编辑点评（中文每个不超过 10 个字，英文不超过 30 个字符），必须具体点出这一句最有冲击力的内容，'
    '文字使用 audience_language（英文平台不得写中文）；例如“七分钟干完三个月”“以退为进”；禁止“逻辑清晰”“直击核心”“干货满满”这类泛泛评价；line 指向被点评的行。'
    'highlights 仅当 template 为 podcast_en 时给出，每 3–4 行最多一个，word 必须是该行（翻译后）里出现的单个关键词。'
    '另外返回 "marks"：每一句一条 {"line":行id,"text":"关键词","speaker":"说话人"}。'
    'line 是该句覆盖的某一行 id；text 是该句译文（或原文）里最该标出的一个短词或短语（中文 2–8 个字，英文一个词），'
    '必须是该句 text 的连续子串，不能是整句，不能编造。'
    'speaker 是这一句实际在说话的人，必须等于 speakers 里的 name，并且用 audience_language 的写法；'
    '主持人和嘉宾分开标，不要把唯一的嘉宾标到每一句；主持人的句子省略 speaker，不确定也省略 speaker。'
    '可以额外返回 "deck"：一行完整的英文斜体导语，不超过 60 个字符，概括主题，例如 "Jensen Huang on the five-layer cake"；'
    '写不出完整的一句就省略，不要返回被截断的半句。'
    '可以额外返回 "issue"：杂志页脚的节目和日期，不超过 60 个字符，例如 "DWARKESH PODCAST · 2026.04.15"；不确定就省略。'
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
                # Silence-snapped cuts can overlap only the last few milliseconds of the
                # previous question. Do not replay that entire row in captions or translation.
                if b - a >= min(.15, (end - start) * .2):
                    lines.append({'start': a, 'end': b, 'text': page.replace('\\N', ' ')})
    return lines


def _fallback_title(draft: dict[str, Any], language: str) -> list[str]:
    import textwrap
    text = _clean(draft.get('hook') or draft.get('title') or '')
    # Width follows the title's own language: an English title on a Chinese platform is not cut at 12.
    own = 'zh' if source_language([text]) == 'zh' else 'en'
    from backend.services.studio.caption_layout import lines_for
    wrap = lambda t: lines_for(t, TITLE_LIMIT[own]) if own == 'zh' else textwrap.wrap(t, width=TITLE_LIMIT[own], break_long_words=True)  # noqa: E731
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


_EN_STOP = {
    'the', 'a', 'an', 'and', 'or', 'to', 'of', 'in', 'on', 'for', 'that', 'this', 'with', 'is', 'are',
    'was', 'were', 'be', 'it', 'as', 'at', 'by', 'from', 'i', 'you', 'he', 'she', 'we', 'they',
}


def _accept_phrase(phrase: str, text: str) -> str:
    """The phrase only counts when it is a short piece of the cue, not the whole sentence."""
    phrase = _clean(phrase)
    if not phrase or not text or phrase == text or len(phrase) > 30:
        return ''
    if phrase in text:
        return phrase
    at = text.lower().find(phrase.lower())
    if at < 0:
        return ''
    return text[at:at + len(phrase)]


_HOST_NAMES = {'主持人', '嘉宾', '采访者', '记者', 'host', 'interviewer', 'guest'}


def key_phrase(text: str, original: str = '') -> str:
    """One highlight already inside `text`. The same inputs always return the same phrase.

    A figure the speaker said wins. Otherwise the last whole word of the last clause
    (a 的/了/着 split, not a 4-character slice), or the last content word of an English line.
    `original` is unused on purpose: a Chinese phrase is not mapped onto an English translation.
    """
    del original
    cleaned = ' '.join(str(text or '').split())
    if not cleaned:
        return ''
    number = re.search(
        r'\d+(?:\.\d+)?(?:\s*[十百千万亿])?(?:\s*(?:倍|个|%|％|年|天|小时|分钟|秒|元|块))?',
        cleaned,
    )
    if number:
        token = number.group().strip()
        if token and token != cleaned and token in cleaned:
            return token[:30]
    parts = [part.strip() for part in re.split(r'[，。！？、；,.!?;:]+', cleaned) if part.strip()]
    chunk = parts[-1] if parts else cleaned
    if CJK.search(chunk):
        from backend.services.studio.cjk_segment import whole_phrase
        phrase = whole_phrase(chunk) or whole_phrase(cleaned)
        if phrase and phrase != cleaned and phrase in cleaned and not phrase.startswith(tuple('的了着过')):
            return phrase[:8]
        return ''
    words = re.findall(r"[A-Za-z][A-Za-z']*", cleaned)
    content = [word for word in words if word.lower() not in _EN_STOP and len(word) > 3]
    chosen = content[-1] if content else (words[-1] if words else '')
    if chosen and chosen != cleaned:
        return chosen[:30]
    return ''


def _cjk_guest_names(*blobs: str) -> list[str]:
    found: list[str] = []
    for blob in blobs:
        for token in re.split(r'[\s,，、/|]+', blob or ''):
            token = token.strip()
            if len(token) < 2 or token.lower() in _HOST_NAMES or not CJK.search(token) or LATIN.search(token):
                continue
            if token not in found:
                found.append(token)
    return found


def _localize_zh_name(name: str, audience: str, *blobs: str) -> str:
    """The Chinese form of a Latin name, or '' when this listing has no single CJK guest.

    黄仁勋 stays. Jensen Huang becomes 黄仁勋 when that Chinese name is the only guest in the
    known names or the roster. An unmapped Latin name is left for the caller: the cover title
    is no longer burned in its place.
    """
    name = (name or '').strip()
    if not name:
        return ''
    if audience != 'zh' or CJK.search(name) or not LATIN.search(name):
        return name
    guests = _cjk_guest_names(*blobs)
    if len(guests) != 1:
        return ''
    folded = ' '.join(blobs).lower()
    tokens = [part.lower() for part in re.split(r'\s+', name) if len(part) > 1]
    if any(token in folded for token in tokens):
        return guests[0]
    nonempty = [blob.strip() for blob in blobs if str(blob or '').strip()]
    if len(nonempty) == 1 and nonempty[0] == guests[0]:
        return guests[0]
    return ''


_NOT_A_NAME = {
    'the', 'a', 'an', 'how', 'why', 'what', 'when', 'where', 'who',
    'interview', 'podcast', 'episode', 'official', 'full', 'on', 'and', 'with',
}


def _exact_person(text: str) -> str:
    """A name and nothing else: 黄仁勋, or Sam Altman, or Mary J. Smith."""
    text = ' '.join(str(text or '').split())
    if not text or text.lower() in _HOST_NAMES:
        return ''
    if CJK.search(text) and not LATIN.search(text):
        return text if re.fullmatch(r'[㐀-鿿]{2,4}', text) and text not in _HOST_NAMES else ''
    words = text.split()
    if not 2 <= len(words) <= 3:
        return ''
    if not all(re.fullmatch(r"[A-Z][A-Za-z'.-]{1,30}", word) for word in words):
        return ''
    if any(word.lower() in _HOST_NAMES or word.lower() in _NOT_A_NAME for word in words):
        return ''
    if len(words) == 3 and not re.fullmatch(r"[A-Z]\.?", words[1]):
        return ''
    return ' '.join(words)


def _listing_guest(known_names: str) -> str:
    """The one person a public title names. Empty when the title does not name one person.

    ``Sam Altman on Astra, AGI...`` and ``Sam Altman: Never a Better Time`` and ``黄仁勋：五层蛋糕``
    name the guest. A channel pasted after that title is not a second guess.
    """
    text = ' '.join(str(known_names or '').split())
    if not text:
        return ''
    titled = re.split(r'[:：|｜]', text, maxsplit=1)[0].strip()
    named = re.match(r'^(.+?)\s+on\s+\S', titled, flags=re.IGNORECASE)
    return _exact_person(named.group(1) if named else titled)


def _apply_audience_names(speakers: list[dict], cues: list[dict], audience: str, known_names: str) -> tuple[list[dict], list[dict]]:
    """Rewrite a Latin guest to the one Chinese name we actually know. Leave every other name as written.

    Sam Altman stays Sam Altman when the package has no 黄仁勋 to put in his place. Street
    paints that Latin name: the cover title is not burned underneath it.
    """
    if audience != 'zh':
        return speakers, cues
    renamed = []
    for item in speakers:
        original = str(item.get('name') or '')
        name = _localize_zh_name(original, audience, known_names)
        renamed.append({**item, 'name': name or original})
    roster = ' '.join(item['name'] for item in renamed)
    for cue in cues:
        if not isinstance(cue, dict):
            continue
        original = str(cue.get('speaker') or '')
        localized = _localize_zh_name(original, audience, known_names, roster)
        cue['speaker'] = localized or original
    return renamed, cues


def _speaker_name(text: str, start: float, claimed: str, speakers: list[dict]) -> str:
    """Who is talking in this cue. Only a name the cue claimed, or the one name the line itself says.

    The person who is on screen at `start` is not assumed to be the speaker. One guest in the
    roster used to label the host's lines as well.
    """
    del start
    known = [item for item in speakers if str(item.get('name') or '').strip()]
    names = {item['name'] for item in known}
    if claimed and claimed in names:
        return claimed
    mentioned = [item['name'] for item in known if item['name'] and item['name'] in (text or '')]
    if len(mentioned) == 1:
        return mentioned[0]
    return ''


def _stamp_cues(payload: dict) -> dict:
    """Fill a missing emphasis and speaker, then validate. Classic ASS never reads these fields."""
    speakers = list(payload.get('speakers') or [])
    deck = _clean(str(payload.get('deck') or '')) if payload.get('deck') else ''
    payload = {**payload, 'deck': deck if deck and LATIN.search(deck) and len(deck) <= 80 else ''}
    cues = []
    for cue in payload.get('cues') or []:
        if not isinstance(cue, dict):
            continue
        text = str(cue.get('text') or '')
        phrase = _accept_phrase(str(cue.get('emphasis') or ''), text) or key_phrase(text, str(cue.get('original') or ''))
        speaker = _speaker_name(text, cue.get('start') or 0, str(cue.get('speaker') or '').strip(), speakers)
        cues.append({**cue, 'emphasis': phrase, 'speaker': speaker})
    payload = {**payload, 'cues': cues}
    return Packaging.model_validate(payload).model_dump()


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
    # Foreign titles on English platforms stay hidden; a rejected translation later preserves
    # readable source captions rather than silently removing the subtitle track.
    fallback_title = [line for line in _fallback_title(draft, audience) if not foreign_for(audience, line)]
    fallback = {**base, 'title_lines': fallback_title, 'fallback': True,
                'cues': [] if not captions or translate else [{'start': l['start'], 'end': l['end'], 'text': l['text'][:600], 'original': ''} for l in lines]}
    if not lines:
        return _stamp_cues(fallback)
    if call is None:
        from backend.services.studio.intelligence import text_json as call
    payload = {'template': template, 'audience_language': audience, 'translate': translate,
               'title_limit': TITLE_LIMIT[audience], 'title_hint': draft.get('title', ''),
               'line_count': len(lines), 'last_line_id': len(lines) - 1,
               'protected_terms': _protected_terms(draft, lines, audience),
               'known_names': known_names[:300], 'lines': [{'id': i, 'text': l['text']} for i, l in enumerate(lines)]}
    # Short ASR rows make the segment contract easy to break once; a second try with the reason
    # usually fixes it, and losing the whole package (captions included) costs far more.
    for attempt in range(2):
        try:
            result = call(PROMPT, payload)
            return _stamp_cues(_validated(result, lines, base, translate, burned, known_names, draft, avoid_palettes, captions))
        except (ValueError, TypeError) as error:
            logger.warning('Packaging response rejected (attempt %d): %s', attempt + 1, error)
            payload = {**payload, 'previous_error': f'上一次返回不合格：{error}。请严格按规则重新返回。'}
        except Exception as error:  # noqa: BLE001 - packaging must never block output
            logger.warning('Packaging fell back: %s', type(error).__name__)
            break
    if translate:
        # Last resort for foreign-language audiences: plain line-by-line translation, so the
        # version still gets captions in its own language instead of none (or the source's).
        fallback['cues'] = _translated_rows(lines, audience, call, keep_original=template == 'interview_zh' and not burned,
                                             protected_terms=_protected_terms(draft, lines, audience))
        if not fallback['cues'] and not burned:
            # A rejected model response must not turn an English interview into a captionless
            # video. Keep readable source rows and disclose the loss of translation in the UI.
            fallback['cues'] = source_cues(lines, audience)
    return _stamp_cues(fallback)


def source_cues(lines: list[dict[str, Any]], audience: str) -> list[dict[str, Any]]:
    return [{'start': l['start'], 'end': l['end'], 'text': l['text'][:600], 'original': ''}
            for l in lines if not foreign_for(audience, l['text'])]


def _translated_rows(lines: list[dict[str, Any]], audience: str, call, *, keep_original=False,
                     protected_terms: list[str] | None = None) -> list[dict[str, Any]]:
    language = {'zh': '简体中文', 'en': 'English'}[audience]
    try:
        result = call(f'把 lines 逐条翻译成{language}，口语自然，不合并、不遗漏，不添加事实。'
                      'protected_terms 中的原文专名和术语在译文中必须保留拼写，不猜测音译或改成地名。'
                      '每个输入 id 必须恰好返回一次。返回 {"lines":[{"id":0,"text":"..."}]}',
                      {'protected_terms': protected_terms or [],
                       'lines': [{'id': i, 'text': line['text']} for i, line in enumerate(lines)]})
        rows = (result or {}).get('lines') if isinstance(result, dict) else None
        if not isinstance(rows, list) or len(rows) != len(lines):
            return []
        if all(isinstance(r, dict) for r in rows):
            ids = [r.get('id') for r in rows]
            if any(type(i) is not int for i in ids) or set(ids) != set(range(len(lines))):
                return []
            rows = [r.get('text') for r in sorted(rows, key=lambda r: r['id'])]
        # Accept the earlier ordered-string contract too; never silently zip a short result.
        if not all(isinstance(r, str) and _clean(r) and not foreign_for(audience, r) for r in rows):
            return []
        if audience == 'zh' and not any(CJK.search(r) for r in rows):
            return []
        for line, row in zip(lines, rows):
            _check_preserved_terms(line['text'], _clean(row)[:600], protected_terms or [])
        return [{'start': l['start'], 'end': l['end'], 'text': _clean(r)[:600],
                 'original': l['text'][:900] if keep_original else ''} for l, r in zip(lines, rows)]
    except Exception as error:  # noqa: BLE001
        logger.warning('Row translation failed: %s', type(error).__name__)
        return []


def _line(result_item: dict, lines: list) -> int | None:
    index = result_item.get('line') if isinstance(result_item, dict) else None
    return index if isinstance(index, int) and 0 <= index < len(lines) else None


_CLAUSE_END = re.compile(r'(?<=[。！？；，、…!?;,])')


def _jumps(lines, start, end):
    """Line ids inside a segment where the next line is not the one spoken next.

    Draft lines follow the edit, so a cold open puts later speech first. A segment that groups
    the cold open with the shot after it runs backwards (1245.78 -> 1236.22) or skips the cold
    open's lines in the source. A plain cut between consecutive lines is not a jump.
    """
    jumps = []
    for i in range(start, end):
        here, there = lines[i], lines[i + 1]
        backwards = there['start'] < here['end'] - .05
        skipped = any(here['end'] - .05 <= line['start'] < there['start'] - .05
                      for k, line in enumerate(lines) if not start <= k <= end)
        if backwards or skipped:
            jumps.append(i)
    return jumps


def _split_at_jumps(lines, start, end, text):
    """Split a segment's text where its lines jump, at the clause nearest each run's share of the text.

    Each run keeps its own subtitle timing. A jump with no clause break near it stays joined to
    the run before; a run that still goes backwards is timed on its first run's lines only.
    """
    jumps = _jumps(lines, start, end)
    if not jumps:
        return [((start, end), text)]
    clauses = [c for c in _CLAUSE_END.split(text) if c]
    sizes = [max(1, len(line['text'])) for line in lines[start:end + 1]]
    total, chars = sum(sizes), len(text)
    cuts, used = [], 0
    edges = [sum(len(c) for c in clauses[:k]) for k in range(1, len(clauses))]
    for jump in jumps:
        target = sum(sizes[:jump - start + 1]) / total * chars
        choices = [k for k, edge in enumerate(edges) if k >= used]
        if not choices:
            continue
        best = min(choices, key=lambda k: abs(edges[k] - target))
        if abs(edges[best] - target) > max(4, chars * .25):
            continue
        cuts.append((jump, best + 1))
        used = best + 1
    runs, lo, at = [], start, 0
    for jump, clause in cuts:
        runs.append(((lo, jump), ''.join(clauses[at:clause])))
        lo, at = jump + 1, clause
    runs.append(((lo, end), ''.join(clauses[at:])))
    out = []
    for (a, b), piece in runs:
        inner = [j for j in jumps if a <= j < b and lines[j + 1]['start'] < lines[j]['end'] - .05]
        if inner:
            b = inner[0]  # still backwards: keep the text on the lines it starts with
        out.append(((a, b), piece))
    return out


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
        for (lo, hi), piece in _split_at_jumps(lines, start, end, text):
            original = ' '.join(line['text'] for line in lines[lo:hi + 1])
            cues.append({'start': lines[lo]['start'], 'end': lines[hi]['end'], 'text': piece,
                         'original': original[:900] if translate else '', 'lines': (lo, hi), 'group': (start, end)})
        expected = end + 1
    if expected != len(lines):
        raise ValueError(f'segments do not cover every line: expected ids 0..{len(lines) - 1}, stopped at {expected - 1}')
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
    protected = _protected_terms(draft, lines, audience)
    if protected and any(not _term_present(term, ' '.join(titles)) for term in protected):
        titles = []  # The existing mixed title is safer than renaming its people/terms.
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
            if audience == 'zh' and not any(CJK.search(cue['text']) for cue in cues):
                raise ValueError('Chinese translation contains no Chinese captions')
            groups = {}
            for cue in cues:
                groups.setdefault(cue.pop('group'), []).append(cue['text'])
            for (start, end), texts in groups.items():
                original = ' '.join(line['text'] for line in lines[start:end + 1])
                _check_preserved_terms(original, ''.join(texts), protected)
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
    if not speakers:
        # The model often leaves speakers empty even when the public title names the guest.
        # Street's nameplate is that name. It is not the cover title, and it is not a guess.
        guest = _listing_guest(known_names)
        if guest and guest.lower() not in seen and _names_allowed(guest, haystack) and not foreign_for(audience, guest):
            speakers.append({'at': lines[0]['start'], 'name': guest, 'role': ''})
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
    marks = _items(result.get('marks'))
    kept = speakers[:8]
    for cue in cues:
        lo, hi = cue.get('lines', (0, 0))
        mark = next((item for item in marks if isinstance(item.get('line'), int) and lo <= item['line'] <= hi), {})
        cue['emphasis'] = _accept_phrase(str(mark.get('text') or ''), cue['text'])
        cue['speaker'] = str(mark.get('speaker') or '').strip()
        cue.pop('lines', None)
    deck = _clean(str(result.get('deck') or '')) if isinstance(result.get('deck'), str) else ''
    issue = _clean(str(result.get('issue') or ''))[:80] if isinstance(result.get('issue'), str) else ''
    look = choose_look(base['template'], result.get('mood'), _seed(lines), avoid_palettes)
    kept, cues = _apply_audience_names(kept, cues, audience, known_names)
    return {**base, **look, 'title_lines': titles, 'title_accent_line': min(accent, max(0, len(titles) - 1)),
            'cues': cues, 'speakers': kept, 'tags': tags, 'highlights': highlights[:40], 'deck': deck, 'issue': issue}

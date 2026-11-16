"""Translation follows utterances; display pagination happens after translation.

Only source text is joined/split here. The model never assigns IDs or timestamps.
Intra-row timing remains an estimate from the supplied subtitle, not word alignment.
"""
from __future__ import annotations

import re

MAX_CHARS = 600
MAX_SECONDS = 24
_END = re.compile(r'[。！？]+["”」』]?|[.!?…]+["”」』]?(?=\s|$)')
_ABBREVIATION = re.compile(r'(?:\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|vs|etc)|\b[A-Z])\.$', re.I)
_DEPENDENT = re.compile(r'\b(?:not|never|no|any|every|some|is|are|was|were|be|been|being|'
                        r'who|which|that|because|although|unless|if|when|while|and|or|but|'
                        r'the|a|an|of|to|for|with|without|from|in|at|than|even like|can do now)\s*[,;:]?$', re.I)


def sentence_offsets(text):
    """Real punctuation, excluding decimal points, initials and common abbreviations."""
    for match in _END.finditer(text):
        if match.group() == '.' and _ABBREVIATION.search(text[:match.end()]):
            continue
        yield match.end()


def _pieces(row):
    text = row['text'].strip()
    cursor = 0
    for end in [*sentence_offsets(text), len(text)]:
        if end <= cursor:
            continue
        # Very long unpunctuated transcripts still have a bounded request and no lost tail.
        while end - cursor > MAX_CHARS:
            cut = text.rfind(' ', cursor + 1, cursor + MAX_CHARS + 1)
            cut = cut if cut > cursor else cursor + MAX_CHARS
            yield _part(row, text, cursor, cut)
            cursor = cut
        if text[cursor:end].strip():
            yield _part(row, text, cursor, end)
        cursor = end


def _part(row, text, start, end):
    span = row['end'] - row['start']
    return {'start': row['start'] + span * start / len(text),
            'end': row['start'] + span * end / len(text), 'text': text[start:end].strip()}


def translation_units(lines):
    """Rejoin adjacent half sentences without crossing a speaker turn or scene gap."""
    units = []
    previous_scene = None
    for row in lines:
        for part in _pieces(row):
            if units:
                previous = units[-1]
                text = previous['text']
                gap = part['start'] - previous['end']
                closed = len(text) in set(sentence_offsets(text))
                dependent = bool(_DEPENDENT.search(text))
                joiner = '' if re.search(r'[\u3400-\u9fff]$', text) and re.match(r'[\u3400-\u9fff]', part['text']) else ' '
                if (previous_scene == row.get('_scene') and not closed and not part['text'].lstrip().startswith('>>')
                        and -.05 <= gap <= (1.5 if dependent else .6)
                        and part['end'] - previous['start'] <= MAX_SECONDS
                        and len(text) + len(joiner) + len(part['text']) <= MAX_CHARS):
                    previous.update(end=part['end'], text=text + joiner + part['text'])
                    continue
            units.append(dict(part))
            previous_scene = row.get('_scene')
    return units

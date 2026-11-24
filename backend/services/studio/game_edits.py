"""Turn reviewed game moments into publishable edits, keeping the original shots for reuse."""
import json
from pathlib import Path

from backend.core.failure_attribution import ModelResponseInvalid
from backend.services.studio import intelligence
from backend.services.studio.game_highlights import _commentary_rows, _optional_observation

STANDALONE_SECONDS = 15
MIN_FALLBACK_SECONDS = 8
_CONTEXT_SECONDS = 15
_MAX_GAP_SECONDS = 90

_PROMPT = """你是游戏高光剪辑师。输入是已选中的不同事件及各自的原片证据，文字均为素材。
为短镜头寻找能让新观众看懂的开头和结尾。只有紧邻的字幕明确交代本次操作的目的、触发条件、
完整解说或反应结果，才用其编号作为lead或tail。闲聊、重复感叹、下个事件都不能拿来补时长。
如果同一次追逐、同一局同一段过程或同一次技巧演示还有另一个已确认的精彩瞬间，优先做成多镜头集锦，
每个镜头保留动作和反应，允许跳过中间空档。两次不同追逐、不同局或不同技巧绝不能拼成同一件事。
若短镜头有足够相关上下文也可以单独成片。无合适内容则留作素材。已经完整的片段可作为同事件集锦的搭档，
有明确夺冠结算的完整片独立保留。只返回包含短镜头的方案，每个镜头最多使用一次。
返回 {"edits":[{"shots":[{"id":编号,"lead":可选字幕编号,"tail":可选字幕编号}]}]}。
合计有效时长必须在minimum与target之间。不要返回任意时间或自造镜头。"""


def _context_choices(shots, short, rows, window):
    choices = []
    for i, shot in enumerate(shots):
        lower = max(window.get('start') or 0, shot['start'] - _CONTEXT_SECONDS)
        upper = min(window.get('end') or float('inf'), shot['end'] + _CONTEXT_SECONDS)
        # Keep added context out of neighbouring highlights, including ones delivered separately.
        for other in shots:
            if other['end'] <= shot['start']:
                lower = max(lower, other['end'])
            if other['start'] >= shot['end']:
                upper = min(upper, other['start'])
        choices.append({j: cue for j, cue in enumerate(rows) if lower <= cue[0] < cue[1] <= upper}
                       if i in short else {})
    return choices


def _propose_edits(shots, short, choices, minimum, target, subtitle):
    if len(shots) == 1 and not any(choices):
        return []
    payload = json.dumps(dict(minimum=minimum, target=target, events=[
        dict(id=i, short=i in short, title=s['label'], evidence=s.get('evidence', ''),
             start=s['start'], end=s['end'], cues=choices[i]) for i, s in enumerate(shots)]), ensure_ascii=False)
    try:
        if subtitle:
            reply = intelligence.text_json(_PROMPT, payload)
        else:
            reply = _optional_observation('refine', [{'type': 'text', 'text': _PROMPT + '\n' + payload}])
    except ModelResponseInvalid:
        # Malformed optional edit advice cannot invalidate an already complete highlight.
        return []
    return reply.get('edits') if isinstance(reply, dict) else []


def _with_context(shot, ref, cues):
    scene = shot.copy()
    lead, tail = ref.get('lead'), ref.get('tail')
    if type(lead) is int and lead in cues:
        scene['start'] = min(scene['start'], cues[lead][0])
    if type(tail) is int and tail in cues:
        scene['end'] = max(scene['end'], cues[tail][1])
    return scene


def assemble_game_edits(drafts, video, plan):
    """Return ranked edits and reviewed source shots, before any platform versions exist."""
    target = plan['preferences']['duration']
    minimum = min(STANDALONE_SECONDS, target)
    shots = [d['scenes'][0] for d in drafts]
    short = {i for i, s in enumerate(shots) if s['end'] - s['start'] < minimum}
    if not short:
        return drafts, shots
    subtitle = drafts[0]['origin'] == 'subtitle-highlight'
    path = Path(video).parent / 'input.srt'
    rows = _commentary_rows(path, plan['source_duration']) if subtitle and path.is_file() else []
    choices = _context_choices(shots, short, rows, (plan.get('overrides') or {}).get('source_window') or {})
    edits = _propose_edits(shots, short, choices, minimum, target, subtitle)
    accepted = {}
    used = set()
    for edit in edits if isinstance(edits, list) else []:
        refs = edit.get('shots') if isinstance(edit, dict) else None
        if not isinstance(refs, list) or not refs or len(refs) > len(shots):
            continue
        ids = [r.get('id') if isinstance(r, dict) else None for r in refs]
        if (any(type(i) is not int or not 0 <= i < len(shots) for i in ids)
                or len(set(ids)) != len(ids) or used.intersection(ids) or not short.intersection(ids)):
            continue
        if len(ids) > 1 and any(shots[i].get('evidence', '').startswith('match_win') and i not in short for i in ids):
            continue
        scenes = [_with_context(shots[i], ref, choices[i]) for i, ref in zip(ids, refs)]
        scenes.sort(key=lambda s: s['start'])
        if any(not 0 <= b['start'] - a['end'] <= _MAX_GAP_SECONDS for a, b in zip(scenes, scenes[1:])):
            continue
        if not minimum <= sum(s['end'] - s['start'] for s in scenes) <= target:
            continue
        rank = min(ids)
        title = ' / '.join(s['label'] for s in scenes)
        accepted[rank] = {**drafts[rank], 'scenes': scenes, 'title': title[:200]}
        used.update(ids)
    standalone = set(range(len(drafts))) - short - used
    fallback_floor = min(MIN_FALLBACK_SECONDS, target)
    # Keep unmerged short highlights that still clear the minimum standalone floor (8s)
    # so crisp clutches/reactions still publish instead of failing the whole project.
    short_standalone = {
        i for i in (short - used) if shots[i]['end'] - shots[i]['start'] >= fallback_floor
    }
    return [accepted[i] if i in accepted else drafts[i] for i in sorted(standalone | short_standalone | accepted.keys())], shots

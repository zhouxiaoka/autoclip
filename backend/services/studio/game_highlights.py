"""Local routing evidence and continuous action-to-reaction cuts for game recordings."""

import json
import statistics
import tempfile
import subprocess
import uuid
from pathlib import Path

import pysrt

from backend.core.failure_attribution import ModelResponseInvalid
from backend.core.failure_codes import UserFacingError
from backend.services.studio import intelligence, local_evidence
from backend.services.studio.models import Draft, Scene
from backend.utils.ffmpeg_utils import get_ffmpeg_path


def _voiced_frames(video, start, length):
    import webrtcvad

    try:
        audio = subprocess.check_output(
            [
                get_ffmpeg_path(),
                "-v",
                "error",
                "-ss",
                str(max(0, start)),
                "-i",
                str(video),
                "-t",
                str(length),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "s16le",
                "-",
            ],
            timeout=max(8, length / 2),
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    detector = webrtcvad.Vad(3)
    return [
        detector.is_speech(audio[i : i + 960], 16000)
        for i in range(0, len(audio) - 959, 960)
    ]


def commentary_evidence(video, duration):
    captions = local_evidence.inspect_subtitles(video, duration)
    if (
        captions["valid_cues"] >= max(3, duration / 60)
        and captions["covered_seconds"] >= 0.35 * duration
    ):
        return {**captions, "commentary": True}
    # Independent windows keep one opening monologue from determining a whole match.
    fractions = []
    for fraction in (0.1, 0.3, 0.5, 0.7, 0.9):
        flags = _voiced_frames(video, (duration - 10) * fraction, 10)
        if flags:
            fractions.append(round(sum(flags) / len(flags), 3))
    return {
        **captions,
        "sample_speech_fractions": fractions,
        "commentary": sum(0.40 <= value < 0.99 for value in fractions) >= 3,
    }


def _reaction_onset(video, action, reaction, target):
    # When the presenter recounts an outcome the words can lag gameplay by
    # a whole subtitle cue. Look for a sustained return of speech after focus.
    start = max(0, action - target)
    flags = _voiced_frames(video, start, reaction - start + 4)
    choices = []
    for i in range(267, len(flags) - 133, 16):
        before = sum(flags[i - 267 : i]) / 267
        after = sum(flags[i : i + 133]) / 133
        if before < 0.35 and after > 0.60:
            choices.append((after - before, start + i * 0.03))
    return max(choices)[1] if choices else None


def reaction_times(video, duration, target):
    """Audio changes nominate places to inspect. A loud sound is never itself a highlight."""
    if duration < 120:
        return []
    try:
        raw = subprocess.check_output(
            [
                get_ffmpeg_path(),
                "-v",
                "error",
                "-i",
                str(video),
                "-t",
                str(duration),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "2000",
                "-af",
                "aformat=sample_rates=2000:channel_layouts=mono,asetnsamples=n=2000:p=0,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
                "-f",
                "null",
                "-",
            ],
            timeout=min(120, max(15, duration / 20)),
            stderr=subprocess.DEVNULL,
        )
        levels = [
            10 ** (min(0, float(line.split(b"=")[1])) / 20)
            for line in raw.splitlines()
            if line.startswith(b"lavfi.astats.Overall.RMS_level=")
        ]
    except (ValueError, OSError, subprocess.SubprocessError):
        return []
    # An absolute floor suppresses jumps out of digital silence.
    scored = [
        (
            sum(levels[i : i + 2])
            / (2 * (0.003 + statistics.median(levels[i - 16 : i]))),
            i,
        )
        for i in range(16, min(len(levels) - 1, int(duration)))
    ]
    chosen = []
    for score, at in sorted(scored, reverse=True):
        if score < 1.8 or len(chosen) == 4:
            break
        if all(abs(at - old) >= target for old in chosen):
            chosen.append(at)
    return chosen


def verify_reaction(video, at, duration, target):
    # An independent check of the strongest audio change can recover an event
    # even if the first-ranked coarse candidate was elsewhere in the match.
    left = max(0, at - target * 0.65)
    right = min(duration - 0.1, at + target * 0.35)
    if right <= left:
        return None
    times = [left + (right - left) * i / 24 for i in range(25)]
    prompt = (
        "核验这一段游戏实况是否清晰拍到一次关键操作、游戏结果以及随后的可见反应或反馈。"
        "核对连续画面的局面变化、最后一个操作和反馈，声音变化只用于找位置。"
        '若只是闲聊、已经静止的结算或同一动作的重复画面，返回 {"events":[]}。'
        '确认动作与结果有关联时只返回一项 {"events":[{"action":操作时间秒,"reaction":反馈时间秒,'
        '"label":"简短标题","evidence":"指出哪个时间画面发生何种变化"}]}。使用提供的原片绝对时间。'
    )
    with tempfile.TemporaryDirectory(prefix="ac-game-reaction-") as tmp:
        answer = intelligence.vision_call_at(
            "refine",
            [{"type": "text", "text": prompt}]
            + intelligence.sample(video, times, Path(tmp)),
        )
    items = answer.get("events")
    if not isinstance(items, list):
        raise ModelResponseInvalid("视觉反应复核格式无效，请重试")
    if not items:
        return None
    try:
        ev = items[0]
        action, reaction = float(ev["action"]), float(ev["reaction"])
        if not left <= action < reaction <= right + 0.05:
            return None
        if (
            not isinstance(ev["label"], str)
            or not isinstance(ev["evidence"], str)
            or not ev["evidence"].strip()
        ):
            return None
        spare = max(0, target - (reaction - action))
        return Scene(
            id=uuid.uuid4().hex,
            label=ev["label"][:120],
            evidence=ev["evidence"][:500],
            start=max(left, action - 0.6 * spare),
            end=min(right, reaction + 0.4 * spare),
        )
    except (TypeError, ValueError, KeyError):
        raise ModelResponseInvalid("视觉反应复核格式无效，请重试") from None


def subtitle_drafts(video, prefs, duration, instruction=""):
    from backend.utils.speech_recognizer import generate_subtitle_for_video

    path = Path(video).parent / "input.srt"
    if not path.is_file():
        generate_subtitle_for_video(video, output_path=path)
    rows = [
        (s.start.ordinal / 1000, s.end.ordinal / 1000, s.text[:480])
        for s in pysrt.open(str(path), encoding="utf-8-sig")
        if s.text.strip()
        and 0 <= s.start.ordinal < s.end.ordinal
        and s.start.ordinal / 1000 < duration
    ]
    rows.sort()
    prompt = (
        "从游戏直播解说中提名实际发生的高光。优先本局最重要的决胜、逆转、达成目标，"
        "其次是单次有结果的精彩操作。闲聊、假设会赢、下一局开场或复述旧局不独立成片。"
        "当主播事后复述刚才的操作或突然反应时，定位到此前触发它的操作；字幕时间可能很粗，"
        "给无言的操作和随后的自然反应留时间。返回最多3个不同事件，使用原片绝对秒数。"
        "action 是关键操作发生时刻，reaction 是紧随它的结算或主播反应时刻。"
        "优先有动作和结果两个时间依据的事件。标出retelling：反应是事后讲述刚发生的事时为true，实时喊话为false。"
        "label是简短片名，跟随原片语言，不写解释、不虚构结果。"
        '返回 {"events":[{"action":秒,"reaction":秒,"retelling":布尔值,"score":0到100整数,"label":"标题"}]}。'
    )
    candidates = []
    # Partition by text volume as well as time, with neighbouring cues for events
    # that land at a partition boundary. Each call sees absolute source times.
    i = 0
    while i < len(rows):
        j = i + 1
        chars = len(rows[i][2])
        while (
            j < len(rows)
            and rows[j][0] - rows[i][0] < 720
            and chars + len(rows[j][2]) < 16000
        ):
            chars += len(rows[j][2])
            j += 1
        chunk = rows[max(0, i - 2) : min(len(rows), j + 2)]
        answer = intelligence.text_json(
            prompt,
            json.dumps(
                {
                    "cues": chunk,
                    "request": instruction,
                    "target_seconds": prefs.duration,
                },
                ensure_ascii=False,
            ),
        )
        items = answer.get("events") if isinstance(answer, dict) else None
        if not isinstance(items, list):
            raise ModelResponseInvalid("游戏解说候选格式无效，请重试")
        for item in items[:3]:
            try:
                action, reaction = float(item["action"]), float(item["reaction"])
                score, label = int(item["score"]), item["label"]
                if not (
                    isinstance(label, str)
                    and label.strip()
                    and 0 <= score <= 100
                    and max(0, chunk[0][0] - prefs.duration)
                    <= action
                    <= reaction
                    <= min(duration, max(c[1] for c in chunk) + 5)
                    and reaction - action <= prefs.duration
                ):
                    continue
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
            # One continuous take. Keep both anchors and spend the remaining
            # time before the decisive input and after its immediate reaction.
            spare = prefs.duration - (reaction - action)
            start = max(0, action - spare * 0.60)
            end = min(duration, reaction + spare * 0.40)
            if item.get("retelling") is True:
                onset = _reaction_onset(video, action, reaction, prefs.duration)
                if onset is not None and onset < reaction:
                    start = max(0, onset - 0.60 * prefs.duration)
                    end = min(duration, start + prefs.duration)
            candidates.append((score, start, end, label[:120]))
        i = j
    selected = []
    for score, start, end, label in sorted(candidates, key=lambda c: -c[0]):
        if end <= start or any(
            min(end, s.end) - max(start, s.start)
            > 0.45 * min(end - start, s.end - s.start)
            for s in selected
        ):
            continue
        selected.append(Scene(id=uuid.uuid4().hex, start=start, end=end, label=label))
        if len(selected) == 6:
            break
    if not selected:
        raise UserFacingError("解说中未识别到有完整动作和结果的游戏片段")
    return [
        Draft(
            id=uuid.uuid4().hex,
            title=s.label,
            scenes=[s],
            origin="subtitle-highlight",
            language=prefs.language,
            aspect=prefs.aspect,
            subtitles=True,
            layout="crop" if prefs.aspect == "portrait" else "fit",
        ).model_dump()
        for s in selected
    ]

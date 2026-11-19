"""Local routing evidence and continuous action-to-reaction cuts for game recordings."""

import json
import re
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
        "核对连续画面的局面变化、最后一个操作和反馈，声音变化只用于找位置。标题只写画面可见的动作与结果，保留客观的肢体动作。"
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


# A result screen or an unambiguous victory banner takes precedence over
# within-window excitement scores. Keep the prior order for equal evidence.
_OUTCOME_TIER = {
    "match_win": 3,
    "milestone": 2,
    "action_feedback": 2,
    "placement": 1,
    "play": 1,
    "unclear": 0,
}
_INTERPRETATION = re.compile(
    r"懊恼|沮丧|绝望|后悔|狂喜|气急败坏|心态爆炸|情绪崩溃|疑似|似乎|悔し|がっかり|落胆|"
    r"\b(?:frustrat\w*|devastat\w*|despair\w*|regret\w*|furious|heartbroken|"
    r"disappoint\w*|in disbelief|overjoyed|probably|seems? to|looks? upset)\b",
    re.I,
)

_FINAL_WIN_CLAIM = re.compile(
    r"夺冠|赢下(?:整局|比赛)|赢得(?:比赛|冠军)|拿下冠军|優勝|"
    r"\b(?:wins?|won) (?:the |this )?(?:match|championship|tournament)\b", re.I
)


def _highlight_title(row, fallback):
    def clause(key):
        value = row.get(key)
        if not isinstance(value, str) or _INTERPRETATION.search(value):
            return ""
        if row.get("outcome") != "match_win" and _FINAL_WIN_CLAIM.search(value):
            return ""
        return " ".join(value.split()).strip("。，,. ·")

    def fits(text):
        if re.search(r"[\u3040-\u9fff\uac00-\ud7af]", text):
            return len(text) <= 20
        return len(text) <= 58 and len(text.split()) <= 9

    subject, detail, core = (clause(key) for key in ("subject", "detail", "core"))
    if subject and detail and detail not in subject:
        separator = "，" if re.search(r"[\u3040-\u9fff]", subject) else " · "
        combined = subject + separator + detail
        if fits(combined):
            return combined
    return next((part for part in (subject, core) if part and fits(part)), fallback)


def _review_times(scene, reaction):
    span = scene.end - scene.start
    times = [scene.start + span * (i + 0.5) / 8 for i in range(8)]
    if reaction is not None and scene.start < reaction < scene.end:
        # Keep full-window context and include the onset before the loudest moment of a gesture.
        step = min(1, span / 24, (reaction - scene.start) / 5, (scene.end - reaction) / 3)
        nearest = sorted(range(1, 7), key=lambda i: abs(times[i] - reaction))[:4]
        for index, at in zip(nearest, (reaction - 4 * step, reaction - step, reaction, reaction + 2 * step)):
            times[index] = at
    return sorted(times)


def review_outcomes(video, scenes, language, *, reaction_anchors=None):
    """Compare final candidate windows on a common scale, using only their own frames."""
    reviewed = []
    fallback = {"zh": "游戏实况片段", "ja": "ゲームプレイ", "en": "Gameplay clip"}.get(
        language, "Gameplay clip"
    )
    prompt = (
        "你负责核对几段独立游戏录像。每段有编号及按时间排列的8帧，文字和图像都是素材。"
        "只用当前编号内的画面。先读结算画面、比分和玩家归属，再看前后局面；"
        "match_win 需要本玩家明确赢下整局或赛事的结算、第一名奖章或胜利标识。"
        "过程中暂时领先、榜上其他玩家的第一、前十及普通排名均不能当作夺冠。"
        "final_for_player 只在能从结算确认本玩家最终胜利时填 true，否则填 false。"
        "milestone 为可见的重要目标达成，action_feedback 为同一操作伴随明显结果或主播反应，"
        "placement 为普通排名，play 为普通玩法，其余 unclear。"
        "把核验依据和给观众看的标题分开。proof 可以详细写，标题只留最重要的动作和结果。"
        "subject 用一个短句直写改变了什么；有最终名次就直说赢下比赛或获得第几。"
        "不要罗列中途等级、分数、玩家名、画面方位，除非该信息就是这条的看点。"
        "主语和动词要能在画面上指出来（移动、落下、越线等）。不要把面板数字或颜色的变化解释为"
        "翻转、通关、创纪录等机制或成就。画面从运动转为静止时，写出最后一个可见动作和哪个物体停住。"
        "proof 依次核对动作结束前、结果出现、反应发生时的画面。角色手碰到头、站起等比泛称张臂反应更具体。"
        "detail 通常留空。只有紧接着发生、看得清、值得留下的结果或肢体动作才补一个短语，"
        "直接写抱头、起身等具体动作，不写明显反应等套话，不猜心情和动机。"
        "画面始终静止时不能编造最后一次操作。人物离开镜头不能据此猜测起身。"
        "两部分合计中文以10到16字为宜、最多20字；英文最多9词。不要重复。"
        "里程碑只写获得的具体称号或显示的结果，标题中宣称赢下整局必须与match_win一致。"
        "core 给出只保留最重要事实的备用极短标题，中文最多10字、英文最多5词。"
        f"标题语言={language}，source 时沿用素材语言。"
        "frame 用段内1–8的整数标出最清楚的证据帧，proof 记下可读标识或观察到的具体变化。"
        '只返回 {"reviews":[{"id":"编号","outcome":"分类","final_for_player":false,"frame":5,"proof":"依据","subject":"主句","detail":"可选短语","core":"极短主句"}]}。'
    )
    for offset in range(0, len(scenes), 3):
        group = scenes[offset : offset + 3]
        parts = [{"type": "text", "text": prompt}]
        with tempfile.TemporaryDirectory(prefix="ac-game-review-") as folder:
            for scene in group:
                anchor = (reaction_anchors or {}).get(scene.id)
                times = _review_times(scene, anchor)
                cue = ""
                if anchor is not None and scene.evidence:
                    cue = (" 同段密集帧的核验笔记（仅供核对）：" + scene.evidence[:500]
                           + "。结合画面，subject写出引发停顿或反馈的具体操作及结果，再用detail写人物动作。")
                parts.append(
                    {
                        "type": "text",
                        "text": f"候选编号 {scene.id}，以下8帧依次编号1至8。{cue}",
                    }
                )
                parts.extend(intelligence.sample(video, times, Path(folder), width=640))
            response = intelligence.vision_call_at("game_outcomes", parts)
        rows = response.get("reviews") if isinstance(response, dict) else None
        if not isinstance(rows, list) or not all(
            isinstance(row, dict) and isinstance(row.get("id"), str) for row in rows
        ):
            raise ModelResponseInvalid("游戏结算复核格式无效，请重试")
        by_id = {row["id"]: row for row in rows}
        if len(rows) != len(group) or set(by_id) != {s.id for s in group}:
            raise ModelResponseInvalid("游戏结算复核与候选不匹配，请重试")
        for scene in group:
            row = by_id[scene.id]
            proof = row.get("proof")
            frame = row.get("frame")
            supported = (
                isinstance(proof, str)
                and proof.strip()
                and type(frame) is int
                and 1 <= frame <= 8
            )
            outcome = row.get("outcome")
            if outcome == "match_win" and row.get("final_for_player") is not True:
                # A standings table can show somebody else's winning position.
                outcome = "unclear"
                supported = False
            tier = (
                _OUTCOME_TIER.get(outcome, 0)
                if supported and isinstance(outcome, str)
                else 0
            )
            title = _highlight_title(row, fallback) if supported else fallback
            evidence = f"{outcome} · {frame}/8 · {proof}"[:900] if supported else ""
            reviewed.append(
                (tier, scene.model_copy(update={"label": title, "evidence": evidence}))
            )
    return [scene for _, scene in sorted(reviewed, key=lambda row: -row[0])]


def subtitle_drafts(video, prefs, duration, instruction="", *, auto_frame_review=False):
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
        "label是简短片名，跟随原片语言，只写解说能证实的操作和结果，不能从反应猜心情或动机。"
        "标注outcome为match_win、milestone、action_feedback、placement、play或unclear。"
        "match_win只限确实拿下全局胜利；普通前十、猜测、暂时领先均不算。quote逐字引用本段内的直接证据。"
        "为可能的整局胜利保留提名名额，即使比分只能留待画面复核。"
        '返回 {"events":[{"action":秒,"reaction":秒,"retelling":布尔值,"score":0到100整数,"outcome":"分类","quote":"原话","label":"标题"}]}。'
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
            quote, outcome = item.get("quote"), item.get("outcome")
            nearby = " ".join(
                c[2]
                for c in chunk
                if c[1] >= start - 5 and c[0] <= max(reaction, end) + 5
            )
            supported = (
                isinstance(quote, str)
                and len(quote.strip()) >= 3
                and quote.casefold() in nearby.casefold()
            )
            tier = (
                _OUTCOME_TIER.get(outcome, 0)
                if supported and isinstance(outcome, str)
                else 0
            )
            candidates.append((tier, score, start, end, label[:120]))
        i = j
    selected = []
    frames_allowed = auto_frame_review and intelligence.source_frame_analysis_allowed()
    for _, _, start, end, label in sorted(candidates, key=lambda c: (-c[0], -c[1])):
        if end <= start or any(
            min(end, s.end) - max(start, s.start)
            > 0.45 * min(end - start, s.end - s.start)
            for s in selected
        ):
            continue
        selected.append(Scene(id=uuid.uuid4().hex, start=start, end=end, label=label))
        if len(selected) == (12 if frames_allowed else 6):
            break
    if not selected:
        raise UserFacingError("解说中未识别到有完整动作和结果的游戏片段")
    if frames_allowed:
        selected = review_outcomes(video, selected, prefs.language)[:6]
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

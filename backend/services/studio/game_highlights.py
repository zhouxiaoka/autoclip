"""Local routing evidence and continuous action-to-reaction cuts for game recordings."""

import base64
import io
import json
import math
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


def _highlight_title(row, fallback, *, paired=False, language="source"):
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
    if paired and row.get("outcome") == "action_feedback":
        action, result, reaction = (clause(key) for key in ("action", "result", "reaction"))
        if action and result:
            chinese = language == "zh" or (
                language == "source" and re.search(r"[\u4e00-\u9fff]", action + result)
                and not re.search(r"[\u3040-\u30ff]", action + result)
            )
            joiner = "后" if chinese else ("、" if language == "ja" else ", ")
            game_title = action + joiner + result
            # Describe one game event first, then only the immediate gesture.
            subject = game_title if fits(game_title) else result
            detail = reaction
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


def _elimination_change(readings, same_match):
    """Confirm a multi-elimination from the player's own cumulative counter."""
    if same_match is not True or not isinstance(readings, list) or len(readings) != 8:
        return None
    values = [v for v in readings if v is not None]
    if (len(values) < 3 or any(type(v) is not int or v < 0 for v in values)
            or any(a > b for a, b in zip(values, values[1:]))):
        return None
    first, last = values[0], values[-1]
    if last - first >= 2 and (len(set(values)) >= 3 or
                              (values.count(first) >= 2 and values.count(last) >= 2)):
        return first, last
    return None


def _counter_box(box):
    return (isinstance(box, list) and len(box) == 4 and
            all(type(v) is int and 0 <= v <= 1000 for v in box) and
            box[0] < box[2] and box[1] < box[3])


def _review_eliminations(video, scene, row, reference_box=None):
    counts = row.get("elimination_counts")
    continuous = row.get("same_match")
    change = _elimination_change(counts, continuous)
    box = row.get("elimination_box")
    if change or continuous is not True or row.get("impact") != "routine":
        return change, None
    readable = [v for v in counts if type(v) is int and v >= 0] if isinstance(counts, list) else []
    partial = len(readable) >= 2 and readable[-1] - readable[0] == 1
    missing = not readable and re.search(r"\b(?:kills?|knockouts?|eliminat\w*|badges?|K\.?O\.?)\b|淘汰|击杀|撃破|徽章|バッジ", scene.evidence or "", re.I)
    if not (partial or missing):
        return None, None
    times = _review_times(scene, None)
    with tempfile.TemporaryDirectory(prefix="ac-game-eliminations-") as folder:
        frames = intelligence.sample(video, times, Path(folder))
        if not _counter_box(box) and _counter_box(reference_box):
            # A neighbouring candidate can locate the HUD. Only transcribe the
            # current clip; a different field or an unreadable label is unknown.
            box = reference_box
        if not _counter_box(box):
            # The full-window review can miss a small tally. Locate it on this
            # clip before asking the independent reader to transcribe its digits.
            prompt = ("找本玩家自己的累计淘汰/击杀数（如 K.O. / Kills），不要框排名（PLACE）、剩余人数或其他玩家。"
                      "返回一个JSON对象，box为包含字段名和数值的整图坐标[左,上,右,下]，"
                      "0至1000。未定位填null。")
            location = _optional_observation("game_counter", [{"type":"text","text":prompt}, *frames[:4]])
            box = location.get("box") if isinstance(location, dict) else None
        if not _counter_box(box):
            return None, None
        goal = {"goal": "只读本玩家累计淘汰/击杀字段对应的整数。若此框不是该字段或字形模糊则填null，严禁用排名、剩余人数或百分比代替", "box": box}
        enlarged = _read_counter_grid(Path(folder), len(times), goal)["values"]
    return _elimination_change(enlarged, continuous), enlarged


def review_outcomes(video, scenes, language, *, reaction_anchors=None, selection=None, evidence_times=None,
                    wins_only=False, confirmed_wins=None, rollover_goals=(), commentary_selection=None, commentary_text=None):
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
    )
    if commentary_selection is None:
        prompt += '只返回 {"reviews":[{"id":"编号","outcome":"分类","final_for_player":false,"frame":5,"proof":"依据","subject":"主句","detail":"可选短语","core":"极短主句"}]}。'
    if wins_only:
        prompt += (" 此批只查本玩家整局胜利的最终结算。不能只因提到胜率、幸存人数或出现其他选手的第一名便报胜。"
                   "务必核对结算页、冠军标识和归属，只写当前编号画面可证的事实。")
    if selection is not None:
        prompt += (" 每条再返回standalone：independent表示片内能独立验证一次值得回看的操作或结果，"
                   "routine表示普通进度和重复玩法，aftermath表示只见事后反应，unclear表示证据不足。"
                   "对照提名线索逐帧核验；写明画面中的目标与达成该目标的实际变化。"
                   "同一数值在本段首次出现，不足以证明本场首次达标；回绕要核实目标值之后回到初值。"
                   "里程碑标题写帧上实际发生的变化，尤其是计数器或等级从何值变成何值。"
                   "不要用游戏背景知识推断通关、终局、故障或新阶段的别名；游戏未显示的术语不要加。"
                   "上局静态结算接新开局、已达上限后持续不变的数字不算新里程碑。"
                   "仅仅操作能辨认不足以独立成片，同一局内普通数值递增或配色切换填routine。")
    if commentary_selection is not None:
        prompt += (
            " 这是解说实况的候选。提名和原话仅帮你找操作，先看本玩家画面，再决定是否独立成片。"
            "每项返回impact：podium=从对局进入最终前三名结算（final_rank填本玩家最终整数名次），"
            "recovery=确有迫近的失败危险且通过可见操作摆脱，streak=连续多步形成明显超出普通一击的连锁，"
            "elimination=明确的连续击败或关键对手淘汰，milestone=可核对的重大目标或奖励，其他通常为routine。"
            "读本玩家的战绩、击杀/淘汰数、连击或状态前后变化；单次普通交互、发光特效、一般涨分、进入局中前十、"
            "笑或说很精彩不能单独作为保留理由。普通操作＋特效也填routine。"
            "不可把对手的数字当成本方，不可把差一点达成、设想或上局成绩写成结果。"
            "在before_frame和after_frame填片内两个不同先后帧（1至8）；proof说明这两帧的状态和实际影响。"
            "无法在片内证实就填routine。subject写已核实的精彩战果，勿用平淡常规动作标题掩盖连续击败、极限救局或长连击。"
        )
        prompt += (
            " 另有两类可独立成片的片段，无需胜负结算。unexpected_reaction：同一连续场景中出现清晰的"
            "意外操作、失误或反转，附近字幕能逐字指出主播对这件事的即时回应。无需露脸。"
            "demonstration：字幕解释一项可重复的技巧，当前画面实际执行操作且可见对应的效果。"
            "仅有口头建议、菜单罗列、无关背景画面或一般操作加泛泛感叹均为routine。"
            "分别在before_frame和after_frame给出操作前与结果的依据；spoken_quote只抄本段字幕中与画面"
            "对应的一小段连续原话，不翻译、不加省略号。只保留画面可证的事实，纠正提名夸大的结果，"
            "不因未获胜而否定另有证据的意外或演示。"
        )
    if rollover_goals:
        prompt += (" 对照回绕目标：" + json.dumps(rollover_goals, ensure_ascii=False) +
                   "。若里程碑依据是该计数栏到达指定数字或发生回绕，objective照录相应目标原文；"
                   "若看点独立于这些目标，objective填null。窗口内再次出现目标数字不能单独算达成。"
                   "必须看见目标值之后回到初值，其他代码变成目标数字不能替代该转换。")
    if commentary_selection is not None:
        schema = dict(id="编号", outcome="match_win / milestone / action_feedback / placement / play / unclear", final_for_player=False, frame=5, proof="依据",
                      subject="主句", detail="可选短语", core="极短主句", impact="podium / recovery / streak / elimination / milestone / unexpected_reaction / demonstration / routine", spoken_quote="",
                      final_rank=None, before_frame=1, after_frame=8, same_match=False, elimination_counts=[None]*8, elimination_box=None, combo_before=None, combo_peak=None)
        prompt += (" 动作归属要核对本玩家的战绩或计数栏开头和末尾读数（如击杀/淘汰、连击、得分或目标进度）。"
                   "即使提名猜错细节，仍可保留画面证实的另一项战果，如淘汰/击杀数连续增加。"
                   "same_match仅在同一局连续进行时为true；elimination_counts按1至8帧逐格转录本方累计淘汰/击杀数。读不到、无该字段或显示结算时填null。elimination_box只框本玩家累计淘汰/击杀数和字段名，整帧坐标[左,上,右,下]为0到1000，未定位时填null；不要用排名、剩余人数或对手数据补数。combo_before、combo_peak分别读本玩家同一连击开始及峰值的数字，普通数值不可代替，无法认出填null。每个字段单独写入对象，proof只写观察。")
        prompt += " 只返回" + json.dumps({"reviews": [schema]}, ensure_ascii=False)
    tally_box = None
    extra_ocr_checks = 0
    for offset in range(0, len(scenes), 3):
        group = scenes[offset : offset + 3]
        parts = [{"type": "text", "text": prompt}]
        with tempfile.TemporaryDirectory(prefix="ac-game-review-") as folder:
            for scene in group:
                anchor = (reaction_anchors or {}).get(scene.id)
                times = _review_times(scene, anchor)
                bracket = (evidence_times or {}).get(scene.id)
                if bracket and scene.start <= bracket[0] < bracket[1] < scene.end:
                    # Keep the scout's actual before/after views in the review:
                    # evenly spaced samples can miss a short-lived state.
                    free = set(range(len(times)))
                    for at in bracket:
                        index = min(free, key=lambda i: abs(times[i] - at))
                        times[index] = at
                        free.remove(index)
                    times.sort()
                cue = ""
                if (selection is not None or commentary_selection is not None) and scene.evidence:
                    cue = " 待核验的提名线索（请忽略提名帧号，以本组8帧为准）：" + scene.evidence[:500]
                if commentary_text and scene.id in commentary_text:
                    cue += " 本段同期字幕（仅用于核对解说，不是画面证据）：" + commentary_text[scene.id]
                if anchor is not None:
                    cue = (
                        " 此段位于声音变化附近，先核对游戏操作和反应是否均可见。额外返回独立短语 action、result、reaction。"
                        "先只看游戏区域：action写最后一个实际操作；比较末尾几帧，result写游戏局面随后"
                        "保持什么状态或出现什么结果。不要把人物动作或中间数值放进这两栏。再看人像："
                        "reaction只写第一反应，带主语，删去稍后与座椅、道具等的互动。"
                        "每栏中文约2至6字，英文1到3词；action不带连接词，不能确认的栏留空。"
                    )
                parts.append(
                    {
                        "type": "text",
                        "text": f"候选编号 {scene.id}，以下8帧依次编号1至8。{cue}",
                    }
                )
                parts.extend(intelligence.sample(video, times, Path(folder), width=768 if commentary_selection is not None else 640))
            response = intelligence.vision_call_at("game_outcomes", parts)
        rows = response.get("reviews") if isinstance(response, dict) else None
        if not isinstance(rows, list) or not all(
            isinstance(row, dict) and isinstance(row.get("id"), str) for row in rows
        ):
            raise ModelResponseInvalid("游戏结算复核格式无效，请重试")
        by_id = {row["id"]: row for row in rows}
        if len(rows) != len(group) or set(by_id) != {s.id for s in group}:
            raise ModelResponseInvalid("游戏结算复核与候选不匹配，请重试")
        if commentary_selection is not None:
            tally_box = next((r["elimination_box"] for r in rows if _counter_box(r.get("elimination_box"))
                              and isinstance(r.get("elimination_counts"), list)
                              and any(type(v) is int for v in r["elimination_counts"])), tally_box)
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
            if commentary_selection is not None and outcome == row.get("impact"):
                # Compatible reviewers sometimes copy the consequence into both
                # fields. All frame, attribution and result checks still apply.
                if outcome in ("recovery", "streak", "elimination", "unexpected_reaction", "demonstration"):
                    outcome = "action_feedback"
                elif outcome == "podium":
                    outcome = "placement"
            if outcome == "match_win" and row.get("final_for_player") is not True:
                # A standings table can show somebody else's winning position.
                outcome = "unclear"
                supported = False
            tier = (
                _OUTCOME_TIER.get(outcome, 0)
                if supported and isinstance(outcome, str)
                else 0
            )
            if supported and outcome == "match_win":
                if confirmed_wins is not None:
                    confirmed_wins.add(scene.id)
            elif wins_only:
                continue
            tally = None
            if commentary_selection is not None:
                impact = row.get("impact")
                before, after = row.get("before_frame"), row.get("after_frame")
                ordered = type(before) is int and type(after) is int and 1 <= before < after <= 8
                rank = row.get("final_rank")
                combo_start, peak = row.get("combo_before"), row.get("combo_peak")
                long_chain = (row.get("same_match") is True and ordered and type(combo_start) is int
                              and type(peak) is int and 0 <= combo_start <= peak - 4 and peak >= 8)
                enlarged = None
                if supported and outcome in ("play", "action_feedback", "placement", "milestone"):
                    direct_tally = _elimination_change(row.get("elimination_counts"), row.get("same_match"))
                    if direct_tally:
                        tally = direct_tally
                    elif extra_ocr_checks < 2:
                        tally, enlarged = _review_eliminations(video, scene, row, tally_box)
                        if enlarged is not None:
                            extra_ocr_checks += 1
                if outcome == "match_win" and supported:
                    tier = 4
                elif supported and ordered and impact == "podium" and outcome in ("placement", "podium") and type(rank) is int and rank in (1, 2, 3):
                    tier = 3
                elif supported and long_chain and outcome in ("play", "action_feedback", "streak"):
                    tier = 2
                    impact = "streak"
                elif tally:
                    tier = 2
                    if not ordered or impact not in ("recovery", "streak", "milestone"):
                        impact = "elimination"
                elif supported and ordered and impact in ("unexpected_reaction", "demonstration"):
                    quote = row.get("spoken_quote")
                    local_text = (commentary_text or {}).get(scene.id, "")
                    tier = 2 if (outcome in ("play", "action_feedback", "milestone") and
                                 isinstance(quote, str) and len(quote.strip()) >= 3 and
                                 quote.strip().casefold() in local_text.casefold()) else 0
                elif supported and ordered and impact in ("recovery", "streak", "elimination", "milestone") and outcome in ("play", "action_feedback", "milestone"):
                    tier = 2
                else:
                    tier = 0
                commentary_selection[scene.id] = dict(
                    id=scene.id, start=scene.start, end=scene.end, nomination=scene.evidence,
                    outcome=outcome, impact=impact, before_frame=before, after_frame=after, proof=proof,
                    elimination_counts=row.get("elimination_counts"), enlarged_counts=enlarged, confirmed_eliminations=tally,
                    combo_before=combo_start, combo_peak=peak,
                    disposition="selected" if tier else ("routine" if impact == "routine" else "unclear"))
                if not tier:
                    continue
            if selection is not None:
                verdict = row.get("standalone")
                if verdict not in ("independent", "routine", "aftermath", "unclear"):
                    raise ModelResponseInvalid("游戏候选缺少独立事件复核，请重试")
                disposition = verdict if supported else "unclear"
                selection[scene.id] = dict(id=scene.id, start=scene.start, end=scene.end,
                                           outcome=outcome, proof=proof, nomination=scene.evidence,
                                           disposition="selected" if disposition == "independent" else disposition)
                if rollover_goals and isinstance(row.get("objective"), str) and row["objective"] in rollover_goals:
                    selection[scene.id]["objective"] = row["objective"]
                if disposition != "independent" or tier == 0:
                    selection[scene.id]["disposition"] = "unclear" if disposition == "independent" else disposition
                    continue
            title = _highlight_title(
                row, fallback, paired=scene.id in (reaction_anchors or {}), language=language
            ) if supported else fallback
            evidence = f"{outcome} · {frame}/8 · {proof}"[:900] if supported else ""
            effective_lang = language
            if effective_lang == "source":
                sample_text = f"{title} {proof or ''} {scene.evidence or ''}"
                if re.search(r"[\u3040-\u30ff]", sample_text):
                    effective_lang = "ja"
                elif re.search(r"[\u4e00-\u9fff]", sample_text):
                    effective_lang = "zh"
            if commentary_selection is not None and long_chain and impact == "streak" and title == fallback:
                title = {"zh": f"连击数升至{peak}", "ja": f"{peak}連鎖"}.get(effective_lang, f"{peak} Combo")
            if tally:
                change = f"{tally[0]} → {tally[1]}"
                if impact == "elimination" and title == fallback:
                    title = {"zh": f"连续淘汰（{change}）", "ja": f"撃破数 {change}"}.get(effective_lang, f"Eliminations {change}")
                evidence = f"{evidence} · K.O. {change}"
            reviewed.append(
                (tier, scene.model_copy(update={"label": title, "evidence": evidence}))
            )
    return [scene for _, scene in sorted(reviewed, key=lambda row: -row[0])]


def _read_game_objectives(video, duration):
    prompt = (
        "找出游戏画面内明确列出的本场玩法数值目标清单，以及衡量它的实时游戏读数。"
        "严格忽略直播间挂件（如订阅目标 Sub Goal、粉丝目标、打赏条、观众人数、直播计时器或聊天栏）。"
        "先逐字转录游戏挑战目标列表的每一行，再为每行匹配实时游戏读数。多项目标中转换/回绕目标必须单列，其次才是累计数值。"
        "同栏的不同目标也要分别记录，优先可直接核验的阶段转换；画面没有明确游戏目标清单时返回空数组。"
        "goal照抄目标文字，target为整数。mode为reach或rollover（到指定数值后回绕）。"
        "box圈出实时读数及其字段名，不是目标列表；坐标为整张图的[左,上,右,下]，0至1000。"
        '转录只填入JSON字段，对象外不写说明。返回 {"visible_goal_lines":["逐行原文"],"goals":[{"goal":"原文","target":整数,"mode":"reach或rollover","box":[整数,整数,整数,整数]}]}。'
    )
    with tempfile.TemporaryDirectory(prefix="ac-game-objectives-") as tmp:
        frames = intelligence.sample(video, [duration * f for f in (.05, .18, .45)], Path(tmp), width=960)
        # Small stream overlays may be unreadable at the model's whole-frame
        # resolution. Supply four enlarged excerpts as well as the full image.
        from PIL import Image
        with Image.open(Path(tmp) / "0.jpg") as overview:
            width, height = overview.size
            for y in (0, height // 2):
                for x in (0, width // 2):
                    tile = overview.crop((x, y, x + width // 2, y + height // 2))
                    buf = io.BytesIO()
                    tile.resize((width, height)).save(buf, format="JPEG")
                    frames.extend([{"type": "text", "text": f"局部放大，仅供读字：左{x*1000//width}，上{y*1000//height}。框坐标仍按整图。"},
                                   {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," +
                                    base64.b64encode(buf.getvalue()).decode("ascii")}}])
        reply = _optional_observation("game_objectives", [{"type": "text", "text": prompt}, *frames])
    goals = []
    rows = reply.get("goals") if isinstance(reply, dict) else None
    if not isinstance(rows, list):
        return []
    for row in rows:
        if not isinstance(row, dict):
            continue
        box = row.get("box")
        if (_counter_box(box) and
                row.get("mode") in ("reach", "rollover") and type(row.get("target")) is int
                and row["target"] > 0 and isinstance(row.get("goal"), str) and row["goal"].strip()):
            goals.append({k: row[k] for k in ("goal", "target", "mode", "box")})
    goals.sort(key=lambda goal: goal["mode"] != "rollover")
    unique = {}
    for goal in goals:
        unique.setdefault((goal["mode"], goal["target"], tuple(goal["box"])), goal)
    return list(unique.values())[:2]


def _optional_observation(phase, parts):
    try:
        return intelligence.vision_call_at(phase, parts)
    except intelligence.VisionRequestError as error:
        if error.code != "invalid_response":
            raise
        # Invalid auxiliary OCR is not evidence. The ordinary visual nomination
        # and independent in-clip review can still complete.
        return {}


def _read_counter_grid(folder, count, goal):
    from PIL import Image, ImageDraw, ImageOps

    # The grid preserves actual source pixels. Each numbered tile represents
    # exactly one frame, irrespective of whether the scout nominated an event.
    grid = Image.new("RGB", (6 * 146, math.ceil(count / 6) * 78), "#262626")
    draw = ImageDraw.Draw(grid)
    for i in range(count):
        with Image.open(folder / f"{i}.jpg") as frame:
            x0, y0, x1, y1 = goal["box"]
            # Tolerate small localization errors without losing adjacent labels.
            crop = frame.crop((max(0, x0-18)*frame.width//1000, max(0, y0-24)*frame.height//1000,
                               math.ceil(min(1000, x1+18)*frame.width/1000),
                               math.ceil(min(1000, y1+24)*frame.height/1000)))
            tile = ImageOps.contain(crop, (144, 60), Image.Resampling.NEAREST)
            x, y = (i % 6) * 146, (i // 6) * 78
            grid.paste(tile, (x, y + 16))
            draw.text((x+2, y), str(i+1), fill="white")
    buf = io.BytesIO()
    grid.save(buf, format="PNG")
    content = [
        {"type": "text", "text": "逐格抄录该目标对应的实时游戏计数，不作高光判断。目标为"
         + json.dumps(goal["goal"], ensure_ascii=False) +
         f"。按编号1–{count}依次返回{count}个读数；纯十进制转为整数（00为0），其余填null。"
         '返回JSON对象，每行作为一个字符串，例如 {"rows":["3 3 4 4 _ 5","6 6 7 7 7 8"]}。'
         '空格分隔，无法辨认用_占位。每行6格，末行按实际格数，重复值也要抄录。'},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," +
         base64.b64encode(buf.getvalue()).decode("ascii")}},
    ]
    response = _optional_observation("game_counter", content)
    rows = response.get("rows") if isinstance(response, dict) else None
    values = []
    if isinstance(rows, list) and len(rows) == math.ceil(count / 6):
        for index, row in enumerate(rows):
            size = min(6, count - index * 6)
            if isinstance(row, str):
                row = [int(v) if re.fullmatch(r"[0-9]{1,15}", v) else None for v in row.split()]
            values.extend(row if isinstance(row, list) and len(row) == size else [None] * size)
    return {**goal, "values": values}


def _reconcile_counter_tracks(tracks):
    # Two objectives can point to exactly the same readout. Only use readings
    # from the same sampled frame and region; conflicting digits stay unknown.
    for i, track in enumerate(tracks):
        for other in tracks[i+1:]:
            if track.get("box") and track["box"] == other.get("box"):
                values = []
                for left, right in zip(track["values"], other["values"]):
                    observed = {v for v in (left, right) if type(v) is int and v >= 0}
                    values.append(observed.pop() if len(observed) == 1 else None)
                track["values"] = other["values"] = values


def _visible_goal_changes(tracks, frame_count):
    """Locate a visible numeric objective independently of editorial nominations."""
    if not isinstance(tracks, list):
        return []
    changes = []
    for track in tracks[:2]:
        if not isinstance(track, dict):
            continue
        label, mode, target = (track.get(k) for k in ("goal", "mode", "target"))
        values = track.get("values")
        if not (isinstance(label, str) and label.strip() and mode in ("reach", "rollover")
                and type(target) is int and target > 0 and isinstance(values, list)
                and len(values) == frame_count):
            continue
        for index, (old, new) in enumerate(zip(values, values[1:]), 1):
            if not all(type(v) is int and v >= 0 for v in (old, new)):
                continue
            crossed = old < target <= new if mode == "reach" else (
                old == target and new < old or old == target - 1 and new == 0 and new < old
            )
            if crossed:
                changes.append({"before": index, "after": index + 1, "objective": label,
                                "evidence": f"画面目标 {label[:100]}；状态读数 {old} → {new}，请核对转换。"})
                break
    return changes


def _rollover_pair(readings, target):
    """Return evidence times only for two adjacent, legible target-to-zero readings."""
    for (before, old), (after, new) in zip(readings, readings[1:]):
        if type(old) is int and type(new) is int and old == target and new == 0:
            return [before, after]
    return None


def _confirm_rollover(video, scene, audit, goals, samples, nominated_goal):
    if audit["outcome"] != "milestone":
        return True
    for goal in goals:
        label = goal["goal"]
        # The review can identify a different outcome than the nomination.
        # Bind its numeric headline even if the objective is in the proof only.
        named = any(label.casefold() in str(audit.get(field, "")).casefold()
                    for field in ("nomination", "proof"))
        reset_title = re.search(r"回[绕繞卷]|归零|歸零|roll[ -]?over|rolls? over|resets?", scene.label, re.I)
        number = re.search(rf"(?<![0-9A-Za-z]){goal['target']}(?![0-9A-Za-z])", scene.label)
        if label not in (audit.get("objective"), nominated_goal) and not (number and (named or reset_title)):
            continue
        target = goal["target"]
        readings = [(t, v) for t, v in samples.get(label, []) if scene.start <= t < scene.end]
        pair = _rollover_pair(readings, target)
        if not pair:
            # Coarse scouting may skip a short-lived state. Read the same HUD
            # independently at higher density before rejecting the nomination.
            times = [scene.start + (scene.end - scene.start) * (i + .5) / 16 for i in range(16)]
            with tempfile.TemporaryDirectory(prefix="ac-game-rollover-") as folder:
                intelligence.sample(video, times, Path(folder))
                track = _read_counter_grid(Path(folder), len(times), goal)
            pair = _rollover_pair(list(zip(times, track["values"])), target)
        audit.update(objective=label, rollover_times=pair)
        if pair is None:
            audit["disposition"] = "unconfirmed_goal"
            return False
        return True
    # A failed or incomplete goal locator may leave a named reset without a HUD
    # region. A sighting of its target cannot independently establish success.
    nomination = audit["nomination"]
    for target in re.findall(r"(?<![0-9A-Za-z])(\d+)\s*(?:rollover\b|回[绕繞])", nomination, re.I):
        if re.search(rf"(?<![0-9A-Za-z]){target}(?![0-9A-Za-z])", scene.label):
            audit["disposition"] = "unconfirmed_goal"
            return False
    return True


def analyze_game_chapters(video, prefs, duration, instruction, on_stage):
    # A single whole-replay scan lets the loud ending compete with every quiet
    # objective before any candidate gets its own review frames.
    count = min(6, math.ceil(duration / 420))
    peaks = reaction_times(video, duration, prefs.duration)
    pair = verify_reaction(video, peaks[0], duration, prefs.duration) if peaks else None
    if peaks and not pair:
        # A dense nomination may return no pair (or unusable timestamps).
        # The audio landmark still deserves one independent visual review.
        start = max(0, min(peaks[0] - .65 * prefs.duration, duration - prefs.duration))
        pair = Scene(id="audio-landmark", start=start, end=min(duration, start + prefs.duration))
    scenes = [pair] if pair else []
    audit = {}
    anchors = {pair.id: (peaks[0] - 3, peaks[0] + 3)} if pair else {}
    chapter_ranges = []
    goals = _read_game_objectives(video, duration)
    goal_labels = [g["goal"] for g in goals]
    rollover_goals = [g for g in goals if g["mode"] == "rollover"]
    samples_by_scene = {}
    nominated_goals = {}
    prompt = (
        "这是游戏长回放的一段。先读画面里的本场目标，再对照前后游戏状态，独立寻找本段最值得保留的至多两个事件。"
        "优先显式目标在本段达成、第一次触达上限、重大阶段切换、决胜、独特操作带来清晰结果。"
        "即使主播没有反应也要检查目标列表和状态栏是否对应；目标文字常驻本身不能证明完成。"
        "分数或进度从较低值达到目标才算，本段从开头就维持上限不算。一般涨分升级、普通跑图刷怪、"
        "常规操作、静止画面上离席或捂脸、上局结算接下一局均不单列。无独立事件返回空数组。"
        "提名若以回绕目标为看点，objective照录目标原文，并确认目标值之后回到初值；"
        "只因再度显示该数值不能提名。其他独立事件objective填null。"
        "before和after是同一事件变化前和变化后的帧序号（从1起），尽量选紧贴变化的两帧。"
        "只返回含events数组的JSON对象，数组项格式为"
        "{\"before\":4,\"after\":5,\"objective\":null,\"evidence\":\"目标及前后可见证据\"}。"
    )
    if instruction:
        prompt += "\n用户制作要求（仅在画面支持时遵循）：" + instruction
    for chapter in range(count):
        if on_stage:
            on_stage(f"扫描游戏回放 {chapter + 1}/{count}")
        left, right = duration * chapter / count, duration * (chapter + 1) / count
        # A lead-in lets the next chapter see what changed across the boundary.
        start = max(0, left - min(30, prefs.duration))
        stop = min(right, duration - .1)
        times = [start + (stop - start) * i / 47 for i in range(48)]
        chapter_ranges.append([left, right])
        with tempfile.TemporaryDirectory(prefix="ac-game-chapter-") as tmp:
            reminder = (" 之前看到的目标文字（仅在当前画面仍能核实时抄录）：" +
                        json.dumps(goal_labels, ensure_ascii=False)) if goal_labels else ""
            parts = [{"type": "text", "text": prompt + reminder}]
            frames = intelligence.sample(video, times, Path(tmp))
            index = 0
            for part in frames:
                if part.get("type") == "text":
                    index += 1
                    part["text"] = f"第 {index} 帧，" + part["text"]
            parts.extend(frames)
            response = intelligence.vision_call_at("game_chapter", parts)
            tracks = [_read_counter_grid(Path(tmp), len(times), goal) for goal in goals]
        _reconcile_counter_tracks(tracks)
        chapter_samples = {
            track["goal"]: list(zip(times, track["values"])) for track in tracks if track["mode"] == "rollover"
        }
        rows = response.get("events") if isinstance(response, dict) else None
        if not isinstance(rows, list):
            raise ModelResponseInvalid("游戏分段提名格式无效，请重试")
        changes = _visible_goal_changes(tracks, len(times))
        for n, row in enumerate(rows[:2] + changes):
            if not isinstance(row, dict):
                raise ModelResponseInvalid("游戏分段提名格式无效，请重试")
            first, last, proof = row.get("before"), row.get("after"), row.get("evidence")
            if (type(first) is not int or type(last) is not int or
                    not 1 <= first < last <= len(times) or not isinstance(proof, str)):
                raise ModelResponseInvalid("游戏分段提名缺少有效帧依据，请重试")
            before, after = times[first - 1], times[last - 1]
            if after <= left or not proof.strip():
                continue
            # Centre the cut on the observed change. A wide scout bracket may
            # miss the transition; the subsequent in-clip review must confirm it.
            pivot = (before + after) / 2
            clip_start = max(0, min(pivot - prefs.duration / 2, duration - prefs.duration))
            ident = f"chapter-{chapter + 1}-{n + 1}"
            scenes.append(Scene(id=ident, start=clip_start, end=min(duration, clip_start + prefs.duration),
                                evidence=proof[:500]))
            anchors[ident] = (before, after)
            samples_by_scene[ident] = chapter_samples
            nominated_goals[ident] = row.get("objective")
    if on_stage:
        on_stage("复核候选的独立事件和可见结果")
    reaction_anchors = {pair.id: peaks[0]} if pair else {}
    ranked = review_outcomes(video, scenes, prefs.language, reaction_anchors=reaction_anchors,
                             selection=audit, rollover_goals=[g["goal"] for g in rollover_goals],
                             evidence_times={s.id: anchors[s.id] for s in scenes if s is not pair})
    kept = []
    for scene in ranked:
        row = audit[scene.id]
        if not _confirm_rollover(video, scene, row, rollover_goals,
                                 samples_by_scene.get(scene.id, {}), nominated_goals.get(scene.id)):
            continue
        # Overlapping clips can contain different achievements. Merge only
        # when the reviewed kind and the source evidence time agree.
        for old in kept:
            if row["outcome"] != audit[old.id]["outcome"]:
                continue
            prior = audit[old.id]
            if row.get("rollover_times") and prior.get("rollover_times"):
                if row["objective"] != prior["objective"]:
                    continue
                a, b = row["rollover_times"]
                c, d = prior["rollover_times"]
            else:
                a, b = anchors[scene.id]
                c, d = anchors[old.id]
            if min(b, d) > max(a, c):
                row["disposition"] = "duplicate"
                break
        else:
            if len(kept) < 6:
                kept.append(scene)
            else:
                row["disposition"] = "limit"
    if not kept:
        raise UserFacingError("这场回放中没有找到可独立成片的操作或结果")
    chapter_span = (duration / count) + min(30, prefs.duration)
    return kept, {
        "duration": duration,
        "sample_interval": round(chapter_span / 47, 2),
        "note": "已分段扫描游戏回放并独立核验关键操作与结果；分类与排序仍需人工核对。",
        "chapters": chapter_ranges,
        "objectives": goals,
        "audio_change_times": peaks,
        "selection": list(audit.values()),
    }


_RESULT_CUE = re.compile(
    r"\b(?:(?:i|we|i've|we've)\s+(?:just\s+|finally\s+|have\s+)?won|"
    r"win\s+rate|first\s+place|we(?:'re| are)\s+(?:the\s+)?champions)\b|"
    r"吃鸡了|夺冠|拿下第一|拿了第一|赢了|胜率|優勝|勝率|勝った", re.I
)


def _recover_result_windows(video, rows, duration, prefs, ranked, confirmed):
    # Retrospective commentary can follow the results by a whole subtitle cue.
    # A phrase only authorizes a look inside the already enabled visual route.
    windows = []
    last_cue = -float("inf")
    for at, _, text in rows:
        if at - last_cue < prefs.duration or not _RESULT_CUE.search(text):
            continue
        last_cue = at
        if any(s.id in confirmed and s.start <= at + prefs.duration and
               s.end >= at - 1.6 * prefs.duration for s in ranked):
            continue
        for offset in (-1.6, -.8, 0):
            start = max(0, min(duration - prefs.duration, at + offset * prefs.duration))
            if not any(abs(start - s.start) < .5 for s in windows):
                windows.append(Scene(id=uuid.uuid4().hex, start=start,
                                     end=min(duration, start + prefs.duration)))
        if len(windows) >= 9:
            break
    wins = review_outcomes(video, windows, prefs.language, wins_only=True) if windows else []
    recovered = []
    for win in wins:
        if not any(min(win.end, s.end) > max(win.start, s.start) for s in recovered):
            recovered.append(win)
    return recovered + [s for s in ranked if not any(
        min(win.end, s.end) - max(win.start, s.start) > .45 * min(win.end-win.start, s.end-s.start)
        for win in recovered)]


def _commentary_rows(path, duration):
    """Preserve the entire ASR cue. Sub-cue times are estimates for scouting, verified on video."""
    rows = []
    for cue in pysrt.open(str(path), encoding="utf-8-sig"):
        start = cue.start.ordinal / 1000
        end = min(duration, cue.end.ordinal / 1000)
        text = " ".join(cue.text.split())
        if not text or start < 0 or start >= end:
            continue
        if end - start <= 12 and len(text) <= 240:
            rows.append((start, end, text))
            continue
        # Prefer clause boundaries. Bound an unpunctuated passage as well, including CJK.
        at = 0
        while at < len(text):
            stop = min(at + 180, len(text))
            boundary = re.search(r"[.!?。！？]+(?=\s|$)|[。！？]+", text[at:stop])
            if boundary:
                stop = at + boundary.end()
            elif stop < len(text):
                space = text.rfind(" ", at + 1, stop + 1)
                if space > at:
                    stop = space
            fragment = text[at:stop].strip()
            if fragment:
                rows.append((start + (end-start)*at/len(text), start + (end-start)*stop/len(text), fragment))
            at = stop
            while at < len(text) and text[at].isspace():
                at += 1
    return sorted(rows)


def subtitle_drafts(video, prefs, duration, instruction="", *, auto_frame_review=False, selection_log=None):
    from backend.utils.speech_recognizer import generate_subtitle_for_video

    path = Path(video).parent / "input.srt"
    if not path.is_file():
        generate_subtitle_for_video(video, output_path=path)
    rows = _commentary_rows(path, duration)
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
    if auto_frame_review:
        prompt += (" 可额外提名第4个有实据的不同事件。优先注意短时间内连续击败、脱险、"
                   "长连击以及整局结算；前后相邻两句可能分别描述第一次及第二次击败。")
        prompt += (
            " 先判断素材讲法。自由探索或搞笑实况，优先意外操作→即时反应，包括有可见后果的失误，"
            "即使没有输赢。不要把不同地点、不同时间发生的追击或相似操作合并。技巧解说优先找可用具体画面"
            "检验的一次完整演示：起初的问题、角色采取的操作、状态变化或重新可用的结果。"
            "按具体示范价值提名，空泛介绍和只有建议的片段跳过。每段材料不求数量，优先最清楚的例子。"
            "这两类事件另返回kind=unexpected_reaction或demonstration，以及cut_start、cut_end，"
            "用原片绝对秒覆盖这一句说明、实际操作及紧接的结果或吐槽，最长target_seconds，"
            "到下个技巧或场景前就结束。action与reaction仍是该事件的两个时间锚点。长字幕拆句时间是近似值。"
        )
    candidates = []
    # Partition by text volume as well as time, with neighbouring cues for events
    # that land at a partition boundary. Each call sees absolute source times.
    window = max(180, min(720, duration / 6)) if auto_frame_review else 720
    i = 0
    while i < len(rows):
        j = i + 1
        chars = len(rows[i][2])
        while (
            j < len(rows)
            and rows[j][0] - rows[i][0] < window
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
        for item in items[:4 if auto_frame_review else 3]:
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
            cut_start, cut_end = item.get("cut_start"), item.get("cut_end")
            if (auto_frame_review and item.get("kind") in ("unexpected_reaction", "demonstration")
                    and type(cut_start) in (int, float) and type(cut_end) in (int, float)
                    and 0 <= cut_start <= action <= reaction <= cut_end <= duration
                    and 3 <= cut_end - cut_start <= prefs.duration):
                start, end = cut_start, cut_end
            elif item.get("retelling") is True:
                onset = _reaction_onset(video, action, reaction, prefs.duration)
                if onset is not None and onset < reaction:
                    start = max(0, reaction - prefs.duration, min(action, onset - 0.60 * prefs.duration))
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
            candidates.append((tier, score, start, end, label[:120], quote if supported else "", action, reaction))
        i = j
    selected = []
    frames_allowed = auto_frame_review and intelligence.source_frame_analysis_allowed()
    anchors = {}
    commentary_text = {}
    for _, _, start, end, label, quote, action, reaction in sorted(candidates, key=lambda c: (-c[0], -c[1])):
        if end <= start or any(
            min(end, s.end) - max(start, s.start)
            > 0.45 * min(end - start, s.end - s.start)
            for s in selected
        ):
            continue
        scene = Scene(id=uuid.uuid4().hex, start=start, end=end, label=label)
        if frames_allowed:
            scene.evidence = f"{label} · {quote}" if quote else label
            anchors[scene.id] = (action, reaction)
            commentary_text[scene.id] = " ".join(text for a, b, text in rows if b > start and a < end)
        selected.append(scene)
        if len(selected) == (9 if frames_allowed else 6):
            break
    if frames_allowed:
        confirmed = set()
        audit = {}
        selected = review_outcomes(video, selected, prefs.language, confirmed_wins=confirmed,
                                   evidence_times=anchors, commentary_selection=audit, commentary_text=commentary_text)
        selected = _recover_result_windows(video, rows, duration, prefs, selected, confirmed)[:6]
        if selection_log is not None:
            final_ids = {s.id for s in selected}
            for r in audit.values():
                if r["disposition"] == "selected" and r["id"] not in final_ids:
                    r["disposition"] = "duplicate"
            for s in selected:
                if s.id not in audit:
                    audit[s.id] = dict(id=s.id, start=s.start, end=s.end, outcome="match_win",
                                       proof=s.evidence, disposition="selected")
            selection_log.extend(audit.values())
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

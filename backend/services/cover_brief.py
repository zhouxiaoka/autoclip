"""Shared editorial planning, typesetting and verification for publishing covers."""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
import uuid
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFont, ImageOps
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.services.studio import cover_design as cd
from backend.core.llm_telemetry import sanitize_model

logger = logging.getLogger(__name__)

VERSION = "brief-7"
Recipe = Literal["auto", "photo_focus", "culture_editorial", "tech_question", "bold_statement"]
Mode = Literal["crop_grade_text_only", "editorial_edit"]


class Options(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipe: Recipe = "auto"
    mode: Mode = "crop_grade_text_only"
    change_frame: bool = False
    frame_time: float | None = Field(None, ge=0, allow_inf_nan=False)
    emphasis: str = Field("", max_length=180)
    accent: str | None = Field(None, pattern=r"^#[a-fA-F0-9]{6}$")
    allow_cutout: bool = False
    allow_background_replace: bool = False


class CoverBrief(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    schema_version: int = 1
    status: Literal["ready", "needs_source_validation", "constraint_conflict"]
    issues: list[dict]
    content: dict
    source: dict
    copy_spec: dict = Field(alias="copy")
    design: dict
    permissions: dict
    export_spec: dict

    @model_validator(mode="after")
    def enforce_contract(self):
        if self.export_spec.get("width", 0) <= 0 or self.export_spec.get("height", 0) <= 0:
            raise ValueError("封面尺寸无效")
        if self.permissions["mode"] == "crop_grade_text_only" and any(
            self.permissions.get(k)
            for k in ("allow_cutout", "allow_background_replace", "allow_subject_redraw", "allow_new_objects")
        ):
            raise ValueError("原帧模式不能重绘或替换场景")
        if self.status == "ready":
            text = self.copy_spec["exact_text"]
            lines = self.copy_spec["lines"]
            if not text or (norm(" ".join(lines)) != norm(text) and "".join(lines) != text):
                raise ValueError("锁定文案与指定行不一致")
            for emphasis in self.copy_spec["emphasis"]:
                if not 1 <= emphasis["occurrence"] <= text.count(emphasis["text"]):
                    raise ValueError("强调词位置无效")
        return self


# Only the bundled OFL typefaces ship with AutoClip. Discover locally installed serif faces.
def typeface(recipe, chinese):
    if recipe == "culture_editorial":
        candidates = (
            [
                "/System/Library/Fonts/Supplemental/Songti.ttc",
                "C:/Windows/Fonts/simsun.ttc",
                "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
            ]
            if chinese
            else [
                "/System/Library/Fonts/Supplemental/Georgia.ttf",
                "C:/Windows/Fonts/georgia.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
            ]
        )
        for name in candidates:
            if Path(name).is_file():
                return Path(name)
    if not chinese and recipe in ("bold_statement", "tech_question"):
        return cd.FONT.parent / "BarlowCondensed-Black.ttf"
    return cd.FONT


def _font(path, size, recipe):
    font = ImageFont.truetype(str(path), size)
    if path == cd.FONT:
        try:
            font.set_variation_by_name("Bold" if recipe != "culture_editorial" else "Medium")
        except (ValueError, OSError, AttributeError):
            pass
    return font


def norm(text):
    # Ignore presentation whitespace, preserve case, punctuation, numbers and lexical boundaries.
    return re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", " ".join(text.split()))


def matches(observed, approved):
    return norm(observed) == norm(approved)


def plan(
    frame,
    *,
    title,
    strategy,
    size,
    origin,
    rows=(),
    options=None,
    centre=None,
    locked=False,
    secondary=(),
    revision=0,
    editorial_context=None,
):
    opts = options or Options()
    evidence = [r for r in rows if r.get("text")]
    transcript = " ".join(r["text"] for r in evidence)
    title = title.strip()
    grounded = bool(title and norm(title).casefold() in norm(transcript).casefold())
    status = "ready" if title and (locked or grounded) else "needs_source_validation"
    issues = []
    if not grounded:
        issues.append(
            dict(
                code="unverified_copy",
                severity="info" if locked else "warning",
                message="文案由用户锁定，缺少直接原话依据" if locked else "缺少当前片段的原话依据",
            )
        )
    chinese = bool(re.search(r"[\u3400-\u9fff]", title))
    question = title.endswith(("?", "？"))
    recipe = opts.recipe
    if recipe == "auto":
        if question:
            recipe = "tech_question"
        elif not chinese and len(title.split()) > 1:
            recipe = "bold_statement"
        elif re.search("创作|舞|自由|经历|文化|表演|烤肉|演员|故乡", title):
            recipe = "culture_editorial"
        else:
            recipe = "photo_focus"
    emphasis = opts.emphasis
    if emphasis and emphasis not in title:
        status = "constraint_conflict"
        issues.append(dict(code="emphasis_absent", severity="error", message="强调词不在锁定标题中"))
    if not emphasis:
        contrast = re.split(r"[,，。；]|\bbut\b|而是", title)
        if len(contrast) > 1 and contrast[-1].strip():
            emphasis = contrast[-1].strip()
        elif not chinese:
            words = re.findall(r"[\w’-]+", title)
            emphasis = max((w for w in words if len(w) > 3), key=len, default="")
        else:
            emphasis = next(
                (w for w in ("创作过程", "自由", "骨子里", "装傻", "最好", "烤肉店") if w in title),
                "",
            )
    strict = opts.mode == "crop_grade_text_only"
    if origin.get("kind") in ("reference_cover", "style_reference", "unverified"):
        status = "needs_source_validation"
        issues.append(
            dict(
                code="source_unverified",
                severity="error",
                message="参考案例无法证明当前片段的主体身份",
            )
        )
    if min(size) <= 0:
        raise ValueError("封面尺寸无效")
    geometry = {}
    if frame:
        detected, _, _ = cd._face_and_sharpness(frame, geometry)
        if detected is not None:
            centre = detected
    w, h = size
    photo = Image.open(io.BytesIO(frame)) if frame else None
    side = (
        "right"
        if centre is not None and centre < 0.46
        else "left"
        if centre is not None and centre > 0.54
        else "bottom"
    )
    layout = "bottom" if h > w else side
    if recipe == "culture_editorial" and w >= h and side == "bottom":
        layout = "left" if (centre or 0.5) >= 0.48 else "right"
    palette = {
        "culture_editorial": ("#FFF2DA", "#F7C86A"),
        "tech_question": ("#FAFAF8", "#FF866B"),
        "bold_statement": ("#FFF8E9", "#FFD54C"),
        "photo_focus": ("#FFF9F0", "#9EDBCF"),
    }[recipe]
    scene_color = None
    if photo:
        preview = photo.convert("RGB").resize((24, 16), Image.Resampling.BOX)
        zone = {"left": (0, 0, 10, 16), "right": (14, 0, 24, 16), "bottom": (0, 10, 24, 16)}[layout]
        scene_color = preview.crop(zone).resize((1, 1), Image.Resampling.BOX).getpixel((0, 0))
        red, green, blue = scene_color
        # Keep a cool counterpoint on warm sets and warm type on cool walls.
        if recipe == "tech_question" and red - blue > 8:
            palette = (palette[0], "#A7F0E0")
        elif recipe == "bold_statement" and blue - red > 12:
            palette = (palette[0], "#FFD694")
        elif recipe == "culture_editorial" and green >= red:
            palette = (palette[0], "#FFD994")
    direction = None
    if editorial_context and frame and status == "ready":
        from backend.services import cover_planner
        editorial = cover_planner.bound(frame, origin, dict(editorial_context, title=title), rows)
        origin = dict(origin, editorial_plan=editorial)
        if editorial["status"] == "planned":
            direction = editorial["direction"]
            layout = direction["text_zone"]
            palette = (palette[0], direction["accent"])
            emphasis = opts.emphasis or direction["emphasis"]
    path = typeface(recipe, chinese)
    if recipe == "culture_editorial" and path == cd.FONT:
        issues.append(
            dict(
                code="serif_unavailable",
                severity="warning",
                message="本机未安装宋体，使用随包字体",
            )
        )
    safe = 0.07
    source = {
        **origin,
        **geometry,
        "frame_sha256": hashlib.sha256(frame).hexdigest() if frame else None,
        "role": origin["kind"] if origin.get("kind") in ("reference_cover", "style_reference") else "subject_reference",
        "size": list(photo.size) if photo else None,
        "text_region_rgb": scene_color,
        "centre": centre,
    }
    content = dict(
        angle=title if grounded else None,
        claim_type="question" if question else "statement",
        evidence_status="verified" if grounded else "user_locked" if locked else "insufficient",
        evidence=evidence,
    )
    brief = CoverBrief(
        status=status,
        issues=issues,
        source=source,
        content=content,
        copy_spec=dict(
            mode="locked" if locked else "extractive",
            exact_text=title,
            lines=direction["lines"] if direction else title.splitlines(),
            line_breaks_locked=bool(direction) or "\n" in title,
            emphasis=[dict(text=emphasis, occurrence=1)] if emphasis else [],
            language="zh" if chinese else "en",
            secondary_text=list(filter(None, secondary)),
            show_nameplate=False,
        ),
        design=dict(
            recipe=recipe,
            layout=layout,
            font_family=path.name,
            palette=dict(text=palette[0], accent=opts.accent or palette[1], background="source"),
            emphasis_method="text_color",
            composition_intent={
                "left": "右侧人物，左侧安置文字",
                "right": "左侧人物，右侧安置文字",
                "bottom": "保留上方主体，在下方暗部安置文字",
            }[layout],
            protected_regions=["face", "eyes", "gesture"],
            revision=revision,
            rationale=dict(
                typography={
                    "photo_focus": "短标题保持摄影画面的主次",
                    "culture_editorial": "衬线笔画用于叙述性标题",
                    "tech_question": "紧凑标题层次保留问题与限定",
                    "bold_statement": "窄粗体容纳完整英文长词",
                }[recipe],
                emphasis="用户指定" if opts.emphasis else "从批准文案选取转折或重点短语",
                framing="依据检测到的脸部位置" if geometry else "未检出可靠人脸，优先底部留白",
            ),
        ),
        permissions=dict(
            mode=opts.mode,
            preserve_identity=True,
            preserve_expression=True,
            preserve_pose=True,
            preserve_clothing=True,
            allow_cutout=not strict and opts.allow_cutout,
            allow_background_replace=False,
            allow_new_objects=False,
            allow_subject_redraw=False,
        ),
        export_spec=dict(
            strategy_id=strategy,
            width=w,
            height=h,
            safe_margins=dict(left=safe, right=safe, top=0.06, bottom=0.08),
        ),
    )

    if direction:
        brief.design["composition_intent"] = direction["composition"]
        brief.design["rationale"].update(typography=direction["typography"], framing=direction["reason"],
                                        color=direction["color_reason"])
    if frame and brief.status == "ready":
        try:
            brief.design["typesetting"] = _measure(brief)
        except ValueError as error:
            # The local typesetter uses a fixed crop. The image editor composes its own canvas.
            if opts.mode == "editorial_edit":
                brief.issues.append(dict(code="local_typesetting", severity="warning", message=str(error)))
            else:
                brief.status = "constraint_conflict"
                brief.issues.append(dict(code="typesetting", severity="error", message=str(error)))
    return brief


def compile_prompt(b):
    design, copy, spec = b.design, b.copy_spec, b.export_spec
    direction = {
        "photo_focus": "人物访谈的视觉重点是说话那一刻的神情。顺着人物的视线，在现场暗部或安静的背景中安排标题，让读者从眼神自然读到整句话。标题用笔画饱满的粗黑体，字组紧凑，重音鲜明。",
        "tech_question": "把问题的铺垫和真正让人想回答的那半句分出轻重，用紧凑的粗黑体托住问句。让人物的表情与问句相呼应，保留疑问和限定词。",
        "culture_editorial": "保留现场光色，让眼神或原有的手势带出叙述。标题使用有粗细变化的衬线字，沿场景留白展开，强调色落在承载主题的词组上。",
        "bold_statement": "用紧实的窄粗体容纳完整观点，将重音落在关键短语上。保留长词和否定词，让原有的姿态与文字在缩略图上都能辨认。",
    }[design["recipe"]]
    planned = b.source.get("editorial_plan") or {}
    if planned.get("status") == "planned":
        shot = planned["direction"]
        direction = "\n".join([f"此帧主体与朝向：{shot['subject']}", f"取景边界：{shot['crop_boundary']}",
                               f"文字区域 {shot['text_zone']}。构图与阅读顺序：{shot['composition']}",
                               f"字体与行间层级：{shot['typography']}", f"色彩依据：{shot['color_reason']}"])
    elif b.source.get("editorial_plan"):
        direction += (f" 本帧排版依据：{design['composition_intent']}。"
                      f"字体选择：{design['rationale']['typography']}。"
                      "以照片中可见的主体边界为摄影截止线，根据真实画面微调，保留原有现场明暗。")
    regions = design.get("protected_regions", [])
    framing = ["沿用参考图的主体、衣着、表情、动作和原现场的光线。"]
    if "visible_shoulders_and_chest" in regions:
        framing.append("把原片当作一幅已经裁好的半身摄影：发顶完整，双肩可见，胸口刚到输入照片下沿就结束。把这条下沿当作摄影截止线；以下仅用取自现场的暗色作为纸面，不得在纸面接续衣服轮廓。严禁向下续画躯干、衣袖、手臂或衣褶。")
    if "right_look_room" in regions:
        framing.append("人物偏左，保住发梢，头顶上方的空场收至一小条，约一只眼睛到眉毛的距离。右侧标题首行落在视线的延长线上，与眼睛大致同高。脸的最右轮廓到首字留半个主标题字宽，末字到画幅右边也留至少半个字宽。版心挤时整组标题用窄体并适当缩小，仍保持在脸旁。")
    framing.append("画外的手、手指、身体或道具不得补画。通过取景避开源片边缘的标志，四角干净，禁止搬移或复制角标。")
    allowed = ["裁切、调光、排字"]
    if b.permissions["allow_cutout"]:
        allowed.append("可沿真实轮廓抠图")
    framing.append("按原照片的朝向取景，保持鼻尖、耳朵、双肩及可见双手的相对位置；不能水平翻转、转头或补出原片边缘以外的衣袖、躯干、手指。"
                   "保留原现场及可辨识物体的排列。版心容不下时，调整标题字号、留白或裁切，不得为排字重建人物或背景。此约束优先于构图建议。")
    palette = design["palette"]
    emphasis = "、".join(e["text"] for e in copy["emphasis"])
    color = f"标题主色 {palette['text']}。"
    if emphasis:
        color += f"将「{emphasis}」作为一个完整的字组，用同一纯色 {palette['accent']} 一次填满其中每个字形；组内不混入主色，不渐变，其余字保持主色。"
    wording = copy["lines"] if copy.get("line_breaks_locked") else [copy["exact_text"]]
    type_direction = "文字采用印刷油墨的平涂硬边，底图选均匀暗部；如需压光，调整整片背景明度，字边周围保持与邻近底图一致。禁用白色光晕、雾状白底、描边和阴影。"
    if planned.get("status") != "planned" and copy.get("line_breaks_locked") and len(wording) == 2 and b.content.get("claim_type") == "question":
        type_direction += "严格按文末换行。第一行用常规字重，相当于 Regular 400，字高约为第二行的三分之二；第二行用窄黑体 Heavy 900，厚实，标点与末词同字号同基线。两行左齐，末尾问号完整入画。"
    return "\n".join([
        f"以提供的真实视频帧为唯一摄影素材，直接交付一张排好字、可发布的 {spec['width']}×{spec['height']} 封面。",
        direction,
        "".join(framing),
        "按以上构图在目标画幅内取景排字。缩到手机列表大小，主体与标题仍要一眼可读；避免四面加框的小照片、独立大标题栏和装饰性描边。",
        color, type_direction,
        "允许的编辑：" + "、".join(allowed) + "。画面只出现以下批准文案一次，保留原字、数字及标点：",
        *wording, *copy["secondary_text"],
    ])


def _wrap(text, font, width, emphasis):
    # Keep numbers with CJK units, punctuation with the preceding word, and
    # keep a short pull-phrase together when it fits in this column.
    phrase = re.escape(emphasis) + "|" if emphasis and font.getlength(emphasis) <= width else ""
    pattern = (
        phrase
        + r"[一二三两几每这那][家个段年次张位种]|[A-Za-z][a-z]+ [A-Z]{2,}(?=\b)|[0-9]+(?:[.,][0-9]+)*(?:个月|个月份|年|天|次|%|元)?|[A-Za-z0-9]+(?:[’'-][A-Za-z0-9]+)*|\s+|."
    )
    lines = []
    for paragraph in text.splitlines():
        current = ""
        if re.search(r"[\u3400-\u9fff]", paragraph):
            from backend.services.studio.cjk_segment import break_units

            tokens = []
            for unit in break_units(paragraph, emphasis):
                if tokens and unit in ("着", "了", "的", "过", "？", "！", "。", "，"):
                    tokens[-1] += unit
                else:
                    tokens.append(unit)
        else:
            tokens = re.findall(pattern, paragraph)
        for token in tokens:
            trial = current + token
            if (
                current.strip()
                and font.getlength(trial) > width
                and not token.isspace()
                and token not in "，。！？,.!?"
            ):
                lines.append(current.rstrip())
                current = ""
            current += token if current else token.lstrip()
        if current:
            lines.append(current.rstrip())
    return lines


def _measure(b):
    if b.status != "ready":
        raise ValueError(b.issues[-1]["message"])
    d, c = b.design, b.copy_spec
    w, h = b.export_spec["width"], b.export_spec["height"]
    photo_w, photo_h = b.source["size"]
    cx = b.source.get("centre")
    # Centre the actual crop on the subject (ImageOps.fit centering is a fraction of excess).
    crop_w = min(photo_w, photo_h * w / h)
    left = min(
        max(0, (cx if cx is not None else 0.5) * photo_w - crop_w / 2),
        photo_w - crop_w,
    )
    side = d["layout"]
    maxw = round(w * (0.86 if side == "bottom" else 0.35 if d["recipe"] == "culture_editorial" else 0.43))
    maxh = round(h * (0.32 if side == "bottom" else 0.66))
    if side == "bottom" and b.source.get("face_box"):
        crop_h = min(photo_h, photo_w * h / w)
        chin = (b.source["face_box"][3] - (photo_h - crop_h) * 0.42) * h / crop_h
        room = int(h * 0.91 - chin)
        if room > h * 0.14:
            maxh = min(maxh, room)
    path = typeface(d["recipe"], c["language"] == "zh")
    size = int(min(w, h) * (0.16 if d["recipe"] == "bold_statement" else 0.145 if h > w else 0.14))
    content = "\n".join([*c["lines"], *c["secondary_text"]])
    size = round(size * (1, 0.94, 1.04)[d["revision"] % 3])
    emphasis = c["emphasis"][0]["text"] if c["emphasis"] else ""
    # A short locked Chinese headline reads better as one line than as a one-character tail.
    if c["language"] == "zh" and len(content) <= 10 and "\n" not in content:
        while size > min(w, h) * 0.075 and _font(path, size, d["recipe"]).getlength(content) > maxw:
            size -= 2
    while size >= min(w, h) * 0.031:
        font = _font(path, size, d["recipe"])
        lines = content.splitlines() if c["line_breaks_locked"] else _wrap(content, font, maxw, emphasis)
        step = int(size * 1.23)
        if lines and max(font.getlength(v) for v in lines) <= maxw and step * len(lines) <= maxh:
            break
        size -= 2
    else:
        raise ValueError("标题无法在安全区域内完整排版")
    if any(
        bytes(font.getmask(ch)) == bytes(font.getmask("\U0010ffff")) for ch in set(content) if not ch.isspace()
    ):
        raise ValueError("字体缺少标题所需字形")
    x = round(w * 0.07) if side != "right" else w - round(w * 0.07) - maxw
    y = round(h * 0.92) - len(lines) * step if side == "bottom" else round((h - len(lines) * step) * 0.52)
    face = b.source.get("face_box")
    if face:
        crop_h = min(photo_h, photo_w * h / w)
        top = (photo_h - crop_h) * 0.42
        fx1, fy1, fx2, fy2 = face
        projected = (
            (fx1 - left) * w / crop_w,
            (fy1 - top) * h / crop_h,
            (fx2 - left) * w / crop_w,
            (fy2 - top) * h / crop_h,
        )
        block_w = max(font.getlength(line) for line in lines)
        block_h = step * len(lines)

        def clears_face(xx, yy):
            a, bb, cc, dd = projected
            return xx + block_w <= a or xx >= cc or yy + block_h <= bb or yy >= dd

        if not clears_face(x, y):
            placements = [
                (x, round(0.92 * h) - block_h, "bottom"),
                (x, round(0.06 * h), "top"),
                (round(0.93 * w - block_w), round(0.92 * h) - block_h, "bottom"),
            ]
            for xx, yy, zone in placements:
                if clears_face(xx, yy):
                    x, y, side = xx, yy, zone
                    break
            else:
                raise ValueError("画幅与文字要求冲突，无法保留清晰脸部")
    return dict(
        lines=lines,
        font=font.getname(),
        font_size=size,
        text_origin=[x, y],
        line_spacing=step,
        crop_centre=[round(left / max(1, photo_w - crop_w), 5), 0.42],
        overlay=side,
    )


def render(frame, b):
    d, c = b.design, b.copy_spec
    w, h = b.export_spec["width"], b.export_spec["height"]
    typeset = d["typesetting"]
    lines = typeset["lines"]
    step = typeset["line_spacing"]
    x, y = typeset["text_origin"]
    side = typeset["overlay"]
    font = _font(typeface(d["recipe"], c["language"] == "zh"), typeset["font_size"], d["recipe"])
    content = "\n".join([*c["lines"], *c["secondary_text"]])
    img = ImageOps.fit(
        Image.open(io.BytesIO(frame)).convert("RGB"),
        (w, h),
        Image.Resampling.LANCZOS,
        centering=typeset["crop_centre"],
    )
    axis = h if side in ("bottom", "top") else w
    mask = Image.new("L", (1, axis))
    for i in range(axis):
        position = i / axis if side in ("right", "bottom") else 1 - i / axis
        mask.putpixel(
            (0, i),
            round(
                215
                * max(
                    0,
                    min(
                        1,
                        (position - (0.58 if side == "bottom" else 0.30)) / (0.35 if side == "bottom" else 0.63),
                    ),
                )
                ** 1.3
            ),
        )
    if side not in ("bottom", "top"):
        mask = mask.transpose(Image.Transpose.TRANSPOSE)
    img = Image.composite(Image.new("RGB", (w, h), (18, 17, 19)), img, mask.resize((w, h)))
    draw = ImageDraw.Draw(img)
    highlight = c["emphasis"][0]["text"] if c["emphasis"] else ""
    first = content.find(highlight) if highlight else -1
    cursor = 0
    for row, line in enumerate(lines):
        offset = content.index(line, cursor)
        cursor = offset + len(line)
        segments = [0, len(line)]
        if first >= 0:
            segments += [v - offset for v in (first, first + len(highlight)) if offset < v < cursor]
        stops = sorted(set(segments))
        for a, z in zip(stops, stops[1:]):
            color = (
                d["palette"]["accent"] if first <= offset + a < first + len(highlight) else d["palette"]["text"]
            )
            draw.text(
                (x + font.getlength(line[:a]), y + row * step),
                line[a:z],
                font=font,
                fill=color,
                anchor="lt",
            )
    out = io.BytesIO()
    img.save(out, "JPEG", quality=94, subsampling=0)
    return out.getvalue(), typeset


def fingerprint(b, provider, model):
    data = [VERSION, b.model_dump(by_alias=True), provider, model]
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def record(b, *, method, check, provider="", model="", prompt=None, reason=None, transform=None):
    return dict(
        schema_version=1,
        prompt_version=VERSION,
        brief=b.model_dump(by_alias=True),
        prompt=prompt,
        provider=provider,
        model=sanitize_model(model) if model else "",
        export_spec=b.export_spec,
        fingerprint=fingerprint(b, provider, model),
        result=method,
        validation="unavailable" if method == "model" else check,
        checks=dict(
            text=check,
            dimensions="passed" if method != "failed" else "unavailable",
            source_pixels="passed" if method == "local_design" else "unavailable",
            typography="passed" if transform else "unavailable",
            selected_face_geometry="passed" if transform and b.source.get("face_box") else "unavailable",
            editorial_identity="unavailable" if method == "model" else "not_applicable",
        ),
        visual_review="pending",
        fallback_reason=reason,
        transform=transform,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def fit_model(image, size):
    with Image.open(io.BytesIO(image)) as original:
        if original.size == size and original.format == "JPEG":
            original.verify()
            return image
        # Retain the whole canvas and all artwork. Neutral matte only for aspect differences.
        img = ImageOps.pad(original.convert("RGB"), size, Image.Resampling.LANCZOS, color=(24, 23, 23))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=95, subsampling=0)
        return buf.getvalue()


def begin(key):
    from backend.services.studio import store

    with store.lock:
        token = uuid.uuid4().hex
        atomic(key.with_suffix(".request"), token.encode())
        return token


@contextmanager
def commit(key, token):
    from backend.services.studio import store

    with store.lock:
        if key.with_suffix(".request").read_text() != token:
            raise ValueError("封面请求已由新版本取代")
        yield


class Rejected(ValueError):
    def __init__(self, message, audit):
        super().__init__(message)
        self.audit = audit


def record_rejection(path, token, rejection):
    with commit(path, token):
        atomic(
            path.with_suffix(".last-failure.json"),
            json.dumps(
                dict(rejection.audit, request_id=token, previous_preserved=True),
                ensure_ascii=False,
            ).encode(),
        )
        logger.warning(
            "Cover model rejected: file=%s provider=%s model=%s attempts=%d fallback_reason=%s",
            path.name,
            rejection.audit.get("provider") or "",
            rejection.audit.get("model") or "",
            int(rejection.audit.get("attempts") or 0),
            rejection.audit.get("fallback_reason"),
        )


def atomic(path, data):
    tmp = path.with_name("." + uuid.uuid4().hex + ".tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _repair_prompt(b, fidelity, layout):
    aspect_names = {
        "identity": "人物身份或五官", "hands": "原帧外的手或改变的手势", "pose": "姿态",
        "orientation": "人物朝向", "facing": "人物朝向", "body_boundary": "超出原帧的躯干或衣袖",
        "background": "现场背景",
    }
    issues = [aspect_names[key] for key in dict.fromkeys(fidelity.get("changed", []) + fidelity.get("uncertain", []))
              if key in aspect_names]
    observations = fidelity.get("observations") or {}
    left, top, right, bottom = layout.bbox_pct
    instructions = [
        "直接制作一张可发布的完整摄影封面。唯一输入照片就是最终封面的摄影原件。"
        "把原照片当作锁定的照片图层，保持现场纹理、光线、衣服与脸部细节。通过同一张照片的等比裁切适配画幅，"
        "保持主体朝向和照片下边缘，不能从胸像拉远成为半身像。如果空间不足，使用纯色排版边栏，摄影区域停在原帧边界。",
        "现场核对要点：" + "、".join(issues) + "。"
        "辨认可见的面部和手臂边缘及人物背后可对应的物件，保持原样。不要重新布光、锐化、叠加颗粒或美术滤镜。",
        "批准标题：" + b.copy_spec["exact_text"],
        f"画幅 {b.export_spec['width']}×{b.export_spec['height']}。标题墨迹范围约为画宽 {left:g}% 至 {right:g}%，"
        f"画高 {top:g}% 至 {bottom:g}%。对齐方式 {layout.align}。按下列行序排字，保持层级和行间距：",
    ]
    for i, line in enumerate(layout.lines, 1):
        instructions.append(f"第{i}行「{line.text}」 字重 {line.weight}，字高约为画高 {line.height_pct:g}%，基色 {line.color}。")
    if layout.emphasis:
        instructions.append(f"「{layout.emphasis}」整体使用 {layout.emphasis_color}，保留其原有断行。")
    if isinstance(observations.get("reference_hands"), int):
        instructions.append(f"源帧中可见 {observations['reference_hands']} 只手。不得增加手、手指、衣袖或躯干。")
    if b.copy_spec["secondary_text"]:
        instructions.append("批准的副文案：" + " / ".join(b.copy_spec["secondary_text"]))
    instructions.append("直接交付一张带上述标题的成品。版式参数和摄影说明不出现在画内。")
    return "\n".join(instructions)


def make(b, frame, cfg, *, can_send, generate, check, previous=False, allow_model=True):
    """Both producers use this decision, including the bounded edit retry and the same-frame fallback."""
    from backend.core.image_providers import ImageError, ImageRequest
    from backend.services import cover_fidelity

    if not frame or hashlib.sha256(frame).hexdigest() != b.source["frame_sha256"]:
        raise ValueError("实际参考图与设计简报不符")
    spec = b.export_spec
    size = (spec["width"], spec["height"])
    prompt = None
    reason = None
    verify = None
    attempts = 0
    comparisons = []
    layout_reference = None
    if b.status == "constraint_conflict":
        raise ValueError(b.issues[-1]["message"])
    if b.status == "needs_source_validation":
        if previous:
            raise ValueError("缺少文案来源，已保留原封面")
        if b.source.get("kind") in ("style_reference", "reference_cover", "unverified"):
            raise ValueError("需要核实原素材，无法使用参考案例作为封面")
        return fit_model(frame, size), record(b, method="source_frame", check="unavailable", reason=b.status)
    if b.permissions["mode"] == "editorial_edit":
        if not allow_model:
            if not can_send:
                reason = "frame_sending_disabled"
            elif not (cfg.enabled and cfg.configured):
                reason = "image_service_unavailable"
        elif can_send and cfg.enabled and cfg.configured:
            prompt = compile_prompt(b)
            req = ImageRequest(
                prompt=prompt,
                width=size[0],
                height=size[1],
                reference=frame,
                model=cfg.model,
            )
            for _ in range(2):
                attempts += 1
                try:
                    image = generate(req)
                    data = fit_model(image, size)
                    fidelity = cover_fidelity.compare(frame, image, layout_reference)
                    comparisons.append(fidelity)
                    verify = None
                    if fidelity["status"] != "passed":
                        reason = "subject_changed" if fidelity["status"] == "failed" else "fidelity_unavailable"
                        if fidelity.get("changed") == ["title_layout"]:
                            reason = "cover_layout_changed"
                        if fidelity.get("changed") == ["photo_quality"]:
                            reason = "cover_photo_degraded"
                        if attempts == 1 and (fidelity.get("changed") or fidelity.get("uncertain")):
                            layout = cover_fidelity.read_title_layout(image, b.copy_spec["exact_text"])
                            if layout is None:
                                fidelity["title_layout_read"] = "unavailable"
                                break
                            fidelity["title_layout_read"] = layout.model_dump()
                            layout_reference = image  # Verification only. The generator receives the original frame.
                            req = replace(req, prompt=_repair_prompt(b, fidelity, layout))
                            continue
                        break
                    verify = check(
                        data,
                        [b.copy_spec["exact_text"], *b.copy_spec["secondary_text"]],
                    )
                except (ImageError, OSError) as exc:
                    reason = (
                        "unsupported_edit"
                        if getattr(exc, "unsupported_edit", False)
                        else "image_service_unavailable"
                    )
                    break
                if verify is True:
                    audit = record(
                        b,
                        method="model",
                        check="passed",
                        provider=cfg.provider,
                        model=cfg.model,
                        prompt=req.prompt,
                    )
                    audit.update(attempts=attempts, model_original_sha256=fidelity["candidate_sha256"],
                                 model_fidelity=fidelity, fidelity_attempts=comparisons)
                    audit["checks"]["editorial_identity"] = "passed"
                    audit["_original_bytes"] = image
                    return data, audit
                reason = "text_unavailable" if verify is None else "text_mismatch"
                if verify is None or attempts == 2:
                    break

                req = replace(
                    req,
                    prompt=prompt + "\n校正上一版的文字：逐字核对批准文案，去除重复和额外文字。",
                )
            prompt = req.prompt if attempts == 2 else prompt
        else:
            reason = "frame_sending_disabled" if not can_send else "image_service_unavailable"
    local_layout_missing = not b.design.get("typesetting")
    # A completed fidelity repair gets the same source-layout fallback on regeneration.
    # If the service never delivered a revision, retain the existing published cover.
    reviewed_repair = len(comparisons) == 2 and comparisons[0]["status"] != "passed"
    if previous and (local_layout_missing or (attempts and not reviewed_repair)):
        audit = record(
            b,
            method="failed",
            check="passed" if verify is True else "unavailable" if verify is None else "failed",
            provider=cfg.provider,
            model=cfg.model,
            prompt=prompt,
            reason=reason,
        )
        audit.update(attempts=attempts, model_fidelity=comparisons[-1] if comparisons else None, fidelity_attempts=comparisons)
        raise Rejected("模型结果未通过验证，已保留原封面" if attempts else "无法在原帧上排版，已保留原封面", audit)
    if local_layout_missing:
        audit = record(b, method="source_frame", check="unavailable", reason=reason or "local_typesetting",
                       prompt=prompt, provider=cfg.provider if attempts else "", model=cfg.model if attempts else "")
        audit.update(attempts=attempts, model_fidelity=comparisons[-1] if comparisons else None, fidelity_attempts=comparisons)
        return fit_model(frame, size), audit
    image, transform = render(frame, b)
    audit = record(
        b,
        method="local_design",
        check="passed",
        transform=transform,
        reason=reason,
        prompt=prompt,
        provider=cfg.provider if attempts else "",
        model=cfg.model if attempts else "",
    )
    audit.update(
        attempts=attempts,
        model_fidelity=comparisons[-1] if comparisons else None,
        fidelity_attempts=comparisons,
        model_text_validation=("failed" if verify is False else "unavailable") if attempts else None,
    )
    return image, audit


def stored_path(meta_path, legacy, field="artifact"):
    try:
        name = json.loads(meta_path.read_text(encoding="utf-8")).get(field, "")
        if isinstance(name, str) and re.fullmatch(r"[a-f0-9]{32}-(cover|frame)\.jpg", name):
            return meta_path.parent / "versions" / name
    except (FileNotFoundError, ValueError, AttributeError):
        pass
    return legacy


def save(meta_path, token, data, frame, metadata):
    # Immutable image/frame followed by a single atomic pointer switch. Readers can finish on an older version.
    with commit(meta_path, token):
        versions = meta_path.parent / "versions"
        versions.mkdir(exist_ok=True)
        img_name, frame_name = token + "-cover.jpg", token + "-frame.jpg"
        metadata = dict(metadata)
        original = metadata.pop("_original_bytes", None)
        if original is not None:
            extension = Image.open(io.BytesIO(original)).format.lower()
            metadata["model_original_file"] = f"{token}-original.{extension}"
            atomic(versions / metadata["model_original_file"], original)
        atomic(versions / img_name, data)
        atomic(versions / frame_name, frame)
        atomic(
            meta_path,
            json.dumps(
                dict(
                    metadata,
                    request_id=token,
                    result_version=token,
                    artifact=img_name,
                    reference_file=frame_name,
                ),
                ensure_ascii=False,
            ).encode(),
        )
        logger.info(
            "Cover artifact saved: file=%s result=%s provider=%s model=%s attempts=%d fallback_reason=%s",
            meta_path.name,
            metadata.get("result") or "",
            metadata.get("provider") or "",
            metadata.get("model") or "",
            int(metadata.get("attempts") or 0),
            metadata.get("fallback_reason"),
        )


def join_lines(lines):
    return (" " if any(re.search("[A-Za-z]", v) for v in lines) else "").join(lines)


def choose_copy(proposed, rows, locked):
    """A publication title is a planning hint. Only extract literal, contiguous speech on automatic jobs."""
    if locked or not rows:
        return proposed
    transcript = " ".join(row["text"] for row in rows)
    if proposed and norm(proposed).casefold() in norm(transcript).casefold():
        return proposed
    # Cross-language audience titles (e.g., Chinese Douyin title over English raw subtitles)
    # must not be replaced with an untranslated quote from the source-language transcript.
    if proposed and bool(re.search(r"[\u3400-\u9fff]", proposed)) != bool(re.search(r"[\u3400-\u9fff]", transcript)):
        return proposed
    parts = [s.strip(" >") for s in re.split(r"(?<=[。！？.!?])\s*|\s*>>\s*", transcript) if s.strip(" >")]
    if not parts:
        return proposed
    keywords = set(re.findall(r"[\w]{3,}|[\u3400-\u9fff]", proposed.casefold()))
    candidates = [p for p in parts if 3 <= len(p) <= 94]
    if not candidates:
        return proposed
    return max(
        candidates,
        key=lambda p: (
            sum(word in p.casefold() for word in keywords),
            -abs(len(p) - 30),
        ),
    )


def compat_prompt(strategy, lines, subtitle="", badge=""):
    brief = plan(
        None,
        title=join_lines(lines),
        strategy=strategy,
        size=cd.size_for(strategy),
        locked=True,
        origin=dict(kind="unspecified"),
        secondary=[subtitle, badge],
        options=Options(mode="editorial_edit"),
    )
    return compile_prompt(brief)


def selected_candidate(video, source, at):
    from backend.services.cover import extract_frame_jpeg

    candidates = source.get("candidates", [])
    match = next((c for c in candidates if c["time"] == at), None)
    if match is None:
        raise ValueError("候选镜头已变化，请刷新后重试")
    frame = extract_frame_jpeg(video, at_sec=at, max_width=1920)
    if match.get("frame_sha256") and match["frame_sha256"] != hashlib.sha256(frame).hexdigest():
        raise ValueError("候选镜头已变化，请刷新后重试")
    source.update(source_timestamp_sec=at, selection_reason="用户选定片段内候选镜头")
    return frame, match["centre"]

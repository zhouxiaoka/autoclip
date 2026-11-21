"""Shared editorial planning, typesetting and verification for publishing covers."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFont, ImageOps
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.services.studio import cover_design as cd
from backend.core.llm_telemetry import sanitize_model

VERSION = "brief-1"
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
            if not text or norm(" ".join(self.copy_spec["lines"])) != norm(text):
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
            lines=title.splitlines(),
            line_breaks_locked="\n" in title,
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
            allow_background_replace=not strict and opts.allow_background_replace,
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

    if frame and brief.status == "ready":
        try:
            brief.design["typesetting"] = _measure(brief)
        except ValueError as error:
            brief.status = "constraint_conflict"
            brief.issues.append(dict(code="typesetting", severity="error", message=str(error)))
    return brief


def compile_prompt(b):
    design, copy, spec = b.design, b.copy_spec, b.export_spec
    allowed = ["裁切、调光和排字"]
    if b.permissions["allow_cutout"]:
        allowed.append("可沿真实轮廓抠图")
    if b.permissions["allow_background_replace"]:
        allowed.append("可替换为取自原场景的色调背景")
    emphasis = "、".join(e["text"] for e in copy["emphasis"]) or "无"
    typeset = design.get("typesetting") or {}
    text = "\n".join(typeset.get("lines") or [copy["exact_text"], *copy["secondary_text"]])
    placement = design["composition_intent"]
    if typeset:
        x, y = typeset["text_origin"]
        placement = f"文字从画幅左侧 {x / spec['width']:.0%}、顶部 {y / spec['height']:.0%} 开始；参考字号约为短边的 {typeset['font_size'] / min(spec['width'], spec['height']):.0%}，按下列行序排字"

    return "\n".join(
        [
            "编辑参考图，参考图是唯一的人物与场景来源。保留脸、衣着、表情、视线和动作。",
            "仅允许：" + "；".join(allowed) + "。禁止添加人物、道具或新动作。",
            f"{design['rationale']['typography']}。{placement}，避开眼睛和重要手势。",
            f"字体 {design['font_family']}，主色 {design['palette']['text']}，强调 {emphasis} 用 {design['palette']['accent']}。",
            "唯一批准的文案如下，保留标点、词间空格与否定词，只呈现一次：",
            text,
            f"交付排好字的 {spec['width']}×{spec['height']} 封面。左右各留 7%，底部留 8%。设计说明和姓名不得入画。",
        ]
    )


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
    content = "\n".join([c["exact_text"], *c["secondary_text"]])
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
    content = "\n".join([c["exact_text"], *c["secondary_text"]])
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


def atomic(path, data):
    tmp = path.with_name("." + uuid.uuid4().hex + ".tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def make(b, frame, cfg, *, can_send, generate, check, previous=False):
    """Both producers use this decision, including the bounded edit retry and the same-frame fallback."""
    from backend.core.image_providers import ImageError, ImageRequest

    if not frame or hashlib.sha256(frame).hexdigest() != b.source["frame_sha256"]:
        raise ValueError("实际参考图与设计简报不符")
    spec = b.export_spec
    size = (spec["width"], spec["height"])
    prompt = None
    reason = None
    verify = None
    attempts = 0
    if b.status == "constraint_conflict":
        raise ValueError(b.issues[-1]["message"])
    if b.status == "needs_source_validation":
        if previous:
            raise ValueError("缺少文案来源，已保留原封面")
        if b.source.get("kind") in ("style_reference", "reference_cover", "unverified"):
            raise ValueError("需要核实原素材，无法使用参考案例作为封面")
        return fit_model(frame, size), record(b, method="source_frame", check="unavailable", reason=b.status)
    if b.permissions["mode"] == "editorial_edit":
        if can_send and cfg.enabled and cfg.configured:
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
                    with Image.open(io.BytesIO(image)) as candidate:
                        if not b.permissions["allow_background_replace"] and not cd.keeps_scene(frame, candidate):
                            reason = "scene_changed"
                            break
                    data = fit_model(image, size)
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
                    audit.update(attempts=attempts)
                    return data, audit
                reason = "text_unavailable" if verify is None else "text_mismatch"
                if verify is None:
                    break
                from dataclasses import replace

                req = replace(
                    req,
                    prompt=prompt + "\n校正上一版的文字：逐字核对批准文案，去除重复和额外文字。",
                )
            prompt = req.prompt if attempts == 2 else prompt
        else:
            reason = "frame_sending_disabled" if not can_send else "image_service_unavailable"
    if previous and attempts:
        audit = record(
            b,
            method="failed",
            check="unavailable" if verify is None else "failed",
            provider=cfg.provider,
            model=cfg.model,
            prompt=prompt,
            reason=reason,
        )
        audit["attempts"] = attempts
        raise Rejected("模型结果未通过验证，已保留原封面", audit)
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


def join_lines(lines):
    return (" " if any(re.search("[A-Za-z]", v) for v in lines) else "").join(lines)


def choose_copy(proposed, rows, locked):
    """A publication title is a planning hint. Only extract literal, contiguous speech on automatic jobs."""
    if locked or not rows:
        return proposed
    transcript = " ".join(row["text"] for row in rows)
    if proposed and norm(proposed).casefold() in norm(transcript).casefold():
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
    source.update(source_timestamp_sec=at, selection_reason="用户选定片段内候选镜头")
    return extract_frame_jpeg(video, at_sec=at, max_width=1920), match["centre"]

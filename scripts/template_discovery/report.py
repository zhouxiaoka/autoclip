"""Report & contact-sheet generator for weekly viral template discovery runs."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from scripts.template_discovery.analyzer import StyleAnalysis
from scripts.template_discovery.sources import CandidateVideo


def build_contact_sheet(
    items: list[tuple[CandidateVideo, StyleAnalysis]],
    dest: Path,
    *,
    max_tiles: int = 12,
) -> Path | None:
    """Render a clean visual contact sheet (up to 4 columns) of the top discovered candidates."""
    usable = [(c, a) for c, a in items if a.keyframe_paths and Path(a.keyframe_paths[0]).is_file()][:max_tiles]
    if not usable:
        return None
    cols = min(4, len(usable))
    rows = (len(usable) + cols - 1) // cols
    tw, th = 320, 220
    pad = 12
    sheet = Image.new('RGB', (cols * (tw + pad) + pad, rows * (th + pad) + pad), (18, 18, 22))
    draw = ImageDraw.Draw(sheet)

    for idx, (cand, ana) in enumerate(usable):
        r, c = divmod(idx, cols)
        x0 = pad + c * (tw + pad)
        y0 = pad + r * (th + pad)
        kf = Path(ana.keyframe_paths[len(ana.keyframe_paths) // 2])
        try:
            with Image.open(kf) as im:
                thumb = im.convert('RGB')
                thumb.thumbnail((tw, th - 36), Image.Resampling.LANCZOS)
                ox = x0 + (tw - thumb.width) // 2
                oy = y0 + (th - 36 - thumb.height) // 2
                sheet.paste(thumb, (ox, oy))
        except Exception:
            continue
        # Bottom strip with archetype badge + palette swatches
        bar_y = y0 + th - 34
        draw.rectangle([x0, bar_y, x0 + tw, y0 + th], fill=(28, 28, 34))
        tag = f"[NEW] {ana.archetype}" if ana.is_new_opportunity else ana.archetype
        draw.text((x0 + 8, bar_y + 9), f"{cand.platform.upper()} | {tag}", fill=(245, 245, 245))
        for si, hx in enumerate(ana.palette[:3]):
            try:
                rgb = tuple(int(hx[i:i + 2], 16) for i in (1, 3, 5))
                sx = x0 + tw - 18 - si * 18
                draw.rectangle([sx, bar_y + 9, sx + 14, bar_y + 23], fill=rgb, outline=(255, 255, 255))
            except Exception:
                pass

    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest)
    return dest


def write_report(
    items: list[tuple[CandidateVideo, StyleAnalysis]],
    out_dir: Path,
) -> dict[str, Path]:
    """Write candidates.json, discovery_report.md, and contact_sheet.png into out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    # Sort by new opportunity first, then engagement score descending.
    ranked = sorted(items, key=lambda pair: (0 if pair[1].is_new_opportunity else 1, -pair[0].engagement_score))

    json_path = out_dir / 'candidates.json'
    payload: list[dict[str, Any]] = [
        {'video': c.to_dict(), 'analysis': a.to_dict()} for c, a in ranked
    ]
    json_path.write_text(json.dumps({'generated_at': now, 'count': len(payload), 'items': payload}, ensure_ascii=False, indent=2), encoding='utf-8')

    sheet_path = build_contact_sheet(ranked, out_dir / 'contact_sheet.png')

    arch_counts = Counter(a.archetype for _, a in ranked)
    new_ops = [(c, a) for c, a in ranked if a.is_new_opportunity]

    lines: list[str] = [
        '# AutoClip 爆款模板自动挖掘周报',
        '',
        f'- 生成时间：`{now}`',
        f'- 扫描候选总数：**{len(ranked)}** 条（其中新模板机会：**{len(new_ops)}** 条）',
        '',
    ]
    if sheet_path is not None:
        lines += [f'![Discovery Contact Sheet](file://{sheet_path.resolve()})', '']

    lines += [
        '## 一、视觉版式聚类分布',
        '',
        '| 视觉原型 (Archetype) | 命中数量 | 现有模板库覆盖 | 是否新模板机会 |',
        '| :--- | :---: | :--- | :---: |',
    ]
    for arch, cnt in arch_counts.most_common():
        sample_ana = next(a for _, a in ranked if a.archetype == arch)
        cov = ', '.join(f'`{t}`' for t in sample_ana.existing_match) if sample_ana.existing_match else '—'
        badge = '🔥 **NEW**' if sample_ana.is_new_opportunity else '✅ 已覆盖'
        lines.append(f'| `{arch}` | {cnt} | {cov} | {badge} |')

    lines += [
        '',
        '## 二、Top 候选清单（按新机会 & 热度排序）',
        '',
        '| # | 平台 | 赛道 | 标题 | 播放量 | 识别原型 | 主色板 | 备注 |',
        '| :-: | :---: | :---: | :--- | ---: | :--- | :--- | :--- |',
    ]
    for idx, (c, a) in enumerate(ranked[:20], 1):
        title = (c.title[:34] + '…') if len(c.title) > 35 else c.title
        title_md = f'[{title}]({c.url})' if c.url.startswith('http') else title
        pal = ' '.join(f'`{h}`' for h in a.palette[:3])
        opp = '🔥 ' if a.is_new_opportunity else ''
        lines.append(
            f'| {idx} | {c.platform} | {c.track} | {title_md} | {c.views:,} | {opp}`{a.archetype}` | {pal} | {a.notes} |'
        )

    lines += [
        '',
        '## 三、一键复刻为热更新模板',
        '',
        '挑选上面看中的参考视频后，可直接运行克隆脚手架生成 `templates-catalog/<new_id>/` 草稿，验收后触发 `Publish Template Catalog` 即可热推送给所有 1.6.1+ 用户：',
        '',
        '```bash',
        'python scripts/template_cloner.py --source <参考视频或链接> --id <new_template_id> --out templates-catalog',
        'python scripts/template_factory.py verify templates-catalog/<new_template_id>',
        '```',
        '',
    ]

    md_path = out_dir / 'discovery_report.md'
    md_path.write_text('\n'.join(lines), encoding='utf-8')
    res = {'json': json_path, 'markdown': md_path}
    if sheet_path is not None:
        res['contact_sheet'] = sheet_path
    return res

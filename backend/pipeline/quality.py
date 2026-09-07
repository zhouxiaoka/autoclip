"""
出片质量工程化：把「程序能算的事」从 LLM 手里拿回来。

- DurationProfile：按视频总时长选一组切片参数，并生成追加到提示词末尾的「本次任务参数」，
  覆盖提示词里为 60 分钟播客写死的「最小 90 秒 / 目标 3–6 分钟」（#59：5 分钟视频切出 3×2 分钟）。
- refine_timeline：把 LLM 给的时间区间对齐到字幕 cue 边界、施加时长上下限、去重合并，
  输出 quality_report 供回归集与前端使用。
- select_clips：评分筛选的兜底——阈值之上全留，不足 min_keep 按分补齐，超过 max_clips 截断（#11：切片为 0）。
- align_scores：评分结果数量与输入不一致时按 outline 对齐，不再整块丢弃。

全部是纯函数（除了 save_* 落盘），方便单测与 eval。
方案见 docs/QUALITY_AND_PUBLISH_PLAN.md。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

PROFILE_FILE = "duration_profile.json"
REPORT_FILE = "quality_report.json"


# ---------------------------------------------------------------- time helpers ---
def to_seconds(t: str) -> float:
    """'HH:MM:SS,mmm' / 'HH:MM:SS.mmm' / 'MM:SS' → 秒。格式错误抛 ValueError。"""
    s = str(t).strip().replace(",", ".")
    parts = s.split(":")
    if len(parts) == 3:
        h, m, sec = parts
    elif len(parts) == 2:
        h, (m, sec) = "0", parts
    else:
        raise ValueError(f"无效时间: {t}")
    return int(h) * 3600 + int(m) * 60 + float(sec)


def to_srt_time(sec: float) -> str:
    sec = max(0.0, float(sec))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms == 1000:
        s, ms = s + 1, 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ---------------------------------------------------------------- duration profile ---
@dataclass(frozen=True)
class DurationProfile:
    tier: str                 # short / medium / long
    total_sec: float
    min_clip_sec: float       # 低于此时长的片段要延长 / 合并 / 丢弃
    target_clip_sec: Tuple[float, float]  # 目标时长区间，写进提示词
    max_clip_sec: float       # 超过则按 cue 截断
    topics_hint: Tuple[int, int]          # 建议话题数（整条视频）
    min_keep: int             # 评分筛选后至少保留几条（有候选时）
    max_clips: int            # 最多保留几条
    snap_window_sec: float = 3.0   # 吸附到最近 cue 的搜索窗口
    merge_gap_sec: float = 5.0     # 太短且与相邻段间隔小于此则合并
    overlap_merge_ratio: float = 0.5  # 重叠超过较短者的这一比例 → 合并

    def prompt_hint(self) -> str:
        """追加到 step1 / step2 提示词末尾，覆盖提示词里写死的时长规则。"""
        lo, hi = self.target_clip_sec
        n_lo, n_hi = self.topics_hint
        total = f"{int(self.total_sec // 60)} 分 {int(self.total_sec % 60)} 秒"
        return (
            "\n\n---\n\n## 本次任务参数（优先级高于上文所有时长与数量规则）\n"
            f"- 视频总时长：{total}（{self.tier} 类型）\n"
            f"- 整条视频建议提取 {n_lo}–{n_hi} 个话题；话题之间不要重叠\n"
            f"- 每个片段目标时长 {_fmt_dur(lo)}–{_fmt_dur(hi)}，最短不少于 {_fmt_dur(self.min_clip_sec)}，最长不超过 {_fmt_dur(self.max_clip_sec)}\n"
            "- 上文中「至少 90 秒」「3–6 分钟」等具体数字一律以本节为准\n"
            "- 起止时间必须落在字幕行的边界上，直接引用字幕行的时间戳，不要自行推算\n"
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["target_clip_sec"] = list(self.target_clip_sec)
        d["topics_hint"] = list(self.topics_hint)
        return d


def _fmt_dur(sec: float) -> str:
    sec = int(round(sec))
    if sec < 60:
        return f"{sec} 秒"
    if sec % 60 == 0:
        return f"{sec // 60} 分钟"
    return f"{sec // 60} 分 {sec % 60} 秒"


def profile_for(total_sec: float) -> DurationProfile:
    """按总时长分档。数字是产品判断，不是实验结论——回归集起来后再调。"""
    total_sec = max(0.0, float(total_sec))
    if total_sec < 8 * 60:
        return DurationProfile(
            tier="short", total_sec=total_sec,
            min_clip_sec=20, target_clip_sec=(30, 90), max_clip_sec=150,
            topics_hint=(3, 6), min_keep=2, max_clips=6,
        )
    if total_sec < 30 * 60:
        return DurationProfile(
            tier="medium", total_sec=total_sec,
            min_clip_sec=45, target_clip_sec=(60, 180), max_clip_sec=300,
            topics_hint=(4, 10), min_keep=3, max_clips=10,
        )
    # 长视频：保持原有播客口径，但上限收紧到 8 分钟
    hours = total_sec / 3600
    return DurationProfile(
        tier="long", total_sec=total_sec,
        min_clip_sec=90, target_clip_sec=(120, 360), max_clip_sec=480,
        topics_hint=(max(6, int(6 * hours)), max(12, int(14 * hours))), min_keep=3, max_clips=max(12, int(16 * hours)),
    )


def profile_from_srt(srt_entries: Sequence[Dict[str, Any]]) -> DurationProfile:
    total = to_seconds(srt_entries[-1]["end_time"]) if srt_entries else 0.0
    return profile_for(total)


def save_profile(profile: DurationProfile, metadata_dir: Path) -> Path:
    path = Path(metadata_dir) / PROFILE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_profile(metadata_dir: Path) -> Optional[DurationProfile]:
    path = Path(metadata_dir) / PROFILE_FILE
    if not path.exists():
        return None
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        d["target_clip_sec"] = tuple(d["target_clip_sec"])
        d["topics_hint"] = tuple(d["topics_hint"])
        return DurationProfile(**d)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"读取 {PROFILE_FILE} 失败: {e}")
        return None


def excerpt_between(srt_entries: Sequence[Dict[str, Any]], start: float, end: float, max_chars: int = 600) -> str:
    """截取时间范围内的转写原文，给评分 / 标题用。"""
    parts: List[str] = []
    for e in srt_entries:
        try:
            s, t = to_seconds(e["start_time"]), to_seconds(e["end_time"])
        except (KeyError, ValueError):
            continue
        if t >= start and s <= end:
            text = str(e.get("text") or "").strip()
            if text:
                parts.append(text)
    return " ".join(parts)[:max_chars]


def load_srt_chunks(metadata_dir: Path) -> List[Dict[str, Any]]:
    """step1 落盘的 SRT 块拼回完整 cue 列表（按块序号）。"""
    chunks_dir = Path(metadata_dir) / "step1_srt_chunks"
    if not chunks_dir.exists():
        return []
    entries: List[Dict[str, Any]] = []
    files = sorted(chunks_dir.glob("chunk_*.json"), key=lambda p: int(p.stem.split("_")[1]) if p.stem.split("_")[1].isdigit() else 0)
    for f in files:
        try:
            entries.extend(json.loads(f.read_text(encoding="utf-8")))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"读取 {f} 失败: {e}")
    return entries


# ---------------------------------------------------------------- refine timeline ---
@dataclass
class _Cue:
    start: float
    end: float
    text: str


def _cues(srt_entries: Sequence[Dict[str, Any]]) -> List[_Cue]:
    out: List[_Cue] = []
    for e in srt_entries:
        try:
            s, t = to_seconds(e["start_time"]), to_seconds(e["end_time"])
        except (KeyError, ValueError):
            continue
        if t < s:
            s, t = t, s
        out.append(_Cue(s, t, str(e.get("text", ""))))
    out.sort(key=lambda c: c.start)
    return out


def _snap_start(sec: float, cues: List[_Cue], window: float) -> Tuple[float, int]:
    """吸附到最近 cue 的 start；窗口内没有则取包含该时刻（或其后第一条）的 cue。返回 (时间, cue 下标)。"""
    if not cues:
        return sec, -1
    best_i, best_d = -1, float("inf")
    for i, c in enumerate(cues):
        d = abs(c.start - sec)
        if d < best_d:
            best_i, best_d = i, d
        if c.start > sec + window:
            break
    if best_d <= window:
        return cues[best_i].start, best_i
    for i, c in enumerate(cues):
        if c.end >= sec:
            return c.start, i
    return cues[-1].start, len(cues) - 1


def _snap_end(sec: float, cues: List[_Cue], window: float) -> Tuple[float, int]:
    if not cues:
        return sec, -1
    best_i, best_d = -1, float("inf")
    for i, c in enumerate(cues):
        d = abs(c.end - sec)
        if d < best_d:
            best_i, best_d = i, d
        if c.start > sec + window:
            break
    if best_d <= window:
        return cues[best_i].end, best_i
    for i in range(len(cues) - 1, -1, -1):
        if cues[i].start <= sec:
            return cues[i].end, i
    return cues[0].end, 0


def _extend_to_min(start: float, end_i: int, cues: List[_Cue], min_sec: float, limit: float) -> Tuple[float, int]:
    """沿 cue 向后延长，直到时长 ≥ min_sec 或撞到 limit（下一段起点 / 视频末尾）。"""
    i = end_i
    end = cues[i].end if 0 <= i < len(cues) else start
    while end - start < min_sec and i + 1 < len(cues) and cues[i + 1].end <= limit + 1e-6:
        i += 1
        end = cues[i].end
    return end, i


def _trim_to_max(start: float, end_i: int, cues: List[_Cue], max_sec: float) -> Tuple[float, int]:
    i = end_i
    end = cues[i].end if 0 <= i < len(cues) else start
    while end - start > max_sec and i > 0 and cues[i - 1].end > start:
        i -= 1
        end = cues[i].end
    return end, i


def refine_timeline(items: Sequence[Dict[str, Any]], srt_entries: Sequence[Dict[str, Any]],
                    profile: Optional[DurationProfile] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    对 step2 的时间区间做程序化校正。返回 (校正后的列表, 质量报告)。

    每条 item 需要 start_time / end_time（SRT 格式），其余字段原样保留；会补 `duration_sec`、
    `refine` 字段（原始区间与做过的操作）。
    """
    cues = _cues(srt_entries)
    if profile is None:
        profile = profile_for(cues[-1].end if cues else 0)
    video_end = cues[-1].end if cues else None

    report: Dict[str, Any] = {
        "profile": profile.to_dict(),
        "input": len(items),
        "snap_offsets_sec": [],
        "dropped": [],
        "merged": [],
        "extended": 0,
        "trimmed": 0,
    }

    # 1) 解析 + 吸附
    parsed: List[Dict[str, Any]] = []
    for raw in items:
        it = dict(raw)
        try:
            s0, e0 = to_seconds(it["start_time"]), to_seconds(it["end_time"])
        except (KeyError, ValueError, TypeError):
            report["dropped"].append({"outline": _title(it), "reason": "时间格式无效"})
            continue
        if e0 <= s0:
            report["dropped"].append({"outline": _title(it), "reason": "结束早于开始"})
            continue
        ops: List[str] = []
        if cues:
            s, si = _snap_start(s0, cues, profile.snap_window_sec)
            e, ei = _snap_end(e0, cues, profile.snap_window_sec)
            if ei < si:
                ei = si
                e = cues[ei].end
            report["snap_offsets_sec"].append(round(abs(s - s0), 3))
            report["snap_offsets_sec"].append(round(abs(e - e0), 3))
            if abs(s - s0) > 0.001 or abs(e - e0) > 0.001:
                ops.append("snap")
        else:
            s, e, si, ei = s0, e0, -1, -1
        it.update({"_s": s, "_e": e, "_si": si, "_ei": ei, "_ops": ops, "_orig": (it["start_time"], it["end_time"])})
        parsed.append(it)

    parsed.sort(key=lambda x: (x["_s"], x["_e"]))

    # 2) 去重 / 合并重叠
    merged: List[Dict[str, Any]] = []
    for it in parsed:
        if merged:
            prev = merged[-1]
            overlap = min(prev["_e"], it["_e"]) - max(prev["_s"], it["_s"])
            shorter = max(1e-6, min(prev["_e"] - prev["_s"], it["_e"] - it["_s"]))
            if overlap > 0 and overlap / shorter >= profile.overlap_merge_ratio:
                _merge_into(prev, it)
                report["merged"].append({"kept": _title(prev), "absorbed": _title(it), "reason": f"重叠 {overlap:.1f}s"})
                continue
            if overlap > 0 and cues:
                # 小重叠：后者起点推到前者终点之后的第一条 cue
                ni = prev["_ei"] + 1
                if ni < len(cues) and cues[ni].start < it["_e"]:
                    it["_s"], it["_si"] = cues[ni].start, ni
                    it["_ops"].append("shift_start")
                else:
                    _merge_into(prev, it)
                    report["merged"].append({"kept": _title(prev), "absorbed": _title(it), "reason": "重叠且无法后移"})
                    continue
        merged.append(it)

    # 3) 时长下限 / 上限（在 cue 边界上）
    if cues:
        for idx, it in enumerate(merged):
            limit = merged[idx + 1]["_s"] if idx + 1 < len(merged) else video_end
            dur = it["_e"] - it["_s"]
            if dur < profile.min_clip_sec:
                e, ei = _extend_to_min(it["_s"], it["_ei"], cues, profile.min_clip_sec, limit)
                if e > it["_e"]:
                    it["_e"], it["_ei"] = e, ei
                    it["_ops"].append("extend")
                    report["extended"] += 1
            dur = it["_e"] - it["_s"]
            if dur > profile.max_clip_sec:
                e, ei = _trim_to_max(it["_s"], it["_ei"], cues, profile.max_clip_sec)
                if e < it["_e"]:
                    it["_e"], it["_ei"] = e, ei
                    it["_ops"].append("trim")
                    report["trimmed"] += 1

        # 4) 仍然太短：与相邻段合并（间隔小）或丢弃
        result: List[Dict[str, Any]] = []
        for it in merged:
            if it["_e"] - it["_s"] >= profile.min_clip_sec:
                result.append(it)
                continue
            if result and it["_s"] - result[-1]["_e"] <= profile.merge_gap_sec \
                    and (it["_e"] - result[-1]["_s"]) <= profile.max_clip_sec:
                _merge_into(result[-1], it)
                report["merged"].append({"kept": _title(result[-1]), "absorbed": _title(it), "reason": "过短，并入前一段"})
            else:
                report["dropped"].append({"outline": _title(it), "reason": f"过短（{it['_e'] - it['_s']:.0f}s < {profile.min_clip_sec:.0f}s）且无法合并"})
        merged = result

    # 5) 收尾：写回字段、重新编号
    out: List[Dict[str, Any]] = []
    durations: List[float] = []
    for i, it in enumerate(merged, 1):
        s, e = it.pop("_s"), it.pop("_e")
        it.pop("_si", None); it.pop("_ei", None)
        ops = it.pop("_ops"); orig = it.pop("_orig")
        it["start_time"] = to_srt_time(s)
        it["end_time"] = to_srt_time(e)
        it["duration_sec"] = round(e - s, 3)
        it["id"] = str(i)
        it["refine"] = {"original": {"start_time": orig[0], "end_time": orig[1]}, "ops": ops}
        durations.append(e - s)
        out.append(it)

    report["output"] = len(out)
    report["durations_sec"] = [round(d, 1) for d in durations]
    if durations:
        report["duration_stats"] = {
            "min": round(min(durations), 1), "max": round(max(durations), 1),
            "mean": round(sum(durations) / len(durations), 1),
        }
    if video_end:
        covered = sum(durations)
        report["coverage"] = round(min(1.0, covered / video_end), 3)
    if report["snap_offsets_sec"]:
        so = sorted(report["snap_offsets_sec"])
        report["snap_offset_p50"] = so[len(so) // 2]
        report["snap_offset_p90"] = so[min(len(so) - 1, int(len(so) * 0.9))]
    return out, report


def _title(it: Dict[str, Any]) -> str:
    o = it.get("outline") or it.get("title") or ""
    if isinstance(o, dict):
        o = o.get("title", "")
    return str(o)[:60]


def _merge_into(keep: Dict[str, Any], absorbed: Dict[str, Any]) -> None:
    keep["_s"] = min(keep["_s"], absorbed["_s"])
    keep["_e"] = max(keep["_e"], absorbed["_e"])
    keep["_si"] = min(keep["_si"], absorbed["_si"])
    keep["_ei"] = max(keep["_ei"], absorbed["_ei"])
    keep["_ops"].append("merge")
    kc, ac = keep.get("content"), absorbed.get("content")
    if isinstance(kc, list) and isinstance(ac, list):
        keep["content"] = kc + [x for x in ac if x not in kc]
    elif isinstance(kc, str) and isinstance(ac, str) and ac and ac not in kc:
        keep["content"] = f"{kc} {ac}".strip()
    at = _title(absorbed)
    if at and at not in _title(keep):
        keep["merged_outlines"] = keep.get("merged_outlines", []) + [at]


def save_report(report: Dict[str, Any], metadata_dir: Path) -> Path:
    path = Path(metadata_dir) / REPORT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: Dict[str, Any] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            existing = {}
    existing.update(report)
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------- scoring guards ---
def align_scores(clips: Sequence[Dict[str, Any]], llm_results: Any,
                 default_score: float = 0.5) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    把 LLM 的评分结果合并回 clips。数量一致按序对齐；不一致按 outline 文本对齐；
    对不上的给 default_score + 「未评分（自动兜底）」。返回 (clips, {matched, fallback})。
    """
    stats = {"matched": 0, "fallback": 0}
    results = llm_results if isinstance(llm_results, list) else []
    by_outline: Dict[str, Dict[str, Any]] = {}
    for r in results:
        if isinstance(r, dict):
            key = _norm(r.get("outline") or r.get("title") or "")
            if key and key not in by_outline:
                by_outline[key] = r

    out: List[Dict[str, Any]] = []
    for i, clip in enumerate(clips):
        c = dict(clip)
        r = None
        if len(results) == len(clips) and isinstance(results[i], dict):
            r = results[i]
        else:
            r = by_outline.get(_norm(_title(c)))
        score = _to_score(r.get("final_score")) if r else None
        if score is None:
            c["final_score"] = default_score
            c["recommend_reason"] = (r or {}).get("recommend_reason") or "未评分（自动兜底）"
            c["score_source"] = "fallback"
            stats["fallback"] += 1
        else:
            c["final_score"] = score
            c["recommend_reason"] = r.get("recommend_reason") or ""
            c["score_source"] = "llm"
            stats["matched"] += 1
        out.append(c)
    return out, stats


def _norm(s: Any) -> str:
    return "".join(str(s).split()).lower()[:80]


def _to_score(v: Any) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f > 1.0:  # 有的模型会给 0–10 / 0–100
        f = f / 10 if f <= 10 else f / 100
    return round(max(0.0, min(1.0, f)), 2)


def select_clips(scored: Sequence[Dict[str, Any]], threshold: float,
                 profile: Optional[DurationProfile] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    阈值之上全留；不足 min_keep 按分补齐（标 selected_by=fallback）；超过 max_clips 按分截断。
    返回顺序按 id（时间序）。
    """
    min_keep = profile.min_keep if profile else 2
    max_clips = profile.max_clips if profile else 12
    items = [dict(c) for c in scored]
    ranked = sorted(items, key=lambda c: float(c.get("final_score") or 0), reverse=True)

    chosen = [c for c in ranked if float(c.get("final_score") or 0) >= threshold]
    for c in chosen:
        c["selected_by"] = "threshold"
    fallback = 0
    if len(chosen) < min_keep:
        for c in ranked:
            if len(chosen) >= min_keep:
                break
            if c in chosen:
                continue
            c["selected_by"] = "fallback"
            chosen.append(c)
            fallback += 1
    truncated = 0
    if len(chosen) > max_clips:
        truncated = len(chosen) - max_clips
        chosen = sorted(chosen, key=lambda c: float(c.get("final_score") or 0), reverse=True)[:max_clips]

    chosen.sort(key=lambda c: _id_key(c.get("id")))
    info = {
        "threshold": threshold, "candidates": len(items), "selected": len(chosen),
        "fallback_selected": fallback, "truncated": truncated, "min_keep": min_keep, "max_clips": max_clips,
    }
    return chosen, info


def _id_key(v: Any) -> Tuple[int, str]:
    try:
        return (int(v), "")
    except (TypeError, ValueError):
        return (1 << 30, str(v))

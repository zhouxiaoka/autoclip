"""对一条校正后的时间线算回归指标。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.pipeline.quality import to_seconds


def compute_metrics(clips: List[Dict[str, Any]], expect: Dict[str, Any],
                    video_sec: Optional[float] = None) -> Dict[str, Any]:
    n = len(clips)
    durs = []
    for c in clips:
        if "duration_sec" in c:
            durs.append(float(c["duration_sec"]))
        else:
            try:
                durs.append(to_seconds(c["end_time"]) - to_seconds(c["start_time"]))
            except (KeyError, ValueError, TypeError):
                continue
    covered = sum(durs)
    checks = {
        "clips_min": n >= expect.get("clips_min", 0),
        "clips_max": n <= expect.get("clips_max", 10**9),
        "must_not_zero": n > 0 if expect.get("must_not_zero", True) else True,
        "duration_min": all(d >= expect.get("duration_min", 0) for d in durs) if durs else n == 0,
        "duration_max": all(d <= expect.get("duration_max", 10**9) for d in durs) if durs else True,
    }
    if expect.get("coverage_min") is not None and video_sec:
        checks["coverage_min"] = (covered / video_sec) >= float(expect["coverage_min"])
    return {
        "n": n,
        "durations": [round(d, 1) for d in durs],
        "coverage": round(covered / video_sec, 3) if video_sec else None,
        "checks": checks,
        "ok": all(checks.values()),
    }

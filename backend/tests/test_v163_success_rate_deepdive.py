"""v1.6.3 success-rate deep-dive regressions:
1. file_lock.acquire retries transient Windows PermissionError on open() instead of failing immediately,
   and uses a 25s default timeout for multi-project / batch-import concurrency (PYTHON-FASTAPI-60).
2. intelligence.sample() falls back to accurate seek (-i before -ss) when fast input seek (-ss before -i)
   fails or produces an empty frame on OBS/VFR/sparse-keyframe recordings (PYTHON-FASTAPI-88).
3. game_highlights.verify_reaction() tolerates single-dict events and '12.5s'/'0:12' timestamps and
   returns None instead of crashing the pipeline on malformed optional recovery responses (PYTHON-FASTAPI-7F/87).
"""
from __future__ import annotations

import builtins
import subprocess
from pathlib import Path

from backend.core import file_lock
from backend.services.studio import game_highlights, intelligence


def test_file_lock_retries_transient_permission_error_on_open(monkeypatch, tmp_path: Path):
    assert file_lock.DEFAULT_TIMEOUT >= 25.0
    lock_path = tmp_path / "studio.lock"
    real_open = builtins.open
    attempts = {"count": 0}

    def flaky_open(path, mode="r", *args, **kwargs):
        if Path(path) == lock_path and attempts["count"] < 2:
            attempts["count"] += 1
            raise PermissionError("WinError 32 transient lock")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", flaky_open)
    handle = file_lock.acquire(lock_path, timeout=2.0)
    try:
        assert attempts["count"] == 2
    finally:
        file_lock.release(handle)


def test_intelligence_sample_falls_back_to_accurate_seek_on_empty_fast_seek(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(intelligence, "_sampling_bounds", lambda video: (120.0, 0.5))
    monkeypatch.setattr(intelligence, "get_ffmpeg_path", lambda: "ffmpeg")
    seen_cmds: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        seen_cmds.append(list(cmd))
        out_path = Path(cmd[-1])
        # Fast seek has -ss before -i -> simulate 0-byte empty output on VFR/OBS recording
        if cmd.index("-ss") < cmd.index("-i"):
            out_path.write_bytes(b"")
        else:
            out_path.write_bytes(b"\xff\xd8\xff\xd9")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(intelligence.subprocess, "run", fake_run)
    content = intelligence.sample(tmp_path / "obs.mkv", [15.0], tmp_path)
    assert len(content) == 2
    assert len(seen_cmds) == 2
    assert seen_cmds[0].index("-ss") < seen_cmds[0].index("-i")
    assert seen_cmds[1].index("-i") < seen_cmds[1].index("-ss")


def test_game_highlights_verify_reaction_tolerates_dict_and_string_timestamps(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(intelligence, "sample", lambda video, times, folder: [])
    monkeypatch.setattr(
        intelligence,
        "vision_call_at",
        lambda stage, payload: {
            "events": {
                "action": "12.5s",
                "reaction": "0:18",
                "label": "绝杀反杀",
                "evidence": "12.5s 躲避技能后 18s 击杀对手",
            }
        },
    )
    scene = game_highlights.verify_reaction(tmp_path / "game.mp4", at=18.0, duration=60.0, target=15.0)
    assert scene is not None
    assert scene.label == "绝杀反杀"
    assert scene.start < scene.end


def test_game_highlights_verify_reaction_returns_none_on_malformed_response(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(intelligence, "sample", lambda video, times, folder: [])
    monkeypatch.setattr(intelligence, "vision_call_at", lambda stage, payload: {"unexpected": "shape"})
    assert game_highlights.verify_reaction(tmp_path / "game.mp4", at=18.0, duration=60.0, target=15.0) is None

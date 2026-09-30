"""Detect subtitles already burned into the source picture, locally and without OCR.

Burned subtitles look like bright glyphs with a dark outline or shadow in the lower part of the
frame, and their shape changes every few seconds. Static overlays such as channel logos stay put,
so requiring the text mask to change between samples keeps them from counting.
"""
from __future__ import annotations

import statistics
import subprocess
from itertools import pairwise
from pathlib import Path

from backend.services import render_limits
from backend.utils.ffmpeg_utils import get_ffmpeg_path

BAND_WIDTH, BAND_HEIGHT = 320, 64
SAMPLES = 12
BRIGHT, DARK, REACH = 200, 80, 2
MIN_TEXT_FRACTION = 0.004      # share of band pixels that look like outlined glyphs
MIN_FRAMES_WITH_TEXT = 0.6     # most samples must carry text
MAX_MEDIAN_OVERLAP = 0.5       # text must change between samples (logos do not)


def _band(video: Path, at: float) -> bytes | None:
    cmd = [
        get_ffmpeg_path(), '-v', 'error', '-ss', f'{at:.2f}', '-i', str(video), '-frames:v', '1',
        '-vf', f'crop=iw:ih*0.35:0:ih*0.65,scale={BAND_WIDTH}:{BAND_HEIGHT},format=gray',
        '-f', 'rawvideo', '-',
    ]
    cmd, priority = render_limits.low_priority(cmd)
    proc = subprocess.run(cmd, capture_output=True, timeout=30, check=False, **priority)
    data = proc.stdout
    return data if proc.returncode == 0 and len(data) == BAND_WIDTH * BAND_HEIGHT else None


def text_mask(pixels: bytes) -> set[int]:
    """Indexes of bright pixels that sit next to a dark pixel on the same row (outlined glyphs)."""
    mask = set()
    for y in range(BAND_HEIGHT):
        row = pixels[y * BAND_WIDTH:(y + 1) * BAND_WIDTH]
        for x, value in enumerate(row):
            if value < BRIGHT:
                continue
            lo, hi = max(0, x - REACH), min(BAND_WIDTH, x + REACH + 1)
            if min(row[lo:hi]) < DARK:
                mask.add(y * BAND_WIDTH + x)
    return mask


def decide(masks: list[set[int]]) -> bool:
    if not masks:
        return False
    threshold = MIN_TEXT_FRACTION * BAND_WIDTH * BAND_HEIGHT
    texty = [mask for mask in masks if len(mask) >= threshold]
    if len(texty) < MIN_FRAMES_WITH_TEXT * len(masks) or len(texty) < 3:
        return False
    overlaps = [len(a & b) / max(1, len(a | b)) for a, b in pairwise(texty)]
    return statistics.median(overlaps) < MAX_MEDIAN_OVERLAP


def has_burned_subtitles(video: Path, duration: float) -> bool:
    if duration <= 0:
        return False
    start, span = duration * 0.05, duration * 0.9
    times = [start + span * (i + 0.5) / SAMPLES for i in range(SAMPLES)]
    masks = [text_mask(band) for band in (_band(video, t) for t in times) if band]
    return decide(masks)

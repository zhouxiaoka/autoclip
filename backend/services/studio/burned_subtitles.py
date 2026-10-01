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

BAND_WIDTH, BAND_HEIGHT = 960, 192  # thin outline-free captions (e.g. Bilibili interviews) vanish when shrunk further
SAMPLES = 12
BRIGHT, DARK, REACH = 200, 80, 2
MIN_TEXT_FRACTION = 0.0012     # share of band pixels that look like glyphs on a darker edge
MIN_FRAMES_WITH_TEXT = 0.6     # most samples must carry text
MAX_MEDIAN_OVERLAP = 0.5       # text must change between samples (logos do not)
EDGE = 0.15                    # captions are centred; corner logos and watermarks live in the outer 15 %


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
    left, right = int(BAND_WIDTH * EDGE), int(BAND_WIDTH * (1 - EDGE))
    for y in range(BAND_HEIGHT):
        row = pixels[y * BAND_WIDTH:(y + 1) * BAND_WIDTH]
        for x, value in enumerate(row):
            if value < BRIGHT or x < left or x >= right:
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


def caption_band(masks: list[set[int]]) -> tuple[float, float] | None:
    """(top, bottom) of the caption lines as fractions of the frame height, with a little margin.

    The sampled band is the bottom 35 % of the frame; rows come from the glyph pixels of the
    frames that carry text, trimmed of stray outliers.
    """
    threshold = MIN_TEXT_FRACTION * BAND_WIDTH * BAND_HEIGHT
    rows = sorted(index // BAND_WIDTH for mask in masks if len(mask) >= threshold for index in mask)
    if not rows:
        return None
    low, high = rows[int(len(rows) * .03)], rows[min(len(rows) - 1, int(len(rows) * .97))]
    top = 0.65 + 0.35 * low / BAND_HEIGHT - 0.02
    bottom = 0.65 + 0.35 * (high + 1) / BAND_HEIGHT + 0.02
    return round(max(0.6, top), 4), round(min(1.0, bottom), 4)


def detect(video: Path, duration: float) -> tuple[bool, tuple[float, float] | None]:
    """(has burned captions, where they sit) from one sampling pass."""
    if duration <= 0:
        return False, None
    start, span = duration * 0.05, duration * 0.9
    times = [start + span * (i + 0.5) / SAMPLES for i in range(SAMPLES)]
    masks = [text_mask(band) for band in (_band(video, t) for t in times) if band]
    found = decide(masks)
    return found, caption_band(masks) if found else None


def has_burned_subtitles(video: Path, duration: float) -> bool:
    return detect(video, duration)[0]

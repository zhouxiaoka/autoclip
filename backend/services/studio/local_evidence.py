"""Bounded local subtitle evidence, without model calls or transcription."""
from pathlib import Path
import pysrt

MAX_SUBTITLE_BYTES = 256 * 1024


def inspect_subtitles(video: Path, duration: float):
    path = video.parent / 'input.srt'
    evidence = {'subtitle_status': 'missing', 'valid_cues': 0, 'covered_seconds': 0.0}
    try:
        with path.open('rb') as stream:
            raw = stream.read(MAX_SUBTITLE_BYTES + 1)
    except FileNotFoundError:
        return evidence
    except OSError:
        return {**evidence, 'subtitle_status': 'unreadable'}
    if len(raw) > MAX_SUBTITLE_BYTES:
        return {**evidence, 'subtitle_status': 'too_large'}
    try:
        cues = pysrt.from_string(raw.decode('utf-8-sig'))
    except (ValueError, UnicodeError):
        return {**evidence, 'subtitle_status': 'invalid'}
    ranges = sorted({(cue.start.ordinal / 1000, cue.end.ordinal / 1000)
                    for cue in cues if cue.text.strip() and
                    0 <= cue.start.ordinal / 1000 < cue.end.ordinal / 1000 <= duration})
    if not ranges:
        return {**evidence, 'subtitle_status': 'invalid'}
    covered = 0.0
    end = 0.0
    for start, stop in ranges:
        covered += max(0, stop - max(start, end))
        end = max(end, stop)
    return {'subtitle_status': 'available', 'valid_cues': len(ranges), 'covered_seconds': round(covered, 3)}

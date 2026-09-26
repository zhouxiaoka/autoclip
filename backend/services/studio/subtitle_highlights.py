"""Adapt this run's scored subtitle ranges without another model request."""
import math
import uuid
from backend.services.studio.models import Draft, Scene
from backend.services.studio.intelligence import validate_scenes
from backend.utils.text_processor import TextProcessor


def make_highlights(clips, preferences, source_duration):
    ranked = []
    for clip in clips:
        try:
            score = float(clip.get('final_score', 0))
            if not math.isfinite(score):
                continue
            scene = Scene(id=uuid.uuid4().hex,
                label=str(clip.get('generated_title') or clip.get('outline') or '字幕高光')[:120],
                start=TextProcessor.time_to_seconds(clip['start_time']),
                end=TextProcessor.time_to_seconds(clip['end_time']))
            validate_scenes([scene], source_duration)
            ranked.append((score, scene))
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
    ranked.sort(key=lambda row: row[0], reverse=True)
    selected = []
    for _, scene in ranked:
        # Preserve whole semantic ranges, removing duplicate/mostly overlapping candidates.
        if any(max(0, min(scene.end, old.end)-max(scene.start, old.start)) /
               min(scene.end-scene.start, old.end-old.start) > .8 for old in selected):
            continue
        selected.append(scene)
        if len(selected) == 6:
            break
    if not selected:
        raise ValueError('没有可用的字幕高光，请检查字幕与选段结果；原素材已保留')
    return [Draft(id=uuid.uuid4().hex, title=s.label, scenes=[s], origin='subtitle-highlight',
        language=preferences.language, aspect=preferences.aspect,
        layout='crop' if preferences.aspect == 'portrait' else 'fit', subtitles=True).model_dump()
        for s in selected]

"""1.5.8 transcription gate for async endpoints (R23 #230).

The gate may run ffprobe (30 s timeout) and, when ffprobe has no duration, an ffmpeg decode (up to 180 s), so
every async endpoint runs it in the threadpool through here, never on the event loop. A refusal becomes the
one coded 422 (``gate_refusal``)."""
from starlette.concurrency import run_in_threadpool

from backend.api.v1.gate_errors import gate_refusal


async def _run(fn, *args, **kwargs) -> None:
    from backend.services.studio import readiness
    try:
        await run_in_threadpool(fn, *args, **kwargs)
    except readiness.TranscriptionNotReady as exc:
        raise gate_refusal(exc) from exc


async def for_project(project_id: str) -> None:
    from backend.services.studio import readiness
    await _run(readiness.ensure_local_transcription_for_project, project_id)


async def for_paths(video, srt=None, **kwargs) -> None:
    from backend.services.studio import readiness
    await _run(readiness.ensure_local_transcription_for_paths, video, srt, **kwargs)

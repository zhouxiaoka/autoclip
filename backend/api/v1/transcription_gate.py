"""Async HTTP entries of the one preflight (``backend.services.studio.preflight``): protocol conversion only.

The whole preflight runs in the threadpool (``run``); a refusal is the one coded 422. The HTTP shape lives here in
the API layer, so the service layer never imports the API layer (#354)."""
from starlette.concurrency import run_in_threadpool

from backend.services.studio import preflight, readiness

from .gate_errors import gate_refusal


async def run(inputs: preflight.ResolvedInputs, **kwargs) -> preflight.PreflightResult:
    """The whole preflight off the event loop; refusals become the one coded 422."""
    try:
        return await run_in_threadpool(preflight.check, inputs, **kwargs)
    except (preflight.SourceRejected, readiness.TranscriptionNotReady) as exc:
        raise gate_refusal(exc) from exc


async def for_project(project_id: str) -> None:
    inputs = preflight.project_inputs(project_id)
    if inputs is not None:
        await run(inputs)


async def for_paths(video, srt=None, **kwargs) -> None:
    inputs = preflight.path_inputs(video, srt, **kwargs)
    if inputs is not None:
        await run(inputs)

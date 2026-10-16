"""Async HTTP entries of the one preflight (``backend.services.studio.preflight``): protocol conversion only.

The whole preflight runs in the threadpool (``preflight.run_async``); a refusal is the one coded 422."""
from backend.services.studio import preflight


async def for_project(project_id: str) -> None:
    inputs = preflight.project_inputs(project_id)
    if inputs is not None:
        await preflight.run_async(inputs)


async def for_paths(video, srt=None, **kwargs) -> None:
    inputs = preflight.path_inputs(video, srt, **kwargs)
    if inputs is not None:
        await preflight.run_async(inputs)

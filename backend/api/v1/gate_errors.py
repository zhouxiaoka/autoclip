"""1.5.7 import gate: the one HTTP shape of a refusal (422 with a stable ``code``, / )."""
from fastapi import HTTPException


def gate_refusal(exc) -> HTTPException:
    return HTTPException(422, exc.detail)

"""A2-1/A2-2: map DownloadError / ValidationError text to named studio codes."""
from __future__ import annotations

import pytest


def test_a2_1_classify_download_error_text_maps_known_phrases():
    from backend.utils.download_recovery import SOURCE_UNSUPPORTED_CODE, classify_download_error_text
    code, _hint = classify_download_error_text('Unsupported URL: https://example.com/x')
    assert code == SOURCE_UNSUPPORTED_CODE
    code2, _ = classify_download_error_text('ERROR: Unsupported URL')
    assert code2 == SOURCE_UNSUPPORTED_CODE
    assert classify_download_error_text('') is None


def test_a2_1_download_error_becomes_pipeline_failure_not_unexpected():
    """Regression: unclassified DownloadError used to land as unexpected; mapped code does not."""
    from backend.core.sentry_setup import studio_error_code
    from backend.core.failure_attribution import unexpected_type_of
    from backend.pipeline.failures import PipelineFailure
    from backend.utils import download_recovery as dr

    class DownloadError(Exception):
        pass

    err = DownloadError('ERROR: Unsupported URL: https://x.test/watch')
    mapped = dr.classify_download_error_text(str(err))
    assert mapped is not None
    code, hint = mapped
    assert code == dr.SOURCE_UNSUPPORTED_CODE
    wrapped = PipelineFailure('INGEST', hint, code=code)
    assert studio_error_code(wrapped) == code
    assert unexpected_type_of(err) == 'DownloadError'
    # Raw DownloadError stays unexpected until wrapped — that is the pre-fix baseline.
    assert studio_error_code(err) == 'unexpected'


def test_a2_2_pydantic_validation_error_unexpected_type_is_named():
    from backend.core.failure_attribution import unexpected_type_of
    try:
        from pydantic import BaseModel, ValidationError
    except ImportError:
        pytest.skip('pydantic missing')

    class Row(BaseModel):
        score: float

    with pytest.raises(ValidationError) as caught:
        Row.model_validate({'score': 'nope'})
    assert unexpected_type_of(caught.value) == 'ValidationError'

"""A2-1/A2-2: map DownloadError / ValidationError text to named studio codes."""
from __future__ import annotations

import json

import pytest


def test_observe_download_failure_splits_network_from_source_without_echoing_text():
    from backend.utils.download_failure_observe import observe_download_failure
    unavailable = observe_download_failure('ERROR: [youtube] abc: This video is unavailable https://youtu.be/secret')
    assert unavailable == {'token': 'unavailable', 'code': 'source_not_found'}
    sign_in = observe_download_failure('ERROR: Private video. Sign in if you have access https://youtu.be/secret')
    assert sign_in == {'token': 'sign_in', 'code': 'source_blocked'}
    timeout = observe_download_failure('ERROR: timed out https://example.invalid/watch')
    assert timeout == {'token': 'timeout', 'code': 'connection'}
    dns = observe_download_failure('ERROR: getaddrinfo failed')
    assert dns == {'token': 'dns', 'code': 'connection'}
    assert observe_download_failure('something else') == {'token': 'unmatched', 'code': None}
    for row in (unavailable, sign_in, timeout, dns):
        assert 'http' not in json.dumps(row)
        assert 'secret' not in json.dumps(row)


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


def test_n5_frame_wins_over_connection_timeout():
    """ffmpeg/postprocess timeouts must be frame_extract_failed, not connection."""
    from backend.utils.download_recovery import classify_download_error_text
    code, _ = classify_download_error_text('ERROR: Postprocessing: ffmpeg timed out')
    assert code == 'frame_extract_failed'
    code2, _ = classify_download_error_text('ERROR: Unable to merge formats: ffmpeg exited with timeout')
    assert code2 == 'frame_extract_failed'
    # Plain network timeout still maps to connection
    code3, _ = classify_download_error_text('ERROR: Unable to download webpage: timed out')
    assert code3 == 'connection'


def test_n5_bare_404_ssl_merge_not_overmatched():
    from backend.utils.download_recovery import classify_download_error_text
    # Tight 404 contexts still map
    assert classify_download_error_text('HTTP Error 404: Not Found')[0] == 'source_not_found'
    assert classify_download_error_text('ERROR: video unavailable')[0] == 'source_not_found'
    # Mac A2-5 @ 81fb3048: yt-dlp deleted watch uses intervening "is"
    assert classify_download_error_text('ERROR: [youtube] dead: This video is unavailable')[0] == 'source_not_found'
    assert classify_download_error_text('ERROR: Video unavailable. This video is unavailable')[0] == 'source_not_found'
    # Bare digit soup / unrelated text must not trip on loose '404' / 'ssl' / 'merge'
    assert classify_download_error_text('clip id 40401 failed for unknown reason') is None
    assert classify_download_error_text('passlen mismatch') is None  # contains no ssl:
    assert classify_download_error_text('emergency stop') is None
    # Real SSL / merge phrases still map
    assert classify_download_error_text('ERROR: [SSL: CERTIFICATE_VERIFY_FAILED]')[0] == 'connection'
    assert classify_download_error_text('ERROR: Unable to merge the formats')[0] == 'frame_extract_failed'


def test_ingest_connection_sentence_is_not_the_model_service_sentence():
    """A download timeout stays code connection, with a sentence that is not about models."""
    from pathlib import Path
    from backend.core.failure_codes import sentence
    from backend.utils.download_failure_observe import INGEST_CONNECTION_MESSAGE, observe_download_failure
    from backend.utils.download_recovery import classify_download_error_text

    code, hint = classify_download_error_text('ERROR: timed out')
    assert code == 'connection'
    assert hint == INGEST_CONNECTION_MESSAGE
    assert hint != sentence('connection')
    assert '模型' not in hint
    assert '登录' not in hint
    assert '删除' not in hint
    dns_code, dns_hint = classify_download_error_text('ERROR: getaddrinfo failed')
    assert dns_code == 'connection' and dns_hint == INGEST_CONNECTION_MESSAGE
    assert classify_download_error_text('ERROR: This video is unavailable')[0] == 'source_not_found'
    assert classify_download_error_text('ERROR: Private video')[0] == 'source_blocked'
    assert observe_download_failure('ERROR: timed out')['code'] == 'connection'
    root = Path(__file__).resolve().parents[2] / 'frontend' / 'src' / 'i18n' / 'locales'
    catalogs = {lang: json.loads((root / f'{lang}.json').read_text(encoding='utf-8')) for lang in ('zh', 'en', 'ja', 'ko', 'es', 'pt', 'ru', 'fr')}
    assert catalogs['zh'][INGEST_CONNECTION_MESSAGE] == INGEST_CONNECTION_MESSAGE
    translations = {catalogs[lang][INGEST_CONNECTION_MESSAGE] for lang in catalogs}
    assert len(translations) == 8
    for text in translations:
        assert '模型' not in text
        assert sentence('connection') not in text


def test_observe_code_matches_the_download_path():
    """The capture observer and the production decision use one code for the same text."""
    from backend.utils.download_failure_observe import observe_download_failure
    from backend.utils import download_recovery as dr

    def production_code(text: str):
        lowered = text.lower()
        if dr._BLOCKED_HTTP_ERROR.search(lowered):
            return dr.SOURCE_BLOCKED_CODE
        kind = dr._link_failure(lowered)
        if kind:
            return kind[0]
        if dr._rename_locked(lowered):
            return dr.FILE_LOCKED_CODE
        mapped = dr.classify_download_error_text(lowered)
        return mapped[0] if mapped else None

    samples = (
        'ERROR: timed out',
        'ERROR: getaddrinfo failed',
        'ERROR: This video is unavailable',
        'ERROR: Private video. Sign in',
        'ERROR: HTTP Error 403: Forbidden',
        'ERROR: HTTP Error 404: Not Found',
        'ERROR: Postprocessing: ffmpeg timed out',
        'ERROR: Unsupported URL: https://example.invalid/x',
        'ERROR: Unable to rename file: WinError 32 being used by another process',
        'something else entirely',
    )
    for text in samples:
        assert observe_download_failure(text)['code'] == production_code(text), text

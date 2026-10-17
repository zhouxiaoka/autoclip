"""R29 #415: the cloud-transcription redaction boundary builds the snapshot; the legacy import path
(import_processing) carries it instead of rebuilding from the safe text. Separate module: no store fixture."""
import httpx

from backend.core.failure_attribution import FailureKind, classify_failure
from backend.core.sentry_setup import studio_failure_context
from backend.tests.test_cloud_adapter_failure import cloud_adapter  # noqa: F401

SECRET_BODY = 'r29-private-asr-body'


def test_import_subtitle_failure_keeps_the_transcription_snapshot(cloud_adapter):
    import pytest
    from backend.services import cloud_transcription as asr
    from backend.tasks.import_processing import import_subtitle_failure
    settings = cloud_adapter.configure('qwen-audio-3.0-asr-flash', lambda request: httpx.Response(
        503, json={'error': {'message': SECRET_BODY}}, request=request))
    with pytest.raises(asr.CloudTranscriptionError) as caught:
        asr.transcribe(cloud_adapter.video, cloud_adapter.tmp_path / 'out.srt', settings)
    assert caught.value.__cause__ is None and SECRET_BODY not in str(caught.value)
    assert classify_failure(caught.value).kind is FailureKind.MODEL
    failure = import_subtitle_failure(caught.value)
    assert studio_failure_context(failure, 'production').get('http_status') == 503

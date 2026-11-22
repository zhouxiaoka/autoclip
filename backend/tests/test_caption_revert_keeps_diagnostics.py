"""#598 caption corrections stay out; drafts they saved still load, and diagnostics stays."""
from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from backend.api.v1.diagnostics import router as diagnostics_router
from backend.api.v1.studio import router as studio_router
from backend.services.studio import store
from backend.services.studio.models import Draft


def _paths(router):
    return {getattr(route, 'path', '') for route in router.routes}


def test_caption_correction_routes_are_gone_and_diagnostics_routes_remain():
    studio = _paths(studio_router)
    assert not any('retranslate' in path or 'retry-translation' in path for path in studio)
    diagnostics = _paths(diagnostics_router)
    for path in ('/diagnostics/consent', '/diagnostics/preview', '/diagnostics/submit',
                 '/diagnostics/cases', '/diagnostics/cases/{item_id}'):
        assert path in diagnostics


def test_draft_saved_with_caption_correction_fields_loads_without_keeping_them():
    payload = {
        'id': 'd1',
        'title': '保留的标题',
        'ending_review_required': True,
        'scenes': [{
            'id': 's1', 'start': 1.0, 'end': 3.0,
            'caption_end': {
                'row_start': 1.0, 'row_end': 3.0,
                'text_sha256': 'a' * 64, 'offset': 4, 'audio_end': 2.8,
            },
        }],
        'packaging': {
            'template': 'interview_zh',
            'audience_language': 'zh',
            'untranslated_cues': [{'start': 1.0, 'end': 2.0, 'text': '漏译'}],
            'translation_status': 'partial',
            'translated_rows': 1,
            'translation_total_rows': 2,
            'cues': [{
                'start': 1.0, 'end': 2.0, 'text': '保留的字幕',
                'source_id': 'b' * 64, 'source_text': 'source line', 'manually_edited': True,
            }],
        },
    }
    draft = Draft.model_validate(payload)
    dumped = draft.model_dump()
    assert 'ending_review_required' not in dumped
    assert dumped['title'] == '保留的标题'
    scene = dumped['scenes'][0]
    assert scene['id'] == 's1' and 'caption_end' not in scene
    packaging = dumped['packaging']
    for key in ('untranslated_cues', 'translation_status', 'translated_rows', 'translation_total_rows'):
        assert key not in packaging
    cue = packaging['cues'][0]
    assert cue['text'] == '保留的字幕'
    assert 'source_id' not in cue and 'source_text' not in cue and 'manually_edited' not in cue
    with pytest.raises(ValidationError):
        Draft.model_validate({**payload, 'not_from_598': True})


def test_studio_writes_still_schedule_diagnostics():
    assert 'schedule_new_failures' in inspect.getsource(store.write)
    assert 'deliver_pending' in inspect.getsource(store._after_store_release)

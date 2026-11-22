"""#565: image models must not occupy the analysis slot."""
from pathlib import Path

import pytest

from backend.core.model_catalog import IMAGE_MARKERS, is_image_model
from backend.services import ai_model_settings as ai
from backend.services.studio import readiness


def test_frontend_image_markers_match_backend():
    ts = Path(__file__).resolve().parents[2] / 'frontend' / 'src' / 'features' / 'settings' / 'modelKind.ts'
    text = ts.read_text(encoding='utf-8')
    start = text.index('export const IMAGE_MARKERS = [')
    end = text.index('] as const', start)
    block = text[start:end]
    found = []
    for line in block.splitlines():
        line = line.strip().strip(',').strip()
        if line.startswith("'") and line.endswith("'"):
            found.append(line[1:-1])
        elif line.startswith('"') and line.endswith('"'):
            found.append(line[1:-1])
    assert tuple(found) == IMAGE_MARKERS
    assert is_image_model('doubao-seedream-5-0-flash-260915')
    assert not is_image_model('doubao-seed-2-1-lite-260915')


def test_readiness_blocks_image_model_in_analysis(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    settings = ai.ModelSettings(
        connections=[ai.Connection(
            id='c1', name='seed', provider='seed', api_key='sk-x', validation_status='ok',
        )],
        analysis=ai.Assignment(connection_id='c1', model='doubao-seedream-5-0-flash-260915'),
        transcription=ai.Transcription(provider='whisper_local', model='base'),
    )
    monkeypatch.setattr(ai, 'for_editing', lambda: settings)
    monkeypatch.setattr(ai, 'load', lambda **k: settings)
    report = readiness.report()
    assert report['checks']['analysis']['ok'] is False
    assert report['checks']['analysis']['code'] == 'image_model_in_analysis'
    with pytest.raises(Exception) as raised:
        readiness.ensure_analysis_usable()
    assert '生图模型' in str(raised.value)

"""R20 #136/#137/#138 for #415: each test fails on 6fbacce3 and passes after the fix."""
import pytest

from backend.core import llm_emit
from backend.core import llm_telemetry as schema
from backend.core.provider_presets import iter_providers
from backend.services import ai_model_settings as ai
from backend.services.studio import failure_identity


@pytest.fixture
def two_connections(tmp_path, monkeypatch):
    """Text on DeepSeek preset, vision on a separate customized OpenAI-compatible endpoint."""
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())
    ai.save(ai.ModelSettings(
        connections=[
            ai.Connection(id='text', name='Text', provider='deepseek', base_url='https://api.deepseek.com', api_key='fixture-key'),
            ai.Connection(id='eyes', name='Eyes', provider='kimi', base_url='https://vision.fixture.example/v1', api_key='fixture-key'),
        ],
        analysis=ai.Assignment(connection_id='text', model='deepseek-flash', capability='text'),
        vision=ai.Assignment(connection_id='eyes', model='private-vision-model', capability='multimodal'),
        analysis_mode='visual', allow_send_frame=True,
    ))


def test_136_vision_attempt_identity_comes_from_the_vision_connection(two_connections):
    assert failure_identity.provider_identity('analysis') == {'provider': 'deepseek', 'config_source': 'preset'}
    assert failure_identity.provider_identity('vision') == {'provider': 'kimi', 'config_source': 'customized'}


def test_137_run_sanitizer_keeps_config_source_and_drops_garbage():
    assert schema.sanitize_run_properties({'config_source': 'preset'})['config_source'] == 'preset'
    assert schema.sanitize_run_properties({'config_source': 'customized'})['config_source'] == 'customized'
    assert 'config_source' not in schema.sanitize_run_properties({'config_source': 'https://x.example/v1'})


def test_137_run_snapshot_carries_config_source(two_connections):
    # R25 #415: inside a run the identity is the frozen phase connection (settings are never read).
    with llm_emit.track_run():
        llm_emit.freeze_phase_identity(failure_identity.phase_identity('production', {'confirmed_analysis': 'subtitle'}))
        snap = llm_emit.run_snapshot()
    assert snap.get('config_source') == 'preset'
    assert set(snap) <= set(schema.RUN_LEVEL_FIELDS)


def test_137_frontend_send_path_keeps_config_source():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / 'frontend/src/analytics/workflow.ts').read_text(encoding='utf-8')
    assert "config_source: ['preset', 'customized']" in src


@pytest.mark.parametrize('preset', [p.id for p in iter_providers()])
def test_138_request_event_provider_is_the_catalog_id_for_every_preset(preset):
    assert llm_emit._provider_name(preset) == preset


def test_138_siliconflow_is_not_compatible_on_the_real_sender():
    class SiliconFlowProvider:
        base_url = 'https://api.siliconflow.cn/v1'
    assert llm_emit._provider_name('siliconflow') == 'siliconflow'
    assert llm_emit._provider_label(SiliconFlowProvider(), SiliconFlowProvider.base_url) == 'siliconflow'


def test_138_no_private_alias_table_in_llm_emit():
    assert not hasattr(llm_emit, '_PROVIDER_ALIASES')
    assert llm_emit._provider_name('88api') == 'api88'   # catalog alias still resolves

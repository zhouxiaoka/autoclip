"""Empty catalog URLs require an explicit, validated compatible endpoint."""
import pytest

from backend.core.provider_presets import iter_providers
from backend.services import ai_model_settings as models

ENDPOINT_IDS = [row.id for row in iter_providers() if not row.base_url and row.protocol != 'local']


@pytest.mark.parametrize('provider', ENDPOINT_IDS)
@pytest.mark.parametrize('url,status,ready', [('', 'ok', False), ('https://endpoint.example.test/v1', 'unchecked', False), ('https://endpoint.example.test/v1', 'failed', False), ('https://endpoint.example.test/v1', 'ok', True)])
def test_runtime_endpoint_gate(provider, url, status, ready):
    # model_construct deliberately covers damaged persisted/old-client rows too.
    connection = models.Connection.model_construct(id='endpoint', name='Endpoint', provider='compatible',
        catalog_provider_id=provider, base_url=url, api_key='test-only', validation_status=status)
    settings = models.ModelSettings.model_construct(connections=[connection], analysis=models.Assignment(connection_id='endpoint', model='model'))
    if ready:
        assert models.connection_for(settings, settings.analysis).id == 'endpoint'
        assert models.chat_endpoint(connection, 'model')['base_url'] == url
    else:
        with pytest.raises(ValueError, match='接口地址|验证'):
            models.connection_for(settings, settings.analysis)
        with pytest.raises(ValueError, match='接口地址|验证'):
            models.require_analysis(settings)


@pytest.mark.parametrize('provider', ENDPOINT_IDS)
def test_endpoint_catalog_identity_survives_save_and_reload(provider, tmp_path, monkeypatch):
    monkeypatch.setattr(models, 'path', lambda: tmp_path / 'settings.json')
    monkeypatch.setattr(models, 'for_editing', lambda: models.ModelSettings())
    connection = models.Connection(id='endpoint', name='Endpoint', provider='compatible', catalog_provider_id=provider,
        base_url='https://endpoint.example.test/v1', api_key='test-only', validation_status='ok')
    settings = models.ModelSettings(connections=[connection], analysis=models.Assignment(connection_id='endpoint', model='model'))
    public = models.save(settings)
    assert public['connections'][0]['catalog_provider_id'] == provider
    assert models.load().connections[0].catalog_provider_id == provider


@pytest.mark.parametrize('provider', ENDPOINT_IDS)
@pytest.mark.parametrize('succeeds', [False, True])
def test_validation_probes_user_endpoint_and_gates_runtime(provider, succeeds, monkeypatch):
    from types import SimpleNamespace
    from backend.services import provider_validation as validation
    from backend.core.upstream_errors import UpstreamErrorType
    monkeypatch.setattr(models, 'for_editing', lambda: models.ModelSettings())
    requested = []
    connection = models.Connection(id='endpoint', name='Endpoint', provider='compatible', catalog_provider_id=provider,
        base_url='https://endpoint.example.test/v1', api_key='test-only')
    def get_models(base, key, protocol):
        requested.append((base, protocol))
        return ['model'], None, SimpleNamespace(recommended={}, truncated=False, message_key='')
    monkeypatch.setattr(validation, '_get_models', get_models)
    monkeypatch.setattr(validation, '_probe', lambda *args: None if succeeds else validation._as_type(UpstreamErrorType.INVALID_KEY))
    result = validation.validate_connection(connection, 'model')
    assert result.ok is succeeds
    assert requested == [('https://endpoint.example.test/v1', 'compatible')]
    checked = connection.model_copy(update={'validation_status': 'ok' if result.ok else 'failed'})
    assert models.endpoint_provider_ready(checked) is succeeds


@pytest.mark.parametrize('provider', ENDPOINT_IDS)
def test_missing_address_rejected_before_any_validation_request(provider):
    with pytest.raises(ValueError, match='接口地址'):
        models.Connection(id='endpoint', name='Endpoint', provider='compatible', catalog_provider_id=provider, api_key='test-only')

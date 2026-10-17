"""R23 #415 (Dong): a text request's identity is the connection of the route it was resolved on
(failure_identity.connection_identity, frozen with the route like vision), never settings re-read at
send time. Drives the real LLMManager route -> call -> provider.call -> observe_provider_call path.
Fails on f5921576 (observe_provider_call read settings before sending)."""
import pytest

from backend.core import llm_emit
from backend.core.llm_manager import LLMManager
from backend.services import ai_model_settings as ai


def _provider_down():
    """R28 I450: a provider failure is a request that was SENT and answered with an error (a status)."""
    return type('ProviderDown', (RuntimeError,), {'status_code': 500})('fixture')


TEXT = {'provider': 'deepseek', 'config_source': 'preset'}


@pytest.fixture(autouse=True)

def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())


@pytest.fixture
def posted(monkeypatch):
    events = []
    monkeypatch.setattr(llm_emit, '_post_event', lambda event, props: events.append((event, props)))
    return events


CONNECTIONS = [
    ai.Connection(id='text', name='Text', provider='deepseek', base_url='https://api.deepseek.com', api_key='fixture-key'),
    ai.Connection(id='other', name='Other', provider='glm', base_url='https://other.fixture.example/v1', api_key='fixture-key'),
]


def _settings(analysis='text'):
    models = {'text': 'deepseek-flash', 'other': 'private-other-model'}
    ai.save(ai.ModelSettings(
        connections=CONNECTIONS,
        analysis=ai.Assignment(connection_id=analysis, model=models[analysis], capability='text'),
    ))


def _ident(record):
    return {k: (record or {}).get(k) for k in ('provider', 'config_source')}


def _failing_send(monkeypatch, provider, during=None):
    def create(**_k):
        if during:
            during()
        raise _provider_down()
    monkeypatch.setattr(provider.client.chat.completions, 'create', create)


def _run(manager, route):
    with llm_emit.track_run():
        with pytest.raises(Exception) as caught:
            manager.call('p', _route=route)
        # R25 #415: a failure is attributed through the record its exception carries (not 'latest request').
        return llm_emit.run_snapshot(error=caught.value), llm_emit.sentry_tags_for_error(caught.value, 'analyze')


def test_r23_settings_saved_after_route_before_send_keep_the_route_connection(monkeypatch, posted):
    _settings()
    manager = LLMManager()
    route = manager._snapshot_call_route()
    _failing_send(monkeypatch, route.provider)
    _settings(analysis='other')                       # saved between route resolution and send
    snap, tags = _run(manager, route)
    request = [p for e, p in posted if e == 'llm_request_finished'][-1]
    assert request['provider'] == 'deepseek'          # request event
    assert _ident(snap) == TEXT                       # run snapshot (generation / production)
    assert tags.get('provider') == 'deepseek'         # terminal Sentry tags


def test_r23_settings_saved_while_text_request_is_in_flight_do_not_move_it(monkeypatch, posted):
    _settings()
    manager = LLMManager()
    route = manager._snapshot_call_route()
    _failing_send(monkeypatch, route.provider, during=lambda: _settings(analysis='other'))
    snap, _tags = _run(manager, route)
    assert _ident(snap) == TEXT


def test_r23_route_carries_the_one_identity_rule():
    _settings()
    route = LLMManager()._snapshot_call_route()
    assert route.identity == TEXT
    assert 'identity' not in route.settings and '_route_identity' not in route.settings  # never saved

"""Exercise the desktop OAuth protocol, archive binding and concurrent project imports offline."""
import base64
import hashlib
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from backend.api.v1.replay_channels import router
from backend.core.database import session_scope
from backend.models.project import Project
from backend.services import replay_channels as channels
from backend.services.studio import jobs, readiness
from backend.tests.test_studio import client, root, source


class FakeVault:
    def __init__(self):
        self.items = {}

    def get_password(self, service, key):
        return self.items.get((service, key))

    def set_password(self, service, key, value):
        self.items[service, key] = value

    def delete_password(self, service, key):
        del self.items[service, key]


class ProviderFixture:
    def __init__(self):
        self.identity = 'channelOne'
        self.verifier = None
        self.waiting = False
        self.revoked = False

    def request(self, method, url, **kwargs):
        if url.endswith('/device'):
            return 200, dict(user_code='EXAMPLE', device_code='device', verification_uri='https://www.twitch.tv/activate')
        if url.endswith('/token'):
            data = kwargs['data']
            if self.waiting:
                return 400, {'message': 'authorization_pending'}
            if data['grant_type'] == 'authorization_code':
                assert data['code'] == 'accepted'
                self.verifier = data['code_verifier']
            if data['grant_type'] == 'refresh_token':
                assert data['refresh_token'] == 'refresh'
            return 200, dict(access_token='access', refresh_token='refresh', expires_in=3600)
        if url.endswith('/users'):
            return 200, {'data': [{'id': self.identity, 'display_name': 'Creator'}]}
        if url.endswith('/channels'):
            assert kwargs['params']['mine'] == 'true'
            return 200, {'items': [{'id': self.identity, 'snippet': {'title': 'Creator'}}]}
        if url.endswith('/videos'):
            params = kwargs['params']
            assert params['user_id'] == self.identity and params['type'] == 'archive'
            item = dict(id=params.get('after', 'first'), type='archive', user_id=self.identity, title='Final round', duration='5h7m',
                        thumbnail_url='https://static-cdn.jtvnw.net/test-%{width}x%{height}.jpg', created_at='2026-01-01T00:00:00Z')
            return 200, {'data': [item, dict(item, user_id='unrelated')], 'pagination': {} if 'after' in params else {'cursor': 'second'}}
        if url.endswith('/liveBroadcasts'):
            params = kwargs['params']
            assert params['broadcastStatus'] == 'completed' and params['broadcastType'] == 'all'
            info = dict(channelId=self.identity, title='Final round',
                        thumbnails={'medium': {'url': 'https://i.ytimg.com/test.jpg'}}, actualStartTime='2026-01-01T00:00:00Z')
            item = dict(id=params.get('pageToken', 'first'), snippet=info, status={'lifeCycleStatus': 'complete'})
            return 200, {'items': [item, dict(item, snippet=dict(info, channelId='unrelated'))],
                         'nextPageToken': None if 'pageToken' in params else 'second'}
        if url.endswith('/revoke'):
            self.revoked = True
            return 200, {}
        raise AssertionError(url)


@pytest.fixture
def platform(client, monkeypatch):
    provider = ProviderFixture()
    vault = FakeVault()
    monkeypatch.setattr(channels, 'config', lambda p: ('desktop-client', 'desktop-secret' if p == 'youtube' else None))
    monkeypatch.setattr(channels, 'keychain', lambda: vault)
    monkeypatch.setattr(channels, 'request', provider.request)
    monkeypatch.setattr(readiness, 'ensure_analysis_usable', lambda: None)
    monkeypatch.setattr('backend.pipeline.media_precheck.too_short', lambda _: False)
    client.app.state.mode = 'desktop'
    client.app.include_router(router, prefix='/channels')
    yield provider
    for name in channels.locks:
        channels.stop_attempt(name)


@pytest.mark.parametrize('name', ['twitch', 'youtube'])
def test_channel_to_project_and_reopen(client, source, platform, monkeypatch, name):
    url = '/channels/' + name
    assert client.get(url).json() == {'configured': True, 'channel': None}
    flow = client.post(url + '/connect').json()
    poll = url + '/connect/' + flow['id']
    if name == 'youtube':
        query = parse_qs(urlsplit(flow['url']).query)
        assert query['scope'] == ['https://www.googleapis.com/auth/youtube.readonly']
        callback = query['redirect_uri'][0]
        assert requests.get(callback, params=dict(state='wrong', code='ignored'), timeout=3).status_code == 400
        assert client.post(poll).json()['pending']
        assert requests.get(callback, params=dict(state=query['state'][0], code='accepted'), timeout=3).ok
    else:
        assert flow['code'] == 'EXAMPLE' and 'device' not in flow
        platform.waiting = True
        assert client.post(poll).json()['pending']
        channels.pending[name]['next_poll'] = 0
        platform.waiting = False
    assert client.post(poll).json() == {'pending': False, 'channel': 'Creator'}
    if name == 'youtube':
        digest = hashlib.sha256(platform.verifier.encode()).digest()
        assert base64.urlsafe_b64encode(digest).rstrip(b'=').decode() == query['code_challenge'][0]
    assert client.post(poll).status_code == 410
    saved = channels.credentials(name)
    saved['expires'] = 0
    channels.credentials(name, saved)
    listing = client.get(url + '/archives').json()
    row, = listing['items']
    assert row['project_id'] is None and row['title'] == 'Final round'
    if name == 'twitch':
        assert row['thumbnail_url'] == 'https://static-cdn.jtvnw.net/test-320x180.jpg'
        assert row['duration'] == '5h7m'
    else:
        assert row['thumbnail_url'] == 'https://i.ytimg.com/test.jpg'
        assert row['duration'] is None
    assert 'token' not in str(listing)
    second = client.get(url + '/archives', params={'cursor': listing['next']}).json()
    assert len(second['items']) == 1 and second['items'][0]['id'] != row['id'] and second['next'] is None
    assert client.put(url + '/selection', json={'archive_id': row['id']}).is_success
    assert client.get(url + '/archives').json()['selected'] == {'id': row['id'], 'title': row['title']}
    calls = []
    monkeypatch.setattr(jobs, 'inspect_project', lambda pid, *a, **kw: calls.append(pid))
    def submit(key=row['id']):
        return client.post('/studio/import', data={'replay_source': name + '_file', 'channel_replay_id': key},
                           files={'video': ('sample.mp4', source.read_bytes(), 'video/mp4')})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: submit(), range(2)))
    assert [r.status_code for r in results] == [200, 200], [r.text for r in results]
    pid = results[0].json()['project_id']
    assert results[1].json()['project_id'] == pid and calls == [pid]
    reopened = client.get(url + '/archives').json()
    assert reopened['items'][0]['project_id'] == pid and reopened['selected'] is None
    with session_scope() as db:
        project = db.get(Project, pid)
        assert project.name == 'Final round' and project.processing_config['channel_replay_id'] == row['id']
    saved['channel'] = 'another'
    channels.credentials(name, saved)
    assert submit().status_code == 409
    assert client.delete(url).status_code == 200 and platform.revoked
    assert client.get(url + '/archives').status_code == 401
    assert calls == [pid]


def test_cancel_and_missing_registration(client, platform, monkeypatch):
    url = '/channels/twitch'
    flow = client.post(url + '/connect').json()
    assert client.delete(url + '/connect/' + flow['id']).is_success
    assert client.post(url + '/connect/' + flow['id']).status_code == 410
    monkeypatch.setattr(channels, 'config', lambda _: (None, None))
    assert client.get(url).json()['configured'] is False
    assert client.post(url + '/connect').status_code == 503


def test_native_app_configuration_reads_downloaded_google_json(tmp_path, monkeypatch):
    import json
    google = tmp_path / 'google-desktop.json'
    google.write_text(json.dumps({'installed': {'client_id': 'test-id', 'client_secret': 'fixture'}}))
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_YOUTUBE_DESKTOP_JSON', str(google))
    monkeypatch.setenv('AUTOCLIP_TWITCH_CLIENT_ID', 'test-public')
    assert channels.config('youtube') == ('test-id', 'fixture')
    assert channels.config('twitch') == ('test-public', None)


def test_failed_copy_releases_archive_for_retry(client, platform, source, monkeypatch):
    import shutil
    url = '/channels/twitch'
    flow = client.post(url + '/connect').json()
    assert client.post(url + '/connect/' + flow['id']).is_success
    key = client.get(url + '/archives').json()['items'][0]['id']
    def submit():
        return client.post('/studio/import', data={'replay_source': 'twitch_file', 'channel_replay_id': key},
                           files={'video': ('replay.mp4', source.read_bytes(), 'video/mp4')})
    def fail(*args, **kwargs):
        raise OSError('fixture copy error')
    with monkeypatch.context() as patch:
        patch.setattr(shutil, 'move', fail)
        with pytest.raises(OSError, match='fixture copy'):
            submit()
    assert client.get(url + '/archives').json()['items'][0]['project_id'] is None
    monkeypatch.setattr(jobs, 'inspect_project', lambda *a, **kw: None)
    assert submit().is_success


def test_picker_availability_is_per_platform_and_does_not_read_credentials(client, platform, monkeypatch):
    def registration(name):
        if name == 'youtube':
            raise channels.HTTPException(503, 'channel_config')
        return 'desktop-client', None

    monkeypatch.setattr(channels, 'config', registration)
    monkeypatch.setattr(channels, 'keychain', lambda: pytest.fail('picker opened the keychain'))
    response = client.get('/channels/availability')
    assert response.json() == {'twitch': True, 'youtube': False}


@pytest.mark.parametrize('reason', ['liveStreamingNotEnabled', 'quotaExceeded', 'forbidden'])
def test_youtube_unavailable_broadcasts(client, platform, monkeypatch, reason):
    channels.credentials('youtube', {'channel': 'channelOne', 'name': 'Creator',
                                    'access': 'fixture', 'expires': 4_000_000_000})
    monkeypatch.setattr(channels, 'authorized_get', lambda *args: (403, {
        'error': {'errors': [{'reason': reason}]}}))
    response = client.get('/channels/youtube/archives')
    if reason == 'liveStreamingNotEnabled':
        assert response.status_code == 200
        assert response.json() == {'channel': 'Creator', 'items': [], 'selected': None,
                                   'next': None, 'live_streaming_disabled': True}
    else:
        assert response.status_code == 503
    assert client.get('/channels/youtube').json()['channel'] == 'Creator'


def test_selected_twitch_archive_download_and_import(client, platform, source, monkeypatch):
    import shutil
    from pathlib import Path
    from backend.services import twitch_replay_media as media

    channels.credentials('twitch', {'channel': 'creator', 'name': 'Creator', 'expires': 4_000_000_000, 'access': 'local'})
    row = {'id': '123', 'user_id': 'creator', 'type': 'archive', 'viewable': 'public', 'stream_id': '99',
           'title': 'Final round', 'duration': '3s'}
    live = []
    def helix(provider, token, path, params):
        assert provider == 'twitch' and token == 'local'
        if path == 'streams':
            assert params == {'user_id': 'creator'}
            return 200, {'data': live}
        assert path == 'videos' and (params.get('id') == '123' or params.get('user_id') == 'creator')
        return 200, {'data': [row]}

    monkeypatch.setattr(channels, 'authorized_get', helix)
    monkeypatch.delenv('AUTOCLIP_TWITCH_REPLAY_PILOT', raising=False)
    listing = '/channels/twitch/archives'
    item, = client.get(listing).json()['items']
    assert 'direct_video_id' not in item
    data = {'twitch_video_id': '123', 'channel_replay_id': item['id'], 'replay_source': 'twitch_file'}
    assert client.post('/studio/import', data=data).status_code == 422
    monkeypatch.setenv('AUTOCLIP_TWITCH_REPLAY_PILOT', '1')
    assert client.get(listing).json()['items'][0]['direct_video_id'] == '123'
    assert client.post('/studio/import', data=data).status_code == 409
    assert client.put('/channels/twitch/selection', json={'archive_id': item['id']}).is_success
    downloads, jobs_started = [], []
    def download(video_id, folder):
        assert video_id == '123'
        downloads.append(video_id)
        path = folder / 'download.mp4'
        shutil.copyfile(source, path)
        return path
    monkeypatch.setattr(media, 'download_archive', download)
    monkeypatch.setattr(jobs, 'inspect_project', lambda pid, *a, **kw: jobs_started.append(pid))
    live.append({'id': '99', 'user_id': 'creator'})
    assert client.post('/studio/import', data=data).status_code == 409
    live.clear()
    row['user_id'] = 'other'
    assert client.post('/studio/import', data=data).status_code == 409
    row['user_id'] = 'creator'
    assert not downloads and not jobs_started
    row['duration'] = '2h'
    assert client.post('/studio/import', data=data).json()['detail'] == 'replay_download_failed'
    assert client.get(listing).json()['items'][0]['project_id'] is None
    row['duration'] = '3s'
    result = client.post('/studio/import', data=data)
    assert result.is_success, result.text
    pid = result.json()['project_id']
    assert client.post('/studio/import', data=data).json()['project_id'] == pid
    assert downloads == ['123', '123'] and jobs_started == [pid]
    with session_scope() as db:
        project = db.get(Project, pid)
        assert project.processing_config['smart_import']['replay_source'] == 'twitch_archive'
        assert project.processing_config['import_source'] == 'twitch_archive'
        assert Path(project.video_path).read_bytes() == source.read_bytes()

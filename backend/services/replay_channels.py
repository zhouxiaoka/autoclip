"""Read-only channel connections for the desktop replay picker."""
import asyncio
import base64
import hashlib
import json
import os
import secrets
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import requests
from fastapi import HTTPException
from sqlalchemy import Boolean, Column, String, text, update
from sqlalchemy.dialects.sqlite import insert

from backend.core.path_utils import get_data_directory
from backend.models.base import Base
from backend.models.project import Project
from backend.services import twitch_replay_media
from backend.services.obs.settings import credential_id, keychain
from backend.services.project_service import ProjectService

GOOGLE_AUTH = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN = 'https://oauth2.googleapis.com/token'
YT = 'https://www.googleapis.com/youtube/v3/'
TW_AUTH = 'https://id.twitch.tv/oauth2/'
HELIX = 'https://api.twitch.tv/helix/'
locks = {p: threading.RLock() for p in ('twitch', 'youtube')}
pending = {}


class ReplayArchive(Base):
    __tablename__ = 'channel_replay_archives'
    id = Column(String(36), primary_key=True)
    provider = Column(String(8), nullable=False)
    channel = Column(String(128), nullable=False)
    title = Column(String(256), nullable=False)
    project_id = Column(String(36), nullable=True)


class ChannelSelection(Base):
    __tablename__ = 'channel_replay_selections'
    provider = Column(String(8), primary_key=True)
    channel = Column(String(128), primary_key=True)
    archive_id = Column(String(36), nullable=False)


class ReplayArchiveMeta(Base):
    """Additive metadata for restoring page-2+ selections without altering legacy tables."""
    __tablename__ = 'channel_replay_archive_meta'
    archive_id = Column(String(36), primary_key=True)
    remote_id = Column(String(64), nullable=False)
    duration = Column(String(32), nullable=True)
    direct_ready = Column(Boolean, nullable=False, default=False)


def _connected_marker(provider):
    return get_data_directory() / f'.replay-channel-{provider}'


def select_archive(provider, key, db):
    with locks[provider]:
        account = credentials(provider)
        if not account:
            raise HTTPException(401, 'channel_reconnect')
        channel = account['channel']
        if key is None:
            selection = db.get(ChannelSelection, (provider, channel))
            if selection:
                db.delete(selection)
        else:
            archive = db.get(ReplayArchive, key)
            if not archive or archive.provider != provider or archive.channel != channel:
                raise HTTPException(409, 'channel_mismatch')
            stmt = insert(ChannelSelection).values(provider=provider, channel=channel, archive_id=key)
            db.execute(stmt.on_conflict_do_update(index_elements=['provider', 'channel'], set_={'archive_id': key}))
        db.commit()


def config(provider):
    # App registrations may be supplied with a build or overridden for local QA.
    bundled = Path(__file__).resolve().parents[1] / 'presets' / 'replay-oauth.json'
    local = get_data_directory() / 'replay-oauth.json'
    path = Path(os.environ.get('AUTOCLIP_REPLAY_OAUTH_CONFIG') or (local if local.exists() else bundled))
    try:
        application = json.loads(path.read_text(encoding='utf-8')).get(provider, {}) if path.is_file() else {}
        if provider == 'youtube' and os.getenv('AUTOCLIP_YOUTUBE_DESKTOP_JSON'):
            desktop = Path(os.environ['AUTOCLIP_YOUTUBE_DESKTOP_JSON']).expanduser()
            application = json.loads(desktop.read_text(encoding='utf-8'))['installed']
        client_id = application.get('client_id') or os.getenv('AUTOCLIP_' + provider.upper() + '_CLIENT_ID')
        secret = None
        if provider == 'youtube':
            secret = application.get('client_secret') or os.getenv('AUTOCLIP_YOUTUBE_CLIENT_SECRET')
        return client_id, secret
    except (OSError, ValueError, AttributeError, KeyError, TypeError):
        raise HTTPException(503, 'channel_config') from None


def credentials(provider, value=None, *, remove=False):
    try:
        store = keychain()
        key = credential_id()
        service = 'AutoClip replay ' + provider
        marker = _connected_marker(provider)
        if remove:
            if store.get_password(service, key):
                store.delete_password(service, key)
            try:
                marker.unlink(missing_ok=True)
            except OSError:
                pass
        elif value is not None:
            store.set_password(service, key, json.dumps(value, ensure_ascii=True))
            try:
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text('1', encoding='utf-8')
            except OSError:
                pass
        else:
            account = json.loads(store.get_password(service, key) or 'null')
            if account and not marker.exists():
                try:
                    marker.parent.mkdir(parents=True, exist_ok=True)
                    marker.write_text('1', encoding='utf-8')
                except OSError:
                    pass
            return account
    except Exception:
        raise HTTPException(503, 'channel_keychain') from None


def request(method, url, **kwargs):
    try:
        response = requests.request(method, url, timeout=12, allow_redirects=False, **kwargs)
        try:
            body = response.json()
        except ValueError:
            body = {}
        return response.status_code, body if isinstance(body, dict) else {}
    except requests.RequestException:
        raise HTTPException(502, 'channel_network') from None


def check(status):
    if status == 401:
        raise HTTPException(401, 'channel_reconnect')
    if not 200 <= status < 300:
        raise HTTPException(503 if status in (403, 429) else 502, 'channel_provider')


def state(provider):
    configured = bool(config(provider)[0])
    account = credentials(provider) if configured else None
    return {'configured': configured, 'channel': account['name'] if account else None}


def google_callback(flow):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # OAuth codes and state never enter access logs.

        def do_GET(self):
            parsed = urlsplit(self.path)
            params = parse_qs(parsed.query)
            if parsed.path != '/callback' or not secrets.compare_digest(params.get('state', [''])[0].encode(), flow['state'].encode()):
                self.send_error(400)
                return
            flow['code'] = params.get('code', [''])[0]
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(b'AutoClip: return to the app to continue.')

    class LoopbackServer(HTTPServer):
        def get_request(self):
            socket, address = super().get_request()
            socket.settimeout(3)
            return socket, address

    server = LoopbackServer(('127.0.0.1', 0), Handler)
    server.timeout = 0.5

    def accept():
        with server:
            while not flow['cancel'].is_set() and 'code' not in flow and time.monotonic() < flow['deadline']:
                server.handle_request()

    threading.Thread(target=accept, daemon=True).start()
    return f'http://127.0.0.1:{server.server_port}/callback'


def cancel(provider):
    flow = pending.pop(provider, None)
    if flow:
        flow['cancel'].set()


def stop_attempt(provider):
    with locks[provider]:
        cancel(provider)


def begin(provider):
    with locks[provider]:
        cid, _ = config(provider)
        if not cid:
            raise HTTPException(503, 'channel_config')
        cancel(provider)
        flow = {'id': secrets.token_urlsafe(24), 'cancel': threading.Event(), 'deadline': time.monotonic() + 300}
        result = {'id': flow['id']}
        if provider == 'youtube':
            verifier = secrets.token_urlsafe(48)
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
            flow.update(state=secrets.token_urlsafe(32), verifier=verifier)
            try:
                flow['redirect'] = google_callback(flow)
            except OSError:
                raise HTTPException(503, 'channel_callback') from None
            result['url'] = GOOGLE_AUTH + '?' + urlencode(dict(client_id=cid, redirect_uri=flow['redirect'],
                response_type='code', scope='https://www.googleapis.com/auth/youtube.readonly',
                access_type='offline', prompt='select_account consent', state=flow['state'],
                code_challenge=challenge, code_challenge_method='S256'))
        else:
            status, body = request('POST', TW_AUTH + 'device', data={'client_id': cid, 'scopes': ''})
            check(status)
            if not all(body.get(k) for k in ('device_code', 'user_code', 'verification_uri')):
                raise HTTPException(502, 'channel_provider')
            flow.update(device=body['device_code'], interval=max(5, int(body.get('interval', 5))), next_poll=0)
            flow['deadline'] = time.monotonic() + min(1800, int(body.get('expires_in', 300)))
            if urlsplit(body['verification_uri']).hostname not in ('www.twitch.tv', 'twitch.tv') or urlsplit(body['verification_uri']).scheme != 'https':
                raise HTTPException(502, 'channel_provider')
            result.update(url=body['verification_uri'], code=body['user_code'])
        pending[provider] = flow
        return result


def authorized_get(provider, token, path, params):
    headers = {'Authorization': 'Bearer ' + token}
    if provider == 'twitch':
        headers['Client-ID'] = config(provider)[0]
    return request('GET', (HELIX if provider == 'twitch' else YT) + path, headers=headers, params=params)


def tokens(body, previous=None):
    if not body.get('access_token'):
        raise HTTPException(502, 'channel_provider')
    return {'access': body['access_token'], 'refresh': body.get('refresh_token') or previous,
            'expires': time.time() + int(body.get('expires_in', 3600))}


def poll(provider, attempt):
    with locks[provider]:
        flow = pending.get(provider)
        if not flow or flow['id'] != attempt or time.monotonic() >= flow['deadline']:
            raise HTTPException(410, 'channel_expired')
        cid, secret = config(provider)
        if provider == 'youtube':
            if 'code' not in flow:
                return {'pending': True}
            if not flow['code']:
                cancel(provider)
                raise HTTPException(403, 'channel_denied')
            data = dict(grant_type='authorization_code', code=flow['code'], client_id=cid,
                        redirect_uri=flow['redirect'], code_verifier=flow['verifier'])
            if secret:
                data['client_secret'] = secret
            status, body = request('POST', GOOGLE_TOKEN, data=data)
        else:
            if time.monotonic() < flow['next_poll']:
                return {'pending': True}
            flow['next_poll'] = time.monotonic() + flow['interval']
            status, body = request('POST', TW_AUTH + 'token', data=dict(client_id=cid, device_code=flow['device'],
                grant_type='urn:ietf:params:oauth:grant-type:device_code', scopes=''))
            reason = body.get('message') or body.get('error')
            if status == 400 and reason in ('authorization_pending', 'slow_down'):
                if reason == 'slow_down':
                    flow['interval'] += 5
                    flow['next_poll'] += 5
                return {'pending': True}
        cancel(provider)
        if status in (400, 403):
            raise HTTPException(403, 'channel_denied')
        check(status)
        account = tokens(body)
        twitch = provider == 'twitch'
        status, identity = authorized_get(provider, account['access'], 'users' if twitch else 'channels',
                                          {} if twitch else {'part': 'snippet', 'mine': 'true'})
        check(status)
        channels = identity.get('data' if twitch else 'items') or []
        if not channels or not channels[0].get('id'):
            raise HTTPException(404, 'channel_missing')
        channel = channels[0]
        account.update(channel=channel['id'], name=channel['display_name'] if twitch else channel['snippet']['title'])
        credentials(provider, account)
        return {'pending': False, 'channel': account['name']}


def refresh(provider, account):
    if not account['refresh']:
        raise HTTPException(401, 'channel_reconnect')
    cid, secret = config(provider)
    data = dict(client_id=cid, grant_type='refresh_token', refresh_token=account['refresh'])
    if secret:
        data['client_secret'] = secret
    status, body = request('POST', TW_AUTH + 'token' if provider == 'twitch' else GOOGLE_TOKEN, data=data)
    if status in (400, 401):
        raise HTTPException(401, 'channel_reconnect')
    check(status)
    account.update(tokens(body, account['refresh']))
    credentials(provider, account)


def validate_twitch():
    if not config('twitch')[0] or not _connected_marker('twitch').exists():
        return
    with locks['twitch']:
        account = credentials('twitch')
        if not account:
            try:
                _connected_marker('twitch').unlink(missing_ok=True)
            except OSError:
                pass
            return
        if account['expires'] <= time.time() + 60:
            try:
                refresh('twitch', account)
            except HTTPException as exc:
                if exc.status_code == 401:
                    credentials('twitch', remove=True)
                raise
        status, identity = request('GET', TW_AUTH + 'validate', headers={'Authorization': 'OAuth ' + account['access']})
        if status == 401 or (status == 200 and (identity.get('user_id') != account['channel']
                                                or identity.get('client_id') != config('twitch')[0])):
            credentials('twitch', remove=True)
            return
        check(status)


async def maintain_twitch():
    while True:
        try:
            await asyncio.to_thread(validate_twitch)
            delay = 3500
        except HTTPException:
            delay = 300
        await asyncio.sleep(delay)


def archive_thumbnail(twitch, info):
    if twitch:
        url = info.get('thumbnail_url') or ''
        for axis, size in (('width', '320'), ('height', '180')):
            placeholder = '{' + axis + '}'
            url = url.replace('%' + placeholder, size).replace(placeholder, size)
    else:
        images = info.get('thumbnails') or {}
        url = next((images[size]['url'] for size in ('medium', 'high', 'default')
                    if (images.get(size) or {}).get('url')), '')
    return url if url.startswith('https://') else None


def list_archives(provider, cursor, db):
    with locks[provider]:
        account = credentials(provider)
        if not account:
            raise HTTPException(401, 'channel_reconnect')
        channel = account['channel']
        if account['expires'] <= time.time() + 60:
            refresh(provider, account)
        twitch = provider == 'twitch'
        params = ({'user_id': channel, 'type': 'archive', 'first': 25} if twitch else
                  {'part': 'id,snippet,status', 'broadcastStatus': 'completed', 'broadcastType': 'all', 'maxResults': 25})
        if cursor:
            params['after' if twitch else 'pageToken'] = cursor
        path = 'videos' if twitch else 'liveBroadcasts'
        status, body = authorized_get(provider, account['access'], path, params)
        if status == 401:
            refresh(provider, account)
            status, body = authorized_get(provider, account['access'], path, params)
        if not twitch and status == 403:
            error = body.get('error')
            details = error.get('errors') if isinstance(error, dict) else None
            if isinstance(details, list) and details and all(
                isinstance(item, dict) and item.get('reason') == 'liveStreamingNotEnabled' for item in details
            ):
                return {'channel': account['name'], 'items': [], 'selected': None,
                        'next': None, 'live_streaming_disabled': True}
        check(status)
        items = []
        for row in body.get('data' if twitch else 'items', []):
            info = row if twitch else row.get('snippet', {})
            if twitch and (info.get('user_id') != channel or info.get('type') != 'archive'):
                continue
            if not twitch and (info.get('channelId') != channel or row.get('status', {}).get('lifeCycleStatus') != 'complete'
                               or row.get('status', {}).get('recordingStatus') == 'notRecording'):
                continue
            key = str(uuid.uuid5(uuid.NAMESPACE_URL, f'autoclip:replay:{provider}:{channel}:{row["id"]}'))
            title = info.get('title', '')[:256]
            stmt = insert(ReplayArchive).values(id=key, provider=provider, channel=channel, title=title)
            db.execute(stmt.on_conflict_do_update(index_elements=['id'], set_={'title': title}))
            direct_ready = bool(twitch and row.get('viewable') == 'public' and row.get('stream_id'))
            duration_str = info.get('duration') if twitch else None
            meta_stmt = insert(ReplayArchiveMeta).values(
                archive_id=key, remote_id=str(row['id'])[:64], duration=duration_str, direct_ready=direct_ready
            )
            db.execute(meta_stmt.on_conflict_do_update(
                index_elements=['archive_id'],
                set_={'remote_id': str(row['id'])[:64], 'duration': duration_str, 'direct_ready': direct_ready},
            ))
            archive = db.get(ReplayArchive, key)
            pid = archive.project_id
            items.append({'id': key, 'title': title, 'date': info.get('created_at' if twitch else 'actualStartTime'),
                          **({'direct_video_id': row['id']} if direct_ready and twitch_replay_media.enabled() else {}),
                          'thumbnail_url': archive_thumbnail(twitch, info),
                          'duration': duration_str,
                          'processing': not twitch and row.get('status', {}).get('recordingStatus') == 'recording',
                          'project_id': pid if pid and db.get(Project, pid) else None})
        db.commit()
        choice = db.get(ChannelSelection, (provider, channel))
        chosen = db.get(ReplayArchive, choice.archive_id) if choice else None
        selected = None
        if chosen and not (chosen.project_id and db.get(Project, chosen.project_id)):
            selected = next((item for item in items if item['id'] == chosen.id and item.get('direct_video_id')), None)
            if selected is None:
                meta = db.get(ReplayArchiveMeta, chosen.id)
                selected = {'id': chosen.id, 'title': chosen.title}
                if twitch and twitch_replay_media.enabled() and meta and meta.direct_ready:
                    selected['direct_video_id'] = meta.remote_id
                    if meta.duration:
                        selected['duration'] = meta.duration
        return {'items': items, 'channel': account['name'], 'selected': selected, 'next': (body.get('pagination') or {}).get('cursor')
                if twitch else body.get('nextPageToken')}


def twitch_selected_source(db, video_id, requested_key):
    """Resolve a selected ended archive against the current channel before acquiring media."""
    with locks['twitch']:
        account = credentials('twitch')
        if not account:
            raise HTTPException(401, 'channel_reconnect')
        channel = account['channel']
        key = str(uuid.uuid5(uuid.NAMESPACE_URL, f'autoclip:replay:twitch:{channel}:{video_id}'))
        if key != requested_key:
            raise HTTPException(409, 'channel_mismatch')
        archive = db.get(ReplayArchive, key)
        if archive and archive.project_id and db.get(Project, archive.project_id):
            return {'project_id': archive.project_id}
        selection = db.get(ChannelSelection, ('twitch', channel))
        if not selection or selection.archive_id != key:
            raise HTTPException(409, 'channel_mismatch')
        if account['expires'] <= time.time() + 60:
            refresh('twitch', account)
        def fetch(path, params):
            status, body = authorized_get('twitch', account['access'], path, params)
            if status == 401:
                refresh('twitch', account)
                status, body = authorized_get('twitch', account['access'], path, params)
            check(status)
            if not isinstance(body.get('data'), list):
                raise HTTPException(502, 'channel_provider')
            return body['data']
        rows = fetch('videos', {'id': video_id})
        if len(rows) != 1:
            raise HTTPException(409, 'archive_unavailable')
        row = rows[0]
        if (row.get('user_id') != channel or row.get('id') != video_id or row.get('type') != 'archive'
                or row.get('viewable') != 'public' or not row.get('stream_id')):
            raise HTTPException(409, 'archive_unavailable')
        live = fetch('streams', {'user_id': channel})
        if any(item.get('user_id') != channel or not item.get('id') or item['id'] == row['stream_id'] for item in live):
            raise HTTPException(409, 'archive_unavailable')
        return {'archive_id': key, 'video_id': video_id, 'duration': row.get('duration')}


def claim(db, provider, key, data):
    """Serialize competing imports before any file handoff or job submission."""
    account = credentials(provider)
    if not account:
        raise HTTPException(401, 'channel_reconnect')
    if db.bind and db.bind.dialect.name == 'sqlite':
        if db.in_transaction():
            db.rollback()
        db.execute(text('BEGIN IMMEDIATE'))
    match = (ReplayArchive.id == key, ReplayArchive.channel == account['channel'], ReplayArchive.provider == provider)
    if db.execute(update(ReplayArchive).where(*match).values(title=ReplayArchive.title)).rowcount != 1:
        raise HTTPException(409, 'channel_mismatch')
    archive = db.get(ReplayArchive, key)
    old = db.get(Project, archive.project_id) if archive.project_id else None
    if old:
        db.rollback()
        return old, False
    data.name = archive.title[:200] or data.name
    data.settings['channel_replay_id'] = key
    project = Project(**ProjectService.project_fields(data))
    db.add(project)
    db.flush()
    archive.project_id = str(project.id)
    choice = db.get(ChannelSelection, (provider, archive.channel))
    if choice and choice.archive_id == key:
        db.delete(choice)
    return project, True


def disconnect(provider):
    with locks[provider]:
        cancel(provider)
        account = credentials(provider)
        if not account:
            return {'disconnected': True}
        cid, _ = config(provider)
        token = account['refresh'] or account['access']
        # Best-effort remote revoke so offline users or upstream 5xx never trap credentials locally.
        try:
            if provider == 'twitch':
                request('POST', TW_AUTH + 'revoke', data={'client_id': cid, 'token': account['access']})
            else:
                request('POST', 'https://oauth2.googleapis.com/revoke', data={'token': token})
        except HTTPException:
            pass
        credentials(provider, remove=True)
        return {'disconnected': True}

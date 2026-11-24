"""Read-only WebSocket 5.x client. Never infer missed transitions from status snapshots."""

import asyncio
import base64
import hashlib
import json
import logging
from pathlib import Path

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed
from . import settings, worker
from .session import Outputs

logger = logging.getLogger(__name__)
PREFIX = 'OBS_WEBSOCKET_OUTPUT_'


def digest64(value):
    return base64.b64encode(hashlib.sha256(value.encode()).digest()).decode()


async def receive(ws):
    return json.loads(await asyncio.wait_for(ws.recv(), 8))


async def identify(ws, cfg):
    hello = await receive(ws)
    if hello.get('op') != 0:
        raise ValueError('invalid hello')
    identity = {'rpcVersion': 1, 'eventSubscriptions': 64}
    auth = hello['d'].get('authentication')
    if auth:
        password = (
            await asyncio.to_thread(
                lambda: settings.keychain().get_password('AutoClip OBS', settings.credential_id())
            )
            if cfg['has_password']
            else ''
        )
        identity['authentication'] = digest64(digest64((password or '') + auth['salt']) + auth['challenge'])
    await ws.send(json.dumps({'op': 1, 'd': identity}))
    if (await receive(ws)).get('op') != 2:
        raise ValueError('not identified')


async def snapshot(ws, name, queued=None):
    await ws.send(json.dumps({'op': 6, 'd': {'requestType': name, 'requestId': name}}))
    for _ in range(32):
        msg = await receive(ws)
        if msg.get('op') == 5 and queued is not None:
            queued.append(msg['d'])
            continue
        data = msg['d']
        if msg['op'] != 7 or data['requestId'] != name or not data['requestStatus']['result']:
            raise ValueError('snapshot not stable')
        return data['responseData']
    raise ValueError('snapshot not stable')


class Monitor:
    def __init__(self):
        self.tasks = []
        self.changed = asyncio.Event()
        self.work = asyncio.Event()
        self.work.set()
        self.state = 'offline'
        self.phase = 'idle'
        self.version = ''
        self.directory = ''
        self.recording = False
        self.supported = False
        self.revision = ''
        self.closing = False

    def start(self):
        self.tasks = [asyncio.create_task(self.listen()), asyncio.create_task(self.drain())]

    async def stop(self):
        self.closing = True
        self.work.set()
        self.changed.set()
        if self.tasks:
            self.tasks[0].cancel()
            await asyncio.gather(*self.tasks, return_exceptions=True)

    async def drain(self):
        await asyncio.to_thread(worker.recover)
        while not self.closing:
            try:
                await self.work.wait()
                self.work.clear()
                batch = await asyncio.to_thread(worker.pending)
                if batch:
                    self.work.set()
                for cid in batch:
                    if self.closing:
                        return
                    await asyncio.to_thread(worker.process, cid, lambda: self.closing)
            except Exception as exc:
                logger.warning('OBS import worker: %s', type(exc).__name__)
            await asyncio.sleep(1)

    async def listen(self):
        delay = 1
        while not self.closing:
            self.changed.clear()
            try:
                cfg = await asyncio.to_thread(settings.read)
                if cfg['enabled']:
                    self.state = 'connecting'
                    await self.observe(cfg)
                else:
                    self.state = 'offline'
                    await self.changed.wait()
                delay = 1
            except Exception as exc:
                auth_error = isinstance(exc, ConnectionClosed) and exc.rcvd and exc.rcvd.code == 4009
                self.state = 'auth_error' if auth_error else 'disconnected'
                self.phase = 'unconfirmed'
                logger.info('OBS listener: %s', type(exc).__name__)
                try:
                    await asyncio.wait_for(self.changed.wait(), delay)
                except asyncio.TimeoutError:
                    pass
                delay = min(20, delay * 2)
            finally:
                self.directory = ''
                self.recording = self.supported = False

    async def observe(self, cfg):
        async with connect(
            f'ws://127.0.0.1:{cfg["port"]}', proxy=None, open_timeout=4, close_timeout=1, max_size=1024 * 1024
        ) as ws:
            await identify(ws, cfg)
            queued = []
            version = await snapshot(ws, 'GetVersion', queued)
            directory = (
                await snapshot(ws, 'GetRecordDirectory', queued)
                if 'GetRecordDirectory' in version['availableRequests']
                else {}
            )
            stream = await snapshot(ws, 'GetStreamStatus', queued)
            record = await snapshot(ws, 'GetRecordStatus', queued)
            self.version = version['obsVersion']
            self.supported = tuple(map(int, version['obsWebSocketVersion'].split('.')[:2])) >= (5, 5)
            self.directory = directory.get('recordDirectory', '')
            outputs = Outputs(stream['outputActive'], record['outputActive'])
            self.phase, self.recording = outputs.status, outputs.recording
            self.state, self.revision = 'connected', cfg['revision']

            async def handle_event(event):
                can_observe = bool(self.supported and self.directory)
                capture = outputs.event(event['eventType'], event['eventData'], armed=can_observe)
                self.phase, self.recording = outputs.status, outputs.recording
                if not capture:
                    return
                latest_cfg = await asyncio.to_thread(settings.read)
                try:
                    _, current_digest = await asyncio.to_thread(settings.overview)
                except (ValueError, OSError):
                    current_digest = ''
                automatic = bool(
                    latest_cfg['consent']
                    and latest_cfg['consent'] == current_digest
                    and latest_cfg['directory']
                    and Path(self.directory).resolve() == Path(latest_cfg['directory'])
                )
                if automatic:
                    await asyncio.to_thread(worker.save, capture, latest_cfg['consent_epoch'])
                    self.work.set()
                else:
                    await asyncio.to_thread(worker.save_manual, capture, self.directory)

            for buffered in queued:
                await handle_event(buffered)
            while not self.changed.is_set():
                try:
                    raw = await asyncio.wait_for(ws.recv(), 0.5)
                except asyncio.TimeoutError:
                    continue
                msg = json.loads(raw)
                if msg['op'] != 5:
                    continue
                await handle_event(msg['d'])

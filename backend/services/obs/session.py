"""Correlate two OBS outputs within one continuously observed WebSocket connection."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import time
import uuid


@dataclass
class Recording:
    started: float
    paused_at: float | None = None
    paused_seconds: float = 0
    split: bool = False

    def position(self, now: float) -> float:
        return (self.paused_at if self.paused_at is not None else now) - self.started - self.paused_seconds


@dataclass
class Capture:
    session_id: str
    path: str
    start: float
    end: float
    duration: float


@dataclass
class Broadcast:
    session_id: str
    recording: Recording | None = None
    start: float = 0
    end: float | None = None
    duration: float | None = None
    path: str = ''
    stopped: bool = False
    ambiguous: bool = False


class Outputs:
    def __init__(self, stream_active: bool, record_active: bool, *, clock: Callable = time.monotonic):
        self.clock = clock
        self.streaming = stream_active
        self.recording = record_active
        self.record: Recording | None = None
        self.broadcast: Broadcast | None = None
        self.status = 'unconfirmed' if stream_active or record_active else 'idle'

    def event(self, kind: str, data: dict, *, armed: bool) -> Capture | None:
        now = self.clock()
        state = data.get('outputState', '').removeprefix('OBS_WEBSOCKET_OUTPUT_')
        if kind == 'RecordFileChanged':
            if self.record:
                self.record.split = True
            return None
        if kind == 'StreamStateChanged':
            if state == 'STARTED' and not self.streaming:
                self.streaming = True
                # A still-open recording spans the new broadcast and its predecessor.
                shared = self.broadcast is not None or (self.recording and self.record is None)
                self.broadcast = Broadcast(
                    str(uuid.uuid4()),
                    self.record,
                    self.record.position(now) if self.record else 0,
                    ambiguous=shared or not armed,
                )
                self.status = 'live'
            elif state == 'STOPPING' and self.broadcast and self.record and self.broadcast.end is None:
                self.broadcast.end = self.record.position(now)
            elif state == 'STOPPED' and self.streaming:
                self.streaming = False
                if self.broadcast:
                    self.broadcast.stopped = True
                    if self.record and self.broadcast.end is None:
                        self.broadcast.end = self.record.position(now)
                    self.status = 'waiting_recording' if self.recording else 'idle'
        elif kind == 'RecordStateChanged':
            if state == 'STARTED' and not self.recording:
                self.recording = True
                self.record = Recording(now, split=self.streaming and self.broadcast is None)
                b = self.broadcast
                if b and self.streaming:
                    b.ambiguous |= b.recording is not None
                    b.recording = self.record
            elif state == 'PAUSED' and self.record and self.record.paused_at is None:
                self.record.paused_at = now
            elif state == 'RESUMED' and self.record and self.record.paused_at is not None:
                self.record.paused_seconds += now - self.record.paused_at
                self.record.paused_at = None
            elif state == 'STOPPED' and self.recording:
                b = self.broadcast
                if b and self.record and b.recording is self.record:
                    b.path = data.get('outputPath') or ''
                    b.duration = self.record.position(now)
                    if b.end is None:
                        b.end = b.duration
                self.recording = False
                self.record = None
        b = self.broadcast
        if not b or not b.stopped or self.recording:
            return None
        self.broadcast = None
        if not armed or b.ambiguous or not b.recording or b.recording.split or not b.path:
            self.status = 'unconfirmed'
            return None
        if b.end is None or b.duration is None or b.end <= b.start or not Path(b.path).is_absolute():
            self.status = 'unconfirmed'
            return None
        self.status = 'checking'
        return Capture(b.session_id, b.path, b.start, b.end, b.duration)

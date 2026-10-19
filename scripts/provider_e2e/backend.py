"""Start and stop an isolated desktop backend for one e2e case."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .http_util import get_json

ROOT = Path(__file__).resolve().parents[2]


def announced_port(text: str) -> str | None:
    for line in text.splitlines():
        if not line.startswith('PORT='):
            continue
        port = line.split('=', 1)[1].strip()
        if port.isdigit():
            return port
    return None


def backend_env(data_dir: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    for key in tuple(env):
        upper = key.upper()
        if upper.endswith(('_API_KEY', '_TOKEN')) or upper in {
            'OPENAI_API_KEY', 'DASHSCOPE_API_KEY', 'GEMINI_API_KEY', 'DEEPSEEK_API_KEY',
        }:
            env[key] = ''
    env.update({
        'AUTOCLIP_DESKTOP_MODE': 'true',
        'AUTOCLIP_MODE': 'desktop',
        'AUTOCLIP_DATA_DIR': str(data_dir),
        'AUTOCLIP_APP_DIR': str(data_dir),
        'AUTOCLIP_HOST': '127.0.0.1',
        'DATABASE_URL': 'sqlite:///' + str(data_dir / 'autoclip.db').replace('\\', '/'),
        'SENTRY_DSN': '',
        'VITE_PUBLIC_SENTRY_DSN': '',
        'VITE_PUBLIC_POSTHOG_KEY': '',
        'SENTRY_UPLOAD_SOURCEMAPS': 'false',
        'PYTHONDONTWRITEBYTECODE': '1',
        'PYTHONUNBUFFERED': '1',
        'PYTHONPATH': str(ROOT),
    })
    if extra:
        env.update(extra)
    return env


class DesktopBackend:
    def __init__(self, data_dir: Path, python: str = sys.executable) -> None:
        self.data_dir = data_dir
        self.python = python
        self.process: subprocess.Popen[bytes] | None = None
        self.base_url = ''
        self._log = None
        self.log_path = data_dir / 'logs' / 'provider-e2e-backend.log'
        # stdout (PORT=/BACKEND_URL= announcements) gets its own file. With stdout and
        # stderr merged, a log line from another thread could land between print()'s "PORT=N"
        # and its newline ("PORT=444652026-10-16 ... INFO"), the port never parsed and the case
        # timed out after 120 s. The desktop app already reads them as separate pipes.
        self.stdout_path = data_dir / 'logs' / 'provider-e2e-stdout.log'
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._out = None

    def start(self, timeout: float = 120) -> str:
        self.log_path.write_bytes(b'')
        self.stdout_path.write_bytes(b'')
        log = self.log_path.open('ab')
        self._log = log
        self._out = self.stdout_path.open('ab')
        self.process = subprocess.Popen(
            [self.python, '-u', '-m', 'backend.desktop_main'],
            cwd=str(ROOT),
            env=backend_env(self.data_dir),
            stdout=self._out,
            stderr=log,
        )
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f'desktop backend exited {self.process.returncode} before announcing PORT')
            text = self.stdout_path.read_text(encoding='utf-8', errors='replace')
            port = announced_port(text)
            if port:
                self.base_url = f'http://127.0.0.1:{port}'
                self._wait_health(deadline)
                return self.base_url
            time.sleep(0.1)
        raise TimeoutError('desktop backend did not print PORT=')

    def _wait_health(self, deadline: float) -> None:
        last = ''
        while time.time() < deadline:
            try:
                payload = get_json(self.base_url + '/health', timeout=2)
                if payload.get('status') in {'ok', 'healthy'}:
                    return
                last = str(payload)
            except Exception as error:  # noqa: BLE001 - startup race
                last = type(error).__name__
            time.sleep(0.2)
        raise TimeoutError(f'desktop backend health check failed: {last}')

    def kill(self) -> None:
        if self.process is None or self.process.poll() is not None:
            self._close_log()
            return
        self.process.send_signal(signal.SIGKILL)
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        self._close_log()

    def stop(self, timeout: float = 10) -> None:
        if self.process is None or self.process.poll() is not None:
            self._close_log()
            return
        self.process.send_signal(signal.SIGTERM)
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.kill()
            return
        self._close_log()

    def _close_log(self) -> None:
        for name in ('_log', '_out'):
            handle = getattr(self, name, None)
            if handle is not None:
                handle.close()
                setattr(self, name, None)

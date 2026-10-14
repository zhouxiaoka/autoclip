"""stdlib HTTP helpers for the studio API. Never log request bodies that may contain keys."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class HttpError(RuntimeError):
    def __init__(self, status: int, body: str) -> None:
        super().__init__(f'HTTP {status}')
        self.status = status
        self.body = body


def get_json(url: str, timeout: float = 15) -> Any:
    request = Request(url, method='GET', headers={'Accept': 'application/json'})
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8') or '{}')
    except HTTPError as error:
        raise HttpError(error.code, error.read().decode('utf-8', errors='replace')) from error
    except URLError as error:
        raise RuntimeError(f'GET {url} failed: {error.reason}') from error


def post_multipart(url: str, fields: dict[str, Any], files: dict[str, Path], timeout: float = 60) -> Any:
    boundary = '----autoclipe2e' + uuid.uuid4().hex
    chunks: list[bytes] = []
    for name, value in fields.items():
        if value is None:
            continue
        if isinstance(value, bool):
            value = 'true' if value else 'false'
        chunks.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode('utf-8')
        )
    for name, path in files.items():
        filename = path.name
        mime = 'text/plain' if path.suffix == '.srt' else 'video/mp4'
        header = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f'Content-Type: {mime}\r\n\r\n'
        ).encode('utf-8')
        chunks.append(header + path.read_bytes() + b'\r\n')
    chunks.append(f'--{boundary}--\r\n'.encode('ascii'))
    body = b''.join(chunks)
    request = Request(url, data=body, method='POST', headers={
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Accept': 'application/json',
    })
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8') or '{}')
    except HTTPError as error:
        raise HttpError(error.code, error.read().decode('utf-8', errors='replace')) from error
    except URLError as error:
        raise RuntimeError(f'POST {url} failed: {error.reason}') from error

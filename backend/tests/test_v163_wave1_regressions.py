"""v1.6.3 Wave 1 regressions:
1. studio_error_code must not collapse disk-full, timeout, or direct network/SSL errors into 'unexpected' (#694).
2. Provider validation & model fetch must fall back to direct connection (trust_env=False) when a stale/broken
   system proxy breaks connection to reachable endpoints such as api.deepseek.com (#704).
"""
from __future__ import annotations

import errno
import ssl
import httpx

from backend.core import sentry_setup
from backend.core import provider_model_fetch
from backend.services import provider_validation


def test_studio_error_code_classifies_disk_timeout_and_network_instead_of_unexpected():
    enospc = OSError(errno.ENOSPC, "No space left on device")
    assert sentry_setup.studio_error_code(enospc) == "disk"

    win_disk = OSError("There is not enough space on the disk")
    win_disk.winerror = 112
    assert sentry_setup.studio_error_code(win_disk) == "disk"

    assert sentry_setup.studio_error_code(httpx.ReadTimeout("read timed out")) == "timeout"
    assert sentry_setup.studio_error_code(httpx.ConnectTimeout("connect timed out")) == "timeout"

    assert sentry_setup.studio_error_code(httpx.ConnectError("connection failed")) == "network"
    assert sentry_setup.studio_error_code(httpx.ProxyError("proxy refused")) == "network"
    assert sentry_setup.studio_error_code(ConnectionResetError("reset by peer")) == "network"
    assert sentry_setup.studio_error_code(ssl.SSLError("EOF occurred in violation of protocol")) == "network"


def test_probe_chat_falls_back_to_direct_when_proxy_fails(monkeypatch):
    seen_trust_env: list[bool] = []

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "application/json"}
        text = '{"choices":[{"message":{"content":"ok"}}]}'

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    class FakeClient:
        def __init__(self, *, timeout=None, trust_env=True, **kwargs):
            self.trust_env = trust_env
            seen_trust_env.append(trust_env)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json=None, headers=None):
            if self.trust_env:
                raise httpx.ProxyError("Cannot connect to proxy 127.0.0.1:7890")
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)

    err = provider_validation._probe(
        "https://api.deepseek.com/v1",
        "sk-test-key",
        "deepseek-flash",
        "deepseek",
    )
    assert err is None
    assert seen_trust_env == [True, False]


def test_default_http_get_falls_back_to_direct_when_proxy_fails(monkeypatch):
    seen_trust_env: list[bool] = []

    class FakeResponse:
        status_code = 200
        text = '{"data":[]}'

    class FakeClient:
        def __init__(self, *, timeout=None, trust_env=True, **kwargs):
            self.trust_env = trust_env
            seen_trust_env.append(trust_env)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, headers=None):
            if self.trust_env:
                raise httpx.ProxyError("Cannot connect to proxy")
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)

    resp = provider_model_fetch._default_http_get(
        "https://api.deepseek.com/v1/models",
        headers={"Authorization": "Bearer sk-test"},
        timeout=8.0,
        trust_env=True,
    )
    assert resp.status_code == 200
    assert seen_trust_env == [True, False]

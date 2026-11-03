"""pytest plugin for test_r32_419_telemetry_isolation (#419 extension), loaded with -p in a child pytest run.
Nothing can leave the machine: every sentry_sdk.init gets a counting fake transport, and urllib.request.urlopen /
non-loopback socket connects are counted and refused (loopback is refused and counted apart). After the run it records how many network calls were attempted, how many
times Sentry was initialized, whether a Sentry client is still bound and whether the MCP telemetry worker (the only
long-lived PostHog client in the backend) was started; results go to $TELEMETRY_PROBE_OUT as JSON."""
import json
import os
import socket
import urllib.error
import urllib.request

import sentry_sdk

from backend.tests.sentry_leak_probe import CountingTransport

STATE = {'network_calls': [], 'loopback_connects': 0, 'sentry_inits': 0, 'sentry_client_active': False, 'posthog_worker_started': False}

_real_init = sentry_sdk.init


def _init(*args, **options):
    STATE['sentry_inits'] += 1
    options['transport'] = CountingTransport
    return _real_init(*args, **options)


def _urlopen(request, *args, **kwargs):
    url = request.full_url if isinstance(request, urllib.request.Request) else str(request)
    STATE['network_calls'].append('urlopen ' + url.split('://', 1)[-1].split('/', 1)[0])  # host only
    raise urllib.error.URLError('network disabled by telemetry_leak_probe')


def _connect(self, address, *args, **kwargs):
    # Loopback (the local Redis that create_app probes) is not telemetry; it is refused too, but only counted apart.
    host = address[0] if isinstance(address, tuple) else 'unix'
    if host in ('127.0.0.1', '::1', 'localhost', 'unix'):
        STATE['loopback_connects'] += 1
    else:
        STATE['network_calls'].append('connect')
    raise OSError('network disabled by telemetry_leak_probe')


def pytest_configure(config):
    sentry_sdk.init = _init
    urllib.request.urlopen = _urlopen
    socket.socket.connect = _connect


def pytest_sessionfinish(session):
    try:
        from backend.services import mcp_telemetry
        mcp_telemetry.flush(1)
        STATE['posthog_worker_started'] = mcp_telemetry._worker is not None
    except Exception as error:  # noqa: BLE001 - the probe reports, never raises
        STATE['probe_error'] = type(error).__name__
    sentry_sdk.flush()
    STATE['sentry_client_active'] = sentry_sdk.get_client().is_active()
    with open(os.environ['TELEMETRY_PROBE_OUT'], 'w', encoding='utf-8') as handle:
        json.dump(STATE, handle)

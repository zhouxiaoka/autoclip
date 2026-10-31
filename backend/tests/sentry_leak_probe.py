"""pytest plugin for test_r31_419_sentry_isolation (-pre #419), loaded with -p in a child pytest run.
Every sentry_sdk.init gets a counting fake transport, so nothing can leave the machine. After each test
it records whether an SDK client is still bound or sentry_setup still thinks it is initialized, and asks
the bound client (if any) to capture one exception; results go to $SENTRY_PROBE_OUT as JSON."""
import json
import os

import pytest
import sentry_sdk
from sentry_sdk.transport import Transport

ENVELOPES = []
STATE = {'envelopes': 0, 'client_bound_after': [], 'initialized_after': [], 'inits': 0}


class CountingTransport(Transport):
    def capture_envelope(self, envelope):
        ENVELOPES.append(envelope)

    def flush(self, timeout, callback=None):
        return None

    def kill(self):
        return None


_real_init = sentry_sdk.init


def _init(*args, **options):
    STATE['inits'] += 1
    options['transport'] = CountingTransport
    return _real_init(*args, **options)


def pytest_configure(config):
    sentry_sdk.init = _init  # only when loaded as a plugin (-p), not when a test imports CountingTransport


@pytest.hookimpl(trylast=True)
def pytest_runtest_logreport(report):
    if report.when != 'teardown':
        return
    from backend.core import sentry_setup
    if sentry_sdk.get_client().is_active():
        STATE['client_bound_after'].append(report.nodeid)
        sentry_sdk.capture_exception(ValueError('probe'))
        sentry_sdk.flush()
    if sentry_setup._initialized:
        STATE['initialized_after'].append(report.nodeid)


def pytest_sessionfinish(session):
    sentry_sdk.flush()
    STATE['envelopes'] = len(ENVELOPES)
    with open(os.environ['SENTRY_PROBE_OUT'], 'w', encoding='utf-8') as handle:
        json.dump(STATE, handle)

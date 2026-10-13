"""W157 IA: the upgrade check must judge the updater manifest, not the VM's network to GitHub."""
import importlib.util
from pathlib import Path

import pytest

PROBE = Path(__file__).resolve().parents[2] / 'scripts' / 'winqa' / 'py' / 'updater_manifest.py'


@pytest.fixture(scope='module')
def probe():
    spec = importlib.util.spec_from_file_location('winqa_probe_under_test', PROBE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LIVE_156 = {'version': '1.5.6', 'pub_date': '2026-10-09T00:00:00Z', 'platforms': {
    'windows-x86_64': {'url': 'https://github.com/zhouxiaoka/autoclip/releases/download/v1.5.6/a.nsis.zip', 'signature': 'sig'},
    'darwin-aarch64': {'url': 'https://github.com/zhouxiaoka/autoclip/releases/download/v1.5.6/a.app.tar.gz', 'signature': 'sig'}}}


def test_older_live_manifest_is_readable(probe):
    # The live latest.json stays 1.5.6 while 1.5.7 is under test: that is still a readable manifest.
    assert probe.judge_updater_manifest(200, LIVE_156, 'windows-x86_64') == 'ok'
    assert probe.judge_updater_manifest(200, LIVE_156, 'darwin-aarch64') == 'ok'


@pytest.mark.parametrize('status,manifest,reason', [
    (404, LIVE_156, 'http_404'),
    (200, None, 'not_json_object'),
    (200, {**LIVE_156, 'version': 'latest'}, 'bad_version'),
    (200, {**LIVE_156, 'platforms': {}}, 'platform_missing'),
    (200, {**LIVE_156, 'platforms': {'windows-x86_64': {'url': 'https://x'}}}, 'platform_entry_incomplete'),
])
def test_broken_manifests_are_named(probe, status, manifest, reason):
    assert probe.judge_updater_manifest(status, manifest, 'windows-x86_64') == reason

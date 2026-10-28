"""MCPB manifest contract for the thin Smithery stdio bundle. No publish."""
import importlib.util
import json
import os
from pathlib import Path
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / 'mcpb'
PYPI_NAME = 'autoclip-mcp'


def _manifest() -> dict:
    return json.loads((BUNDLE / 'manifest.json').read_text(encoding='utf-8'))


def _bundle_project() -> dict:
    return tomllib.loads((BUNDLE / 'pyproject.toml').read_text(encoding='utf-8'))


def _load_entry():
    spec = importlib.util.spec_from_file_location('autoclip_mcpb_entry', BUNDLE / 'src' / 'server.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.stdlib_only
def test_mcpb_manifest_is_a_thin_pypi_launcher():
    root = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']
    product = (ROOT / 'backend' / '__init__.py').read_text(encoding='utf-8')
    manifest = _manifest()
    project = _bundle_project()['project']
    server = manifest['server']
    api_key = manifest['user_config']['api_key']

    assert '__version__ = "1.5.7"' in product
    assert manifest['manifest_version'] == '0.4'
    assert manifest['name'] == PYPI_NAME
    assert manifest['version'] == '1.5.7'
    assert 'tools' not in manifest
    assert manifest['tools_generated'] is True
    assert server['type'] == 'python'
    assert server['entry_point'] == 'src/server.py'
    assert server['mcp_config']['command'] == 'uv'
    assert server['mcp_config']['args'] == ['run', '--directory', '${__dirname}', 'src/server.py']
    assert server['mcp_config']['env'] == {'AUTOCLIP_API_KEY': '${user_config.api_key}'}
    assert api_key['type'] == 'string'
    assert api_key['sensitive'] is True
    assert api_key['required'] is False
    assert 'default' not in api_key
    assert project['name'] == 'autoclip-mcpb'
    assert project['dependencies'] == [f'{PYPI_NAME}=={root["version"]}']
    assert (BUNDLE / 'icon.png').is_file()
    assert (BUNDLE / server['entry_point']).is_file()
    assert not (BUNDLE / 'backend').exists()
    entry = (BUNDLE / 'src' / 'server.py').read_text(encoding='utf-8')
    assert 'from backend.mcp_server import main as mcp_main' in entry


@pytest.mark.stdlib_only
def test_blank_user_config_does_not_override_desktop_settings(monkeypatch):
    entry = _load_entry()
    monkeypatch.setenv('AUTOCLIP_API_KEY', '   ')
    entry._drop_unset_api_key()
    assert 'AUTOCLIP_API_KEY' not in os.environ

    monkeypatch.setenv('AUTOCLIP_API_KEY', '${user_config.api_key}')
    entry._drop_unset_api_key()
    assert 'AUTOCLIP_API_KEY' not in os.environ

    monkeypatch.setenv('AUTOCLIP_API_KEY', 'sk-real-key')
    entry._drop_unset_api_key()
    assert os.environ['AUTOCLIP_API_KEY'] == 'sk-real-key'


@pytest.mark.stdlib_only
def test_docs_explain_pack_and_do_not_publish():
    guide = (ROOT / 'docs' / 'CLI_AND_MCP.md').read_text(encoding='utf-8')
    readme = (ROOT / 'README.md').read_text(encoding='utf-8')
    english = (ROOT / 'README-EN.md').read_text(encoding='utf-8')
    script = (ROOT / 'scripts' / 'pack_mcpb.py').read_text(encoding='utf-8')
    ignore = (ROOT / '.gitignore').read_text(encoding='utf-8')
    for text in (guide, readme, english):
        assert 'smithery mcp publish' in text
        assert 'pack_mcpb.py' in text
    assert 'smithery mcp publish' in script
    assert "['smithery'" not in script
    assert '["smithery"' not in script
    bundled = '\n'.join(
        path.read_text(encoding='utf-8')
        for path in BUNDLE.rglob('*')
        if path.is_file() and path.suffix in {'.py', '.json', '.md', '.toml'}
    )
    assert 'SMITHERY_API_KEY=' not in bundled
    assert 'sk-' not in bundled
    assert 'dist/' in ignore
    assert '*.mcpb' in ignore

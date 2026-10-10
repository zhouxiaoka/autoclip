"""Agent-facing docs must read the installed version instead of pinning one."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SURFACES = (
    'skills/autoclip/SKILL.md',
    'docs/CLI_AND_MCP.md',
    'README.md',
    'README-EN.md',
    'README-JA.md',
    'README-KO.md',
    'README-ES.md',
    'README-PT.md',
    'README-RU.md',
    'README-FR.md',
)
RELEASE_URL = re.compile(r'releases/(?:tag|download)/v\d+\.\d+\.\d+')
WHEEL_PIN = re.compile(r'autoclip-\d+\.\d+\.\d+-')
OLD_WHEEL = 'autoclip-*-py3-none-any.whl'
WHEEL_GLOB = 'autoclip_mcp-*-py3-none-any.whl'
STATED_VERSION = re.compile(r'(?:核对为|统一为|都为)\s*\d+\.\d+\.\d+')


def _product_version() -> str:
    pyproject = (ROOT / 'pyproject.toml').read_text(encoding='utf-8')
    match = re.search(r'^\[project\][^\[]*?^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE | re.DOTALL)
    assert match, 'pyproject.toml has no project version'
    init = (ROOT / 'backend/__init__.py').read_text(encoding='utf-8')
    package = re.search(r'^__version__\s*=\s*"([^"]+)"', init, re.MULTILINE)
    assert package and package.group(1) == match.group(1)
    return match.group(1)


@pytest.mark.stdlib_only
def test_agent_docs_do_not_hardcode_a_product_version():
    version = _product_version()
    pinned = re.compile(rf'(?<![\d.]){re.escape(version)}(?![\d.])')
    for relative in SURFACES:
        text = (ROOT / relative).read_text(encoding='utf-8')
        assert pinned.search(text) is None, relative
        assert '1.5.0' not in text, relative
        assert RELEASE_URL.search(text) is None, relative
        assert WHEEL_PIN.search(text) is None, relative
        assert OLD_WHEEL not in text, relative
        assert STATED_VERSION.search(text) is None, relative
        if relative.startswith('README'):
            assert WHEEL_GLOB in text, relative
    skill = (ROOT / 'skills/autoclip/SKILL.md').read_text(encoding='utf-8')
    guide = (ROOT / 'docs/CLI_AND_MCP.md').read_text(encoding='utf-8')
    readme = (ROOT / 'README.md').read_text(encoding='utf-8')
    assert 'get_version' in skill and 'autoclip --version' in skill
    assert 'get_version' in guide and 'autoclip --version' in guide
    assert 'autoclip --version' in readme and 'releases/latest' in readme

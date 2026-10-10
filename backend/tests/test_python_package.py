"""PyPI metadata for `uvx autoclip-mcp` and the skill install command. No publish."""
from pathlib import Path
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEV_PACKAGES = {'pytest', 'pytest-cov', 'pytest-mock'}
INSTALL_COMMANDS = ('uvx autoclip-mcp', 'npx skills add zhouxiaoka/autoclip')
WHEEL_GLOB = 'autoclip_mcp-*-py3-none-any.whl'


def runtime_requirements(text: str) -> list[str]:
    found = []
    for line in text.splitlines():
        raw = line.strip()
        if not raw or raw.startswith('#'):
            continue
        name = raw.split('==', 1)[0].split('[', 1)[0].strip()
        if name in DEV_PACKAGES:
            continue
        found.append(raw)
    return found


@pytest.mark.stdlib_only
def test_distribution_is_autoclip_mcp_and_keeps_runtime_pins():
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']
    version = (ROOT / 'backend' / '__init__.py').read_text(encoding='utf-8')
    assert project['name'] == 'autoclip-mcp'
    assert f'__version__ = "{project["version"]}"' in version
    assert project['scripts']['autoclip'] == 'backend.cli:main'
    assert project['scripts']['autoclip-mcp'] == 'backend.mcp_server:main'
    dependencies = project['dependencies']
    assert dependencies == runtime_requirements((ROOT / 'requirements.txt').read_text(encoding='utf-8'))
    assert 'mcp==2.1.1' in dependencies
    assert not any(item.split('==', 1)[0].split('[', 1)[0] in DEV_PACKAGES for item in dependencies)

    from scripts.build_python_release import expected_wheel_name
    assert expected_wheel_name(project['version']) == f'autoclip_mcp-{project["version"]}-py3-none-any.whl'
    for relative in (
        '.github/workflows/ci.yml',
        '.github/workflows/desktop-build.yml',
        '.github/workflows/windows-install-smoke.yml',
    ):
        assert WHEEL_GLOB in (ROOT / relative).read_text(encoding='utf-8')


@pytest.mark.stdlib_only
def test_docs_advertise_the_one_line_install_commands():
    surfaces = [
        ROOT / 'README.md',
        ROOT / 'README-EN.md',
        ROOT / 'README-JA.md',
        ROOT / 'README-KO.md',
        ROOT / 'README-ES.md',
        ROOT / 'README-PT.md',
        ROOT / 'README-RU.md',
        ROOT / 'README-FR.md',
        ROOT / 'docs' / 'CLI_AND_MCP.md',
        ROOT / 'skills' / 'autoclip' / 'SKILL.md',
    ]
    for path in surfaces:
        text = path.read_text(encoding='utf-8')
        for command in INSTALL_COMMANDS:
            assert command in text, path.name
        assert '即将提供' not in text, path.name
        assert 'coming soon' not in text.lower(), path.name
        assert 'python -m pip install --no-deps .' in text, path.name
    notes = (ROOT / 'scripts' / 'release_notes.py').read_text(encoding='utf-8')
    for command in INSTALL_COMMANDS:
        assert command in notes
    assert '即将提供' not in notes
    assert 'python -m pip install --no-deps .' in notes

"""Shipping templates load, and a broken folder never joins the candidate set."""
from pathlib import Path

import pytest
import yaml

from backend.services.studio.templates.registry import TemplateRegistryError, load_directory, load_folder, load_shipping
from backend.services.studio.templates.spec import TemplateSpec

ROOT = Path(__file__).resolve().parents[1] / 'assets' / 'templates'


def test_shipping_templates_are_editorial_and_street_only():
    loaded = load_shipping()
    assert set(loaded) == {'editorial', 'street'}
    editorial, street = loaded['editorial'], loaded['street']
    assert editorial.name.zh == '杂志风' and street.name.zh == '街头快剪'
    assert editorial.canvas.overlay_px == (720, 1280) and editorial.canvas.fps == 30
    assert editorial.overlay.slots['subtitle'].max_rows == 2
    assert street.overlay.limits['sticker_max'] == 2
    assert street.audio.bgm == 'none' and street.audio.optional_bed is True
    assert editorial.audio.bgm == 'none' and editorial.audio.optional_bed is False
    assert editorial.base.zoom.mode == 'creep' and editorial.base.zoom.creep == 0.07
    assert street.base.zoom.step == [1.0, 1.22]
    assert 'podcast' not in loaded


def test_page_contract_exposes_the_three_hooks():
    for name in ('editorial', 'street'):
        script = (ROOT / name / 'template.js').read_text(encoding='utf-8')
        assert 'window.setData' in script and 'window.renderFrame' in script and 'window.occupiedRects' in script
        assert 'Date.now' not in script and 'performance.now' not in script


def _copy_shipping(tmp_path: Path) -> Path:
    target = tmp_path / 'templates'
    for name in ('editorial', 'street'):
        folder = target / name
        folder.mkdir(parents=True)
        for item in (ROOT / name).iterdir():
            (folder / item.name).write_bytes(item.read_bytes())
    return target


def test_a_template_that_fails_validation_is_not_loaded(tmp_path):
    root = _copy_shipping(tmp_path)
    spec = yaml.safe_load((root / 'editorial' / 'template.yaml').read_text(encoding='utf-8'))
    spec['id'] = 'podcast'
    (root / 'editorial' / 'template.yaml').write_text(yaml.safe_dump(spec, allow_unicode=True), encoding='utf-8')
    with pytest.raises(TemplateRegistryError, match='editorial'):
        load_directory(root)


def test_missing_render_hook_is_rejected(tmp_path):
    folder = tmp_path / 'editorial'
    folder.mkdir()
    for item in (ROOT / 'editorial').iterdir():
        (folder / item.name).write_bytes(item.read_bytes())
    (folder / 'template.js').write_text('window.setData = function () {};\n', encoding='utf-8')
    with pytest.raises(TemplateRegistryError, match='renderFrame'):
        load_folder(folder)


def test_unknown_field_and_odd_canvas_are_rejected():
    raw = yaml.safe_load((ROOT / 'street' / 'template.yaml').read_text(encoding='utf-8'))
    raw['fields']['optional'].append('publish_caption')
    with pytest.raises(Exception):
        TemplateSpec.model_validate(raw)
    raw = yaml.safe_load((ROOT / 'street' / 'template.yaml').read_text(encoding='utf-8'))
    raw['canvas']['overlay_px'] = [721, 1280]
    with pytest.raises(Exception):
        TemplateSpec.model_validate(raw)

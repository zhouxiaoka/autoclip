"""Unit & integration tests for Packaging Engine v2 (variables, ACMotion) and In-App AI Style Cloner."""
from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from backend.services.studio.templates import catalog, cloner, registry, user_vars
from backend.services.studio.templates.spec import TemplateVariableSpec


def test_template_variable_spec_and_user_vars_persistence(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    bp = cloner.StyleBlueprint(
        name_zh='霓虹穿影',
        name_en='Neon Depth',
        accent_color='#2d6bff',
        depth_enabled=True,
        grain_enabled=False,
        font_scale='M',
    )
    tpl_dir = cloner.synthesize_template_dir('neon_depth_test', bp, tmp_path / 'neon_depth_test')
    spec = registry.load_folder(tpl_dir)
    assert len(spec.variables) == 4
    assert spec.default_vars() == {
        'accent_color': '#2D6BFF',
        'font_scale': 'M',
        'depth_enabled': True,
        'grain_enabled': False,
    }
    assert spec.base.subject_layer is True
    assert spec.overlay.back_entry == 'back.html'

    # Persist overrides + verify invalid values are safely ignored
    merged = user_vars.write_user_vars(
        spec,
        {'accent_color': '#34D399', 'font_scale': 'L', 'grain_enabled': True, 'accent_color_bad': 'oops', 'unknown': 1},
        user_root=tmp_path / 'templates',
    )
    assert merged['accent_color'] == '#34D399'
    assert merged['font_scale'] == 'L'
    assert merged['grain_enabled'] is True
    assert merged['depth_enabled'] is True

    # Reload from disk
    again = user_vars.resolved_vars(spec, user_root=tmp_path / 'templates')
    assert again == merged


def test_variable_spec_rejects_invalid_color():
    with pytest.raises(Exception):
        TemplateVariableSpec(
            key='accent_color',
            kind='color',
            label={'zh': '颜色', 'en': 'Color'},
            default='not-a-hex',
        )


def test_clone_refine_revert_save_and_export_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    user_root = tmp_path / 'templates'

    def fake_vision(content):
        return {
            'name_zh': '金句跳词',
            'name_en': 'Gold Pop',
            'desc_zh': '高对比亮黄跳词风格',
            'desc_en': 'High-contrast gold kinetic caption style',
            'accent_color': '#FFE548',
            'caption_motion': 'karaoke_pill',
            'header_style': 'pill_hook',
            'depth_enabled': False,
        }

    job = cloner.start_clone_job(
        prompt_hint='亮黄跳词风格',
        depth_mode='off',
        render_preview=False,
        vision_caller=fake_vision,
        sync_run=True,
    )
    assert job['status'] == 'ready'
    assert job['revision'] == 1
    assert job['can_undo'] is False
    assert job['blueprint']['accent_color'] == '#FFE548'

    # Refine via variable override (0-token)
    r2 = cloner.refine_clone_job(
        job['job_id'],
        variable_overrides={'accent_color': '#34D399', 'font_scale': 'L'},
        render_preview=False,
    )
    assert r2['revision'] == 2
    assert r2['can_undo'] is True
    assert r2['blueprint']['accent_color'] == '#34D399'
    assert r2['blueprint']['font_scale'] == 'L'

    # Undo back to revision 1
    rev1 = cloner.revert_clone_job(job['job_id'], render_preview=False)
    assert rev1['revision'] == 1
    assert rev1['can_undo'] is False
    assert rev1['blueprint']['accent_color'] == '#FFE548'

    # Save into user_templates
    saved = cloner.save_clone_job(
        job['job_id'],
        name_zh='我的金句',
        name_en='My Gold',
        user_root=user_root,
    )
    tid = saved['installed']
    assert (user_root / tid / 'template.yaml').is_file()
    loaded = registry.get_loaded(tid, user_root=user_root)
    assert loaded is not None
    assert loaded.spec.name.zh == '我的金句'
    assert loaded.spec.name.en == 'My Gold'

    # Export as .zip and verify valid archive structure + re-importable via catalog
    fname, zbytes = cloner.export_template_zip(tid, user_root=user_root)
    assert fname.endswith('.zip')
    with zipfile.ZipFile(BytesIO(zbytes)) as zf:
        names = set(zf.namelist())
        assert f'{tid}/template.yaml' in names
        assert f'{tid}/ac-template-sdk.js' in names
        assert f'{tid}/template.js' in names

    # Re-import into a fresh isolated user_root
    other_root = tmp_path / 'other_user_templates'
    reimported = catalog.install_from_archive(zbytes, source_url='local-upload', user_root=other_root)
    assert reimported.spec.id == tid

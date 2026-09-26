"""Offline regressions for filesystem and saved-credential boundaries."""
import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.core.path_utils import get_project_directory
from backend.schemas.clip import ClipCreate, ClipUpdate
from backend.schemas.collection import CollectionCreate, CollectionUpdate
from backend.services.storage_service import StorageService


@pytest.mark.parametrize('project_id', ['..', '.', '../other', r'..\other', '/tmp/x', r'C:\x', 'C:x', 'foo.', '', 'a\x00b'])
def test_project_ids_cannot_change_directory(monkeypatch, tmp_path, project_id):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    with pytest.raises(ValueError):
        get_project_directory(project_id)


def test_project_and_json_symlink_containment(monkeypatch, tmp_path):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'data'))
    service = StorageService('local-test_1')
    metadata = service.save_metadata({'ok': True}, 'step1')
    assert service.get_file_content(metadata) == {'ok': True}
    secret = tmp_path / 'secret.json'
    secret.write_text('{"secret": true}')
    assert service.get_file_content(str(secret)) is None
    other = StorageService('other')
    assert service.get_file_content(other.save_metadata({'secret': True}, 'step')) is None
    link = service.project_dir / 'linked.json'
    link.symlink_to(secret)
    assert service.get_file_content(str(link)) is None
    (service.project_dir.parent / 'escape').symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        get_project_directory('escape')


@pytest.mark.parametrize('schema, kwargs, field', [
    (ClipUpdate, {}, 'clip_metadata'),
    (ClipCreate, dict(project_id='p1', title='t', description='d', start_time=0, end_time=1, duration=1), 'clip_metadata'),
    (CollectionUpdate, {}, 'metadata'),
    (CollectionCreate, dict(project_id='p1', name='n'), 'metadata'),
])
def test_clients_cannot_supply_storage_locator(schema, kwargs, field):
    with pytest.raises(ValidationError, match='managed by the server'):
        schema(**kwargs, **{field: {'metadata_file': '/tmp/secret.json'}})
    assert getattr(schema(**kwargs, **{field: {'custom': 'kept'}}), field) == {'custom': 'kept'}


@pytest.mark.parametrize('filename', ['../secret.json', r'..\secret.json', r'C:\secret.json', '/tmp/secret.json'])
def test_project_file_rejects_filename_paths(monkeypatch, tmp_path, filename):
    from backend.api.v1.projects import get_project_file
    from fastapi import HTTPException
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_project_file('p1', filename, None))
    assert exc.value.status_code == 400


def test_project_file_keeps_normal_read_and_blocks_symlink(monkeypatch, tmp_path):
    from backend.api.v1.projects import get_project_file
    from fastapi import HTTPException
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'data'))
    pdir = get_project_directory('p1')
    (pdir / 'normal.json').write_text('{"ok": true}')
    assert asyncio.run(get_project_file('p1', 'normal.json', None)) == {'ok': True}
    secret = tmp_path / 'secret.json'
    secret.write_text('{"secret": true}')
    (pdir / 'secret.json').symlink_to(secret)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_project_file('p1', 'secret.json', None))
    assert exc.value.status_code == 404


@pytest.mark.parametrize('requested, saved, explicit, expected', [
    ('https://evil.test/v1', '', '', ''),
    ('https://api.openai.com.evil.test/v1', '', '', ''),
    ('https://api.openai.com@evil.test/v1', '', '', ''),
    ('http://api.openai.com/v1', '', '', ''),
    ('https://api.openai.com/v1/', '', '', 'saved-secret'),
    ('https://custom.test/v1', 'https://custom.test/v1/', '', 'saved-secret'),
    ('https://custom.test/other', 'https://custom.test/v1', '', ''),
    ('https://evil.test/v1', '', 'explicit-secret', 'explicit-secret'),
])
def test_model_discovery_binds_saved_secret(monkeypatch, requested, saved, explicit, expected):
    from backend.api.v1 import settings as api
    from backend.core import model_catalog
    settings = api.DesktopSettings()
    settings.api.api_provider = 'openai'
    settings.api.api_base_url = saved
    settings.api.api_keys.openai = 'saved-secret'
    async def load():
        return settings
    seen = {}
    async def catalog(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(catalog={}, as_dict=lambda: {})
    monkeypatch.setattr(api, 'load_settings', load)
    monkeypatch.setattr(model_catalog, 'list_available_models', catalog)
    asyncio.run(api.get_available_models(provider='openai', base_url=requested, api_key=explicit))
    assert seen['api_key'] == expected


def test_clip_update_keeps_server_locator():
    from backend.services.clip_service import ClipService
    service = object.__new__(ClipService)
    service.get = lambda _: SimpleNamespace(clip_metadata={"metadata_file": "server.json"})
    service.update = lambda _, **kwargs: kwargs
    updated = service.update_clip("clip1", ClipUpdate(clip_metadata={"custom": "new"}))
    assert updated["clip_metadata"] == {"metadata_file": "server.json", "custom": "new"}

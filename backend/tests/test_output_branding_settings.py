"""The application toggle controls new automatic renders and editor re-exports, and survives restart."""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.services import output_branding
from backend.services.studio import jobs, store
from backend.services.studio.models import Draft, Scene
from backend.tests.test_studio import client, root, source  # noqa: F401 - shared API fixtures


def test_settings_api_defaults_to_on_and_persists_off():
    from backend.api.v1.settings import router
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as api:
        assert api.get('/settings/output-branding').json() == {'enabled': True}
        assert api.put('/settings/output-branding', json={'enabled': False}).json() == {'enabled': False}
        assert api.get('/settings/output-branding').json() == {'enabled': False}
        assert api.put('/settings/output-branding', json={'enabled': 'true'}).status_code == 422
    assert output_branding.load_settings().enabled is False


@pytest.mark.parametrize('enabled', [True, False])
def test_automatic_render_obeys_the_saved_switch(root, monkeypatch, enabled):
    output_branding.save_settings(output_branding.BrandingSettings(enabled=enabled))
    submitted = []
    monkeypatch.setattr(jobs, 'render_executor', SimpleNamespace(submit=lambda *args, **kwargs: submitted.append((args, kwargs))))
    draft = Draft(id='d', title='x', scenes=[Scene(id='s', start=0, end=1)], subtitles=False)
    job = jobs.export('p1', draft, brand_outro=True)
    assert job['brand_outro'] is enabled
    assert submitted[0][1].get('brand_outro', False) is enabled


def test_a_different_outro_setting_cannot_reuse_the_other_active_render(root, monkeypatch):
    monkeypatch.setattr(jobs, 'render_executor', SimpleNamespace(submit=lambda *_args, **_kwargs: None))
    draft = Draft(id='d', title='x', scenes=[Scene(id='s', start=0, end=1)], subtitles=False)
    plain = jobs.export('p1', draft, brand_outro=False)
    branded = jobs.export('p1', draft, brand_outro=True)
    assert plain['job_id'] != branded['job_id']
    assert jobs.export('p1', draft, brand_outro=True)['job_id'] == branded['job_id']


@pytest.mark.parametrize('enabled', [True, False])
def test_editing_an_automatic_output_keeps_the_outro_and_respects_the_global_switch(client, monkeypatch, enabled):
    output_branding.save_settings(output_branding.BrandingSettings(enabled=enabled))
    draft = Draft(id='d', title='edited', revision=2, scenes=[Scene(id='s', start=0, end=1)], subtitles=False)
    store.write('p1', {'drafts': [draft.model_dump()], 'jobs': [], 'output_variants': [
        {'id': 'v', 'draft_id': 'd', 'branding': {'outro_enabled': True}, 'status': 'completed'}]})
    monkeypatch.setattr(jobs, 'render_executor', SimpleNamespace(submit=lambda *_args, **_kwargs: None))
    result = client.post('/studio/p1/drafts/d/export', json={'revision': 2})
    assert result.status_code == 200 and result.json()['brand_outro'] is enabled

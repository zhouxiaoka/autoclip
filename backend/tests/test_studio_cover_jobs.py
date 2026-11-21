"""Output-card AI covers use the platform's publish kit, with one task and honest outcomes."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from backend.services import cover
from backend.services.studio import jobs, publish_kit, store
from backend.tests.test_studio import client, root, source  # noqa: F401 - shared API fixtures


@pytest.fixture
def cover_state(monkeypatch, tmp_path):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    (tmp_path / 'privacy.json').write_text('{"crash_reports":false}')
    state = {'drafts': [], 'jobs': [], 'output_variants': [
        {'id': 'v', 'strategy_id': 'xiaohongshu', 'render_job_id': 'render', 'cover': 'design'}]}
    monkeypatch.setattr(store, 'read', lambda _: deepcopy(state))
    monkeypatch.setattr(store, 'change', lambda _, fn: fn(state))
    monkeypatch.setattr(cover, 'load_config', lambda: SimpleNamespace(enabled=True, configured=True, allow_send_frame=True))
    return state


def test_double_click_and_automatic_request_share_one_paid_task(cover_state, monkeypatch):
    submitted = []
    monkeypatch.setattr(jobs.cover_executor, 'submit', lambda *args, **kwargs: submitted.append(args))
    first = jobs.request_ai_cover('p', 'v')
    assert jobs.request_ai_cover('p', 'v') == first
    assert len(submitted) == 1 and first['status'] == 'queued'
    assert 'instance' not in first


@pytest.mark.parametrize('made', [True, False])
def test_the_task_uses_the_exact_platform_and_reports_failure_without_losing_the_cover(cover_state, monkeypatch, made):
    received = []
    monkeypatch.setattr(jobs.cover_executor, 'submit', lambda fn, *args, **kwargs: fn(*args, **kwargs))
    monkeypatch.setattr(publish_kit, 'ai_cover', lambda *args, **kwargs: received.append(args) or made)
    result = jobs.request_ai_cover('p', 'v')
    assert received == [('p', 'render', 'xiaohongshu')]
    assert result['status'] == ('completed' if made else 'failed')
    assert cover_state['output_variants'][0]['cover'] == ('ai' if made else 'design')


def test_dispatch_failure_preserves_the_video_and_allows_retry(cover_state, monkeypatch):
    def rejected(*_, **kwargs):
        raise RuntimeError('shutting down')
    monkeypatch.setattr(jobs.cover_executor, 'submit', rejected)
    result = jobs.request_ai_cover('p', 'v')
    assert result['status'] == 'failed' and cover_state['output_variants'][0]['cover'] == 'design'
    monkeypatch.setattr(jobs.cover_executor, 'submit', lambda *_, **kwargs: None)
    assert jobs.request_ai_cover('p', 'v')['job_id'] != result['job_id']


def test_no_model_task_when_image_generation_is_disabled(cover_state, monkeypatch):
    monkeypatch.setattr(cover, 'load_config', lambda: SimpleNamespace(enabled=False, configured=True, allow_send_frame=False))
    monkeypatch.setattr(jobs.cover_executor, 'submit', lambda *_: pytest.fail('must not submit'))
    assert jobs.request_ai_cover('p', 'v') is None
    assert 'cover_job' not in cover_state['output_variants'][0]


def test_interrupted_cover_is_failed_and_can_be_requested_again(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'directory', lambda _: tmp_path)
    state = {'jobs': [], 'output_variants': [{'id': 'v', 'status': 'completed', 'cover': 'design',
             'cover_job': {'job_id': 'old', 'status': 'running', 'instance': 'previous-server'}}]}
    store.write('p', state)
    store.recover('p')
    result = jobs.ai_cover_status('p', 'v')
    assert result['status'] == 'failed' and '重启' in result['error']
    assert store.read('p')['output_variants'][0]['status'] == 'completed'


def test_failed_atomic_cover_write_leaves_the_previous_cover_usable(tmp_path, monkeypatch):
    target = tmp_path / 'cover.jpg'
    target.write_bytes(b'previous-complete-image')
    def disk_error(*_):
        raise OSError('disk full')
    from backend.services import cover_brief
    monkeypatch.setattr(cover_brief.os, 'replace', disk_error)
    with pytest.raises(OSError):
        cover_brief.atomic(target, b'new-image')
    assert target.read_bytes() == b'previous-complete-image'
    assert list(tmp_path.iterdir()) == [target]


def _completed_output():
    return {'jobs': [{'job_id': 'render', 'status': 'completed'}], 'output_variants': [
        {'id': 'v', 'strategy_id': 'xiaohongshu', 'render_job_id': 'render', 'status': 'completed', 'cover': 'design'}]}


@pytest.mark.parametrize('allow_frame', [True, False])
def test_card_api_returns_and_polls_the_same_platform_cover_task(client, monkeypatch, allow_frame):
    store.write('p1', _completed_output())
    monkeypatch.setattr(cover, 'load_config', lambda: SimpleNamespace(enabled=True, configured=True, allow_send_frame=allow_frame))
    submitted = []
    monkeypatch.setattr(jobs.cover_executor, 'submit', lambda *args, **kwargs: submitted.append(args))
    started = client.post('/studio/p1/output-variants/v/cover/ai')
    if not allow_frame:
        assert started.status_code == 409 and not submitted
        return
    assert started.status_code == 200
    assert client.post('/studio/p1/output-variants/v/cover/ai').json() == started.json()
    assert client.get('/studio/p1/output-variants/v/cover/ai').json() == started.json()
    assert len(submitted) == 1


def test_card_api_rejects_ai_when_image_model_is_disabled(client, monkeypatch):
    store.write('p1', _completed_output())
    monkeypatch.setattr(cover, 'load_config', lambda: SimpleNamespace(enabled=False, configured=True, allow_send_frame=False))
    monkeypatch.setattr(jobs.cover_executor, 'submit', lambda *_: pytest.fail('must not submit'))
    assert client.post('/studio/p1/output-variants/v/cover/ai').status_code == 409


def test_redesign_returns_the_model_jpeg_verbatim_over_http(client, monkeypatch):
    import io
    import json
    from PIL import Image
    from backend.core import image_providers

    store.write('p1', _completed_output())
    config = cover.CoverConfig(enabled=True, model='test-image', api_key='fixture', allow_send_frame=True)
    monkeypatch.setattr(cover, 'load_config', lambda: config)
    monkeypatch.setattr(jobs.cover_executor, 'submit', lambda fn, *args, **kwargs: fn(*args, **kwargs))
    encoded = io.BytesIO()
    Image.new('RGB', (1080, 1440), 'navy').save(encoded, 'JPEG')
    reference = encoded.getvalue()
    args = ('p1', 'render', 'xiaohongshu')
    publish_kit.frame_path(*args).write_bytes(reference)
    publish_kit.cd_meta_path(*args).write_text(json.dumps({'lines': ['Headline'], 'accent': 0}))

    def image_model(*, request, **_):
        assert request.reference == reference
        assert request.model == 'test-image'
        return reference

    monkeypatch.setattr(image_providers, 'generate_image', image_model)
    monkeypatch.setattr(publish_kit, '_title_ok', lambda *_: True)
    url = '/studio/p1/output-variants/v/cover'
    job = client.post(url + '/regenerate',json={'title':'Headline','design':{'mode':'editorial_edit'}})
    assert job.status_code == 200 and job.json()['status'] == 'completed'
    assert client.get(url + '/ai').json()['job_id'] == job.json()['job_id']
    response = client.get(url)
    assert response.status_code == 200 and response.headers['content-type'] == 'image/jpeg'
    assert response.content == reference
    with Image.open(io.BytesIO(response.content)) as image:
        assert image.size == (1080, 1440)


@pytest.mark.parametrize(('automatic', 'model_fails'), [(True, False), (False, False), (True, True), (False, True)])
def test_default_export_and_regeneration_make_distinct_local_jpegs(client, root, source, monkeypatch, automatic, model_fails):
    import io
    import shutil
    from PIL import Image, ImageChops
    from backend.core import image_providers

    job_id = 'a' * 32
    title = 'A new beginning'
    draft = {'title': title, 'scenes': [{'start': 0, 'end': 2}]}
    job = {'job_id': job_id, 'draft_id': 'd1', 'revision': 1, 'title': title, 'status': 'completed', 'snapshot': draft,
           'result': {'duration': 3, 'width': 320, 'height': 180}}
    variant = {'id': 'v', 'strategy_id': 'xiaohongshu', 'render_job_id': job_id, 'status': 'completed'}
    store.write('p1', {'jobs': [job], 'output_variants': [variant] if automatic else []})
    output = root / 'output' / 'studio'
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, output / f'{job_id}.mp4')
    config = cover.CoverConfig(enabled=model_fails, api_key='fixture' if model_fails else '', model='fixture')
    monkeypatch.setattr(cover, 'load_config', lambda: config)
    def generate_image(**kwargs):
        pytest.fail('a default studio cover may never send an unreferenced image request')
    monkeypatch.setattr(image_providers, 'generate_image', generate_image)
    monkeypatch.setattr(jobs, 'source', lambda _: source)
    monkeypatch.setattr(jobs.cover_executor, 'submit', lambda fn, *args, **kwargs: fn(*args, **kwargs))
    jobs._design_covers('p1', draft, job_id)
    url = '/studio/p1/output-variants/v/cover'

    def image():
        content = (client.get(url).content if automatic else
                   cover.cover_path('p1', 'studio-' + job_id, 'bilibili').read_bytes())
        with Image.open(io.BytesIO(content)) as jpg:
            assert jpg.format == 'JPEG'
            return jpg.convert('RGB')

    previous = image()
    for _ in range(2):
        if automatic:
            response = client.post(url + '/regenerate',json={'title':title})
            assert response.status_code == 200, response.text
            assert response.json()['status'] == 'completed'
            assert store.read('p1')['output_variants'][0]['cover'] == 'design'
        else:
            cover.generate_cover(project_id='p1', clip_id='studio-' + job_id, platform='bilibili', title=title)
        current = image()
        assert previous.size == current.size
        assert ImageChops.difference(previous, current).getbbox(), 'regeneration repeated the same image'
        previous = current


def test_kit_http_download_cleans_up_the_archive(client, root, monkeypatch):
    from pathlib import Path
    store.write('p1', _completed_output())
    output = root / 'output' / 'studio'
    output.mkdir(parents=True)
    (output / 'render.mp4').write_bytes(b'complete-video')
    monkeypatch.setattr(publish_kit, 'cover_file', lambda *_: (None, None))
    created = []
    original = publish_kit.kit_file
    def capture(*args, **kwargs):
        result = original(*args, **kwargs)
        created.append(Path(result[0]))
        return result
    monkeypatch.setattr(publish_kit, 'kit_file', capture)
    response = client.get('/studio/p1/output-variants/v/kit')
    assert response.status_code == 200 and response.content.startswith(b'PK')
    assert len(created) == 1 and not created[0].exists()


def test_manual_export_has_editable_copy_and_its_own_matching_kit(client, root):
    import io
    import zipfile
    from backend.services.studio import publishing
    job_id = 'a' * 32
    job = {'job_id': job_id, 'status': 'completed', 'title': 'Original', 'snapshot': {'hook': 'From the draft'},
           'result': {'height': 1920, 'width': 1080}}
    store.write('p1', {'jobs': [job]})
    video = root / 'output' / 'studio' / f'{job_id}.mp4'
    video.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(b'versioned video')
    path = publishing.export_cover_file('p1', job)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'actual cover')
    public = client.get('/studio/p1').json()['jobs'][0]
    assert public['post']['description'] == 'From the draft'
    assert public['cover_revision'] == str(path.stat().st_mtime_ns)
    post = {'title': 'Edited', 'description': 'Ready to publish', 'tags': ['interview']}
    base = f'/studio/p1/jobs/{job_id}'
    assert client.put(base + '/post', json=post).json() == post
    assert client.get('/studio/p1').json()['jobs'][0]['post'] == post
    with zipfile.ZipFile(io.BytesIO(client.get(base + '/kit').content)) as archive:
        assert archive.read('Edited.mp4') == video.read_bytes()
        assert archive.read('Edited 封面.jpg') == path.read_bytes()
        assert '#interview' in archive.read('Edited 发布文案.txt').decode()

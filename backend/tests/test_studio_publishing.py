"""Completed Studio snapshots use the same publishers without rerendering or network."""
from pathlib import Path
from types import SimpleNamespace
import pytest
from backend.services.studio import store
from backend.services import publish_export as exp, cover as cover_svc

JID = 'a' * 32
CID = 'studio-' + JID

@pytest.fixture
def completed(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    root = store.directory('p1')
    output = root / 'output' / 'studio' / f'{JID}.mp4'
    output.parent.mkdir(parents=True)
    output.write_bytes(b'immutable packaged portrait and audio')
    store.write('p1', {'drafts': [{'id': 'd1', 'revision': 9, 'title': 'New unsent title'}], 'events': [], 'analysis': None,
        'jobs': [{'job_id': JID, 'draft_id': 'd1', 'title': 'Saved V2', 'revision': 2, 'status': 'completed',
                  'result': {'path': '/untrusted/result/path.mp4'}}]})
    monkeypatch.setattr(exp, '_probe', lambda path: {'duration': 26.7, 'width': 1080, 'height': 1920})
    monkeypatch.setattr(exp, 'find_source_video', lambda *_: pytest.fail('must not read original video'))
    return output

def test_export_keeps_exact_snapshot_and_file_without_rerender(completed):
    result = exp.export_clip(exp.ExportRequest('p1', CID, preset='bilibili', subtitles=True, title_card=True))
    assert result['path'] == str(completed)
    assert Path(result['path']).read_bytes() == b'immutable packaged portrait and audio'
    assert result['title'] == 'Saved V2' and result['revision'] == 2
    assert result['preset'] == 'studio' and result['width'] == 1080
    assert not (completed.parents[2] / 'metadata' / 'clips_metadata.json').exists()

@pytest.mark.parametrize('status', ['queued', 'running', 'failed'])
def test_rejects_unfinished_export(completed, status):
    store.change('p1', lambda data: data['jobs'][0].update(status=status))
    with pytest.raises(FileNotFoundError): exp.load_clip_meta('p1', CID)

def test_missing_empty_wrong_project_and_invalid_ids_are_rejected(completed):
    with pytest.raises(FileNotFoundError): exp.load_clip_meta('p2', CID)
    with pytest.raises(FileNotFoundError): exp.load_clip_meta('p1', 'studio-../../secret')
    completed.write_bytes(b'')
    with pytest.raises(FileNotFoundError): exp.load_clip_meta('p1', CID)
    completed.unlink()
    with pytest.raises(FileNotFoundError): exp.load_clip_meta('p1', CID)

def test_overlong_export_is_rejected_instead_of_silently_cut(completed, monkeypatch):
    monkeypatch.setattr(exp, '_probe', lambda _: {'duration': 100000, 'width': 1080, 'height': 1920})
    with pytest.raises(ValueError, match='限制'): exp.export_clip(exp.ExportRequest('p1', CID, preset='shorts'))

def test_cover_uses_packaged_frame_not_original_source(completed, monkeypatch):
    monkeypatch.setattr(cover_svc, 'find_source_video', lambda *_: pytest.fail('must use completed output'))
    path, at = cover_svc.resolve_clip_frame('p1', CID)
    assert path == completed and 0 < at < 26.7

def test_upload_post_submits_exact_export_and_records_revision(completed):
    from backend.services import upload_post_publisher as up
    calls = []
    class Session:
        def post(self, url, **kw):
            calls.append(kw['files']['video'][1].read())
            return SimpleNamespace(status_code=200, json=lambda: {'request_id': 'r1'})
    result = up.publish_clip(up.PublishRequest(project_id='p1', clip_id=CID, platforms=['youtube'], user='test'),
        config=up.UploadPostConfig(api_key='test', user='test'), session=Session())
    assert calls == [completed.read_bytes()]
    assert result['revision'] == 2 and result['preset'] == 'studio'
    record = up.list_records('p1')[0]
    assert record['studio_job_id'] == JID and record['title'] == 'Saved V2'

def test_bilibili_uses_exported_file_and_preserves_private_default(completed, monkeypatch):
    from backend.services import bilibili_publisher as bili
    monkeypatch.setattr(bili, 'load_config', lambda: SimpleNamespace(configured=True, cookie='test'))
    calls = []
    def upload(cookie, path, **kw):
        calls.append((path, kw['private']))
        return {'aid': 1, 'bvid': 'BVtest', 'url': 'https://example.test/video'}
    monkeypatch.setattr(bili, 'upload_video', upload)
    result = bili.publish_clip(bili.BilibiliPublishRequest(project_id='p1', clip_id=CID))
    assert calls == [(completed, True)]
    assert result['preset'] == 'studio' and result['revision'] == 2

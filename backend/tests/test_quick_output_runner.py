"""Headless imports use Studio, and status/ZIP observers preserve a live producer's state."""
import json
import zipfile
import pytest

from backend.services import quick_output_runner as quick
from backend.services.studio import jobs, store, publish_kit
from backend.tests.test_cli import data_dir, isolated_db  # noqa: F401


@pytest.fixture
def imported(data_dir, isolated_db, tmp_path, monkeypatch):
    import backend.utils.thumbnail_generator as thumbnail
    monkeypatch.setattr(thumbnail, 'generate_project_thumbnail', lambda *a, **kw: None)
    source = tmp_path / 'demo.mp4'
    source.write_bytes(b'local-video')
    srt = tmp_path / 'demo.srt'
    srt.write_text('1\n00:00:00,000 --> 00:00:02,000\nHello demo\n')
    calls = []
    def inspect(pid, options, url, browser, **kwargs):
        calls.append((pid, options, url, browser))
        store.write(pid, {'generation': {'status':'screening'}, 'jobs':[], 'drafts':[], 'output_variants':[]})
    monkeypatch.setattr(jobs, 'inspect_project', inspect)
    return source, srt, calls


def test_local_start_registers_project_and_enters_desktop_auto_pipeline(imported, isolated_db):
    from backend.models.project import Project
    source, srt, calls = imported
    pid = quick.start(str(source), ['shorts', 'reels', 'shorts'], srt_path=str(srt), instruction='A clear demo')
    _, options, url, browser = calls[0]
    assert options.auto_start and options.platforms == ['youtube_shorts', 'instagram_reels']
    assert options.instruction == 'A clear demo' and options.branding.outro_enabled
    assert url is None and browser is None
    assert (store.directory(pid) / 'raw' / 'input.mp4').read_bytes() == source.read_bytes()
    assert (store.directory(pid) / 'raw' / 'input.srt').read_bytes() == srt.read_bytes()
    with isolated_db() as db:
        row = db.query(Project).filter(Project.id == pid).one()
        assert row.video_path.endswith('/raw/input.mp4') and row.processing_config['smart_import']['auto_start']
    assert quick.status(pid)['status'] == 'running'


def test_url_start_keeps_provided_subtitles_for_the_desktop_downloader(imported):
    _, srt, calls = imported
    pid = quick.start('https://youtu.be/example', ['youtube_long'], srt_path=str(srt), browser='chrome')
    assert calls[0][2:] == ('https://youtu.be/example', 'chrome')
    assert (store.directory(pid) / 'raw' / 'input.srt').is_file()


@pytest.mark.parametrize('source,platforms', [('https://example.com/demo', ['douyin']),
                                             ('http://youtu.be/demo', ['douyin']),
                                             ('https://youtu.be/demo', ['bad-platform'])])
def test_invalid_import_never_creates_or_dispatches_a_project(imported, data_dir, source, platforms):
    with pytest.raises(ValueError): quick.start(source, platforms)
    assert not imported[2]
    assert not list((data_dir / 'projects').glob('*'))


def test_status_in_another_process_reports_live_jobs_without_restart_recovery(data_dir):
    root = store.directory('p1'); root.mkdir(parents=True)
    state = {'generation': {'status':'rendering'}, 'analysis': {'status':'running','instance':'producer'},
             'jobs': [{'job_id':'j1','status':'running','instance':'producer'}],
             'output_variants': [{'id':'v1','strategy_id':'youtube_long','status':'running','render_job_id':'j1'}]}
    store.write('p1', state)
    path = root / 'metadata' / 'studio.json'; before = path.read_bytes()
    assert quick.status('p1')['status'] == 'running'
    assert quick.status('p1')['outputs'][0]['status'] == 'running'
    assert path.read_bytes() == before
    assert store.read('p1')['jobs'][0]['status'] == 'failed'  # server recovery still works


def test_completed_status_exports_video_cover_and_copy_without_model_calls(data_dir, monkeypatch):
    root = store.directory('p1'); (root / 'output' / 'studio').mkdir(parents=True)
    video = root / 'output' / 'studio' / 'j1.mp4'; video.write_bytes(b'final-video')
    cover = publish_kit.kit_cover_path('p1', 'j1', 'youtube_long')
    cover.parent.mkdir(parents=True, exist_ok=True); cover.write_bytes(b'final-cover')
    state = {'generation': {'status':'completed'}, 'analysis':None,
             'jobs': [{'job_id':'j1','status':'completed','result':{'title':'Demo', 'outro_applied':True}}],
             'output_variants':[{'id':'v1','strategy_id':'youtube_long','status':'completed', 'render_job_id':'j1',
                                 'post':{'title':'Demo', 'description':'Test copy','tags':['AI']}}]}
    store.write('p1', state)
    monkeypatch.setattr(jobs, 'inspect_project', lambda *a: pytest.fail('Status dispatched production'))
    first = quick.status('p1', export_kits=True)
    row = first['outputs'][0]
    assert row['video_path'] == str(video) and row['cover_path'] == str(cover)
    assert row['post']['title'] == 'Demo' and row['result']['outro_applied']
    with zipfile.ZipFile(row['kit_path']) as archive:
        assert archive.read('Demo.mp4') == b'final-video'
        assert archive.read('Demo cover.jpg') == b'final-cover'
        assert 'Test copy' in archive.read('Demo post.txt').decode()
    assert quick.status('p1', export_kits=True)['outputs'][0]['kit_path'] == row['kit_path']
    state['output_variants'][0]['post']['description'] = 'Updated copy'; store.write('p1', state)
    assert quick.status('p1', export_kits=True)['outputs'][0]['kit_path'] != row['kit_path']


def test_cli_and_mcp_use_the_shared_quick_output_and_return_the_same_artifacts(imported, monkeypatch, capsys):
    from backend import cli, mcp_server
    source, srt, _ = imported
    result = {'project_id':'p1','status':'completed','outputs':[{'video_path':'/tmp/demo.mp4','kit_path':'/tmp/kit.zip'}]}
    calls=[]
    monkeypatch.setattr(quick, 'wait', lambda pid, **kw: calls.append(pid) or result.copy())
    args = cli.build_parser().parse_args(['produce',str(source),'--platform','youtube_long','--srt',str(srt),'--json'])
    assert cli.cmd_produce(args) == 0
    assert json.loads(capsys.readouterr().out)['outputs'] == result['outputs']
    started = mcp_server.start_quick_output(str(source), ['youtube_long'], srt_path=str(srt))
    assert started['ok'] and started['status'] == 'running'
    monkeypatch.setattr(quick, 'status', lambda pid, **kw: result.copy())
    assert mcp_server.get_quick_output_status(started['project_id'], export_kits=True)['outputs'] == result['outputs']


def test_wait_preserves_partial_outputs_and_reports_timeout_without_cancel(data_dir, monkeypatch):
    completed = {'status':'partial','outputs':[{'video_path':'/tmp/good.mp4'}]}
    monkeypatch.setattr(quick, 'status', lambda pid, **kw: completed.copy())
    assert quick.wait('p1')['outputs'] == completed['outputs']
    running = {'status':'running','outputs':[]}
    monkeypatch.setattr(quick, 'status', lambda pid, **kw: running.copy())
    assert quick.wait('p1', timeout=0)['timed_out']


def test_cli_progress_does_not_corrupt_json_stdout(monkeypatch, capsys):
    from backend import cli
    def start(*args, **kw):
        print('ASR progress')
        return 'p1'
    def wait(*args, **kw):
        print('Provider progress')
        return {'status':'completed','outputs':[]}
    monkeypatch.setattr(quick, 'start', start); monkeypatch.setattr(quick, 'wait', wait)
    args = cli.build_parser().parse_args(['produce','demo.mp4','--json'])
    assert cli.cmd_produce(args) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)['ok']
    assert 'ASR progress' in captured.err and 'Provider progress' in captured.err


def test_bad_status_id_returns_a_tool_error_instead_of_a_traceback(capsys):
    from backend import cli, mcp_server
    args = cli.build_parser().parse_args(['outputs','../other-project'])
    assert cli.cmd_outputs(args) == 2
    assert not json.loads(capsys.readouterr().out)['ok']
    assert not mcp_server.get_quick_output_status('../other-project')['ok']


def test_stopped_producer_is_reported_without_erasing_completed_outputs(data_dir, monkeypatch):
    import psutil
    root=store.directory('p1');root.mkdir(parents=True)
    state={'generation':{'status':'rendering','producer':{'pid':123,'created_at':1}},'jobs':[],
           'output_variants':[{'id':'v1','strategy_id':'douyin','status':'queued'}]}
    store.write('p1',state)
    monkeypatch.setattr(psutil,'Process',lambda pid:(_ for _ in ()).throw(psutil.NoSuchProcess(pid)))
    result=quick.status('p1')
    assert result['status']=='failed' and result['phase']=='interrupted'
    assert result['outputs'][0]['status']=='failed'
    assert store.read('p1',recover=False)['generation']['status']=='rendering'

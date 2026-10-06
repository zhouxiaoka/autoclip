"""CTC timing, complete text, route selection, dependency isolation and locking."""
import json
import os
from pathlib import Path, PureWindowsPath
import subprocess
import sys
from types import SimpleNamespace
import wave

import pytest

from backend.services.sensevoice_alignment import aligned_cues
from backend.services import sensevoice_runtime as runtime
from backend.services.ai_model_settings import ModelSettings, Transcription


def fixture(text='这是第一段。这里是第二段。最后一段用于验证音频末尾。'):
    words = list(text)
    return [{'text': '<|zh|><|NEUTRAL|>' + text, 'words': words,
             'timestamp': [[1050 + i * 800, 1550 + i * 800] for i in range(len(words))],
             'sentence_info': [{'sentence': text, 'start': 0, 'end': 30010}]}]


def test_ctc_avoids_coarse_vad_cues_and_preserves_all_text():
    raw = fixture()
    cues = aligned_cues(raw, 45100)
    assert len(cues) > 2
    assert ''.join(c['text'] for c in cues) == raw[0]['text'].split('>')[-1]
    assert cues[0]['start'] == 1.05
    assert cues[-1]['end'] == raw[0]['timestamp'][-1][1] / 1000
    from backend.utils.word_timing import valid_words
    assert all(valid_words(c) and c['end'] - c['start'] <= 8 for c in cues)


def test_spaces_numbers_and_punctuation_are_preserved():
    raw = [{'text': 'Hello, world. It was 19 years ago.',
            'words': ['Hello', ',', 'world', '.', 'It', 'was', '1', '9', 'years', 'ago', '.'],
            'timestamp': [[i * 500, i * 500 + 400] for i in range(11)]}]
    cues = aligned_cues(raw, 6000)
    assert [c['text'] for c in cues] == ['Hello, world.', 'It was 19 years ago.']
    assert ''.join(w['text'] for c in cues for w in c['words']) == raw[0]['text']


@pytest.mark.parametrize('broken', ['missing', 'partial', 'reverse', 'overlap', 'nan', 'beyond', 'text'])
def test_bad_alignment_never_fabricates_or_partially_writes(broken):
    raw = fixture()
    if broken == 'missing': raw[0].pop('timestamp')
    if broken == 'partial': raw[0]['words'].pop()
    if broken == 'reverse': raw[0]['timestamp'][0] = [2000, 1000]
    if broken == 'overlap': raw[0]['timestamp'][1] = [1100, 1600]
    if broken == 'nan': raw[0]['timestamp'][0][0] = float('nan')
    if broken == 'beyond': raw[0]['timestamp'][-1] = [46000, 47000]
    if broken == 'text': raw[0]['text'] += '丢失的正文'
    with pytest.raises(ValueError):
        aligned_cues(raw, 45100)


def test_multiple_vad_items_must_be_complete_and_monotonic():
    first = fixture('你好。')
    second = fixture('再见。')
    for time in second[0]['timestamp']:
        time[0] += 5000; time[1] += 5000
    cues = aligned_cues(first + second, 10000)
    assert [c['text'] for c in cues] == ['你好。', '再见。']
    with pytest.raises(ValueError): aligned_cues(second + first, 10000)


def test_local_selection_has_no_connection_and_validates_model(monkeypatch, tmp_path):
    selection = Transcription(provider='sensevoice_local', model='SenseVoiceSmall', connection_id='obsolete')
    assert selection.connection_id is None
    with pytest.raises(ValueError): Transcription(provider='sensevoice_local', model='base')
    from backend.services import ai_model_settings
    from backend.utils import speech_recognizer
    monkeypatch.setattr(ai_model_settings, 'load', lambda: ModelSettings(transcription=selection))
    calls = []
    def transcribe(*args):
        calls.append(args)
        return tmp_path / 'out.srt'
    monkeypatch.setattr(runtime, 'transcribe', transcribe)
    monkeypatch.setattr(speech_recognizer, 'SpeechRecognizer', lambda: pytest.fail('must not load Whisper'))
    assert speech_recognizer.generate_subtitle_for_video(tmp_path / 'video.mp4', model='tiny') == tmp_path / 'out.srt'
    assert calls[0][2:] == ('auto', 0)


def test_cross_process_lock_rejects_uninstall_and_releases(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, 'root', lambda: tmp_path / 'sensevoice')
    with runtime.operation():
        with pytest.raises(RuntimeError, match='正在准备或转写'): runtime.uninstall()
    assert runtime.uninstall()['status'] == 'not_installed'


def test_worker_uses_isolated_interpreter_not_parent_import_path(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, 'root', lambda: tmp_path)
    calls = []
    def run(cmd, **kw):
        calls.append(cmd)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(runtime.subprocess, 'run', run)
    runtime.worker('transcribe', tmp_path / 'r.json', tmp_path / 'a.wav')
    assert calls[0][:2] == [sys.executable, '-S']
    assert calls[0][2].endswith('sensevoice_worker.py')
    assert '-m' not in calls[0]


def test_interrupted_install_is_retryable_after_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, 'root', lambda: tmp_path / 'sensevoice')
    runtime._state('installing')
    assert runtime.status()['status'] == 'error'
    with runtime.operation():
        assert runtime.status()['status'] == 'installing'


def test_state_ignores_stale_readonly_temporary_file(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, 'root', lambda: tmp_path)
    stale = tmp_path / 'status.tmp'
    stale.write_text('interrupted writer')
    stale.chmod(0o444)
    try:
        runtime._state('ready')
        assert json.loads((tmp_path / 'status.json').read_text())['status'] == 'ready'
        assert stale.read_text() == 'interrupted writer'
    finally:
        stale.chmod(0o600)


def test_prepare_ignores_stale_readonly_ready_file(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, 'root', lambda: tmp_path)
    stale = tmp_path / 'ready.tmp'
    stale.write_text('interrupted model preparation')
    stale.chmod(0o444)
    monkeypatch.setattr(runtime.subprocess, 'run', lambda *_a, **_k: SimpleNamespace(returncode=0))
    def prepare_worker(action, result, **kwargs):
        assert action == 'prepare'
        package = tmp_path / 'runtime' / 'funasr'
        package.mkdir(parents=True)
        (package / '__init__.py').touch()
        paths = {}
        for name in ('model', 'vad_model'):
            folder = tmp_path / 'models' / name
            folder.mkdir(parents=True)
            (folder / 'model.pt').touch()
            paths[name] = str(folder)
        result.write_text(json.dumps({'paths': paths}))
    monkeypatch.setattr(runtime, 'worker', prepare_worker)
    try:
        runtime.prepare()
        assert runtime.status()['status'] == 'ready'
        assert stale.read_text() == 'interrupted model preparation'
        assert not list(tmp_path.glob('ready-*.tmp'))
    finally:
        stale.chmod(0o600)


def test_bundled_prepare_does_not_require_an_end_user_compiler(tmp_path, monkeypatch):
    resources = tmp_path / 'resources'
    service = resources / 'backend' / 'services'
    wheels = service / 'runtime_wheels'
    wheels.mkdir(parents=True)
    (wheels / 'editdistance-0.8.1-cp313-cp313-test.whl').touch()
    (resources / 'python').mkdir()
    monkeypatch.setattr(runtime, '__file__', str(service / 'sensevoice_runtime.py'))
    monkeypatch.setattr(runtime.sys, 'executable', str(resources / 'python' / 'python.exe'))
    monkeypatch.setattr(runtime, 'root', lambda: tmp_path / 'data')
    def compiler_unavailable(command, **kwargs):
        binary = command[command.index('--only-binary') + 1]
        uses_wheel = '--find-links' in command and command[command.index('--find-links') + 1] == str(wheels)
        return SimpleNamespace(returncode=0 if uses_wheel and 'editdistance' in binary.split(',') else 1)
    monkeypatch.setattr(runtime.subprocess, 'run', compiler_unavailable)
    def prepare_worker(action, result, **kwargs):
        package = runtime.root() / 'runtime' / 'funasr'
        package.mkdir(parents=True)
        (package / '__init__.py').touch()
        paths = {}
        for name in ('model', 'vad_model'):
            folder = runtime.root() / 'models' / name
            folder.mkdir(parents=True)
            (folder / 'model.pt').touch()
            paths[name] = str(folder)
        result.write_text(json.dumps({'paths': paths}))
    monkeypatch.setattr(runtime, 'worker', prepare_worker)
    runtime.prepare()
    assert runtime.status()['status'] == 'ready'


@pytest.mark.parametrize('extended', [False, True])
@pytest.mark.parametrize('layout', ['root', 'bin'])
def test_bundled_install_uses_wheel_with_native_executable_path(tmp_path, monkeypatch, extended, layout):
    resources = tmp_path / 'resources'
    service = resources / 'backend' / 'services'
    wheels = service / 'runtime_wheels'
    wheels.mkdir(parents=True)
    (wheels / 'editdistance-0.8.1-cp313-cp313-test.whl').touch()
    executable = resources / 'python' / ('bin/python.exe' if layout == 'bin' else 'python.exe')
    executable.parent.mkdir(parents=True)
    executable.touch()
    value = str(executable)
    if extended:
        if os.name == 'nt':
            value = '\\\\?\\' + str(executable.resolve())
        else:
            # Reproduce the namespace retained by the native Windows launcher;
            # Windows itself uses the real filesystem path in this regression.
            value = str(PureWindowsPath(r'\\?\C:\portable\python') /
                        ('bin/python.exe' if layout == 'bin' else 'python.exe'))
            resolved = SimpleNamespace(parents=executable.resolve().parents,
                                       is_relative_to=PureWindowsPath(value).is_relative_to)
            native_path = SimpleNamespace(parent=executable.parent,
                                          resolve=lambda: resolved)
            monkeypatch.setattr(runtime, 'Path', lambda path: native_path if path == value else Path(path))
    monkeypatch.setattr(runtime, '__file__', str(service / 'sensevoice_runtime.py'))
    monkeypatch.setattr(runtime.sys, 'executable', value)
    command = runtime._installation_command(tmp_path / 'data' / 'runtime')
    assert command[0] == value
    assert command[command.index('--find-links') + 1] == str(wheels)
    assert 'editdistance' in command[command.index('--only-binary') + 1].split(',')


@pytest.mark.parametrize('portable_directory_exists', [False, True])
def test_source_interpreter_does_not_require_packaged_wheel(tmp_path, monkeypatch, portable_directory_exists):
    resources = tmp_path / 'resources'
    service = resources / 'backend' / 'services'
    service.mkdir(parents=True)
    if portable_directory_exists:
        (resources / 'python').mkdir()
    executable = tmp_path / 'source-python' / 'python.exe'
    executable.parent.mkdir()
    executable.touch()
    monkeypatch.setattr(runtime, '__file__', str(service / 'sensevoice_runtime.py'))
    monkeypatch.setattr(runtime.sys, 'executable', str(executable))
    command = runtime._installation_command(tmp_path / 'data' / 'runtime')
    assert '--find-links' not in command
    assert 'editdistance' not in command[command.index('--only-binary') + 1].split(',')


def test_missing_bundled_wheel_does_not_compile_or_destroy_ready_data(tmp_path, monkeypatch):
    service = tmp_path / 'resources' / 'backend' / 'services'
    (tmp_path / 'resources' / 'python').mkdir(parents=True)
    monkeypatch.setattr(runtime, '__file__', str(service / 'sensevoice_runtime.py'))
    monkeypatch.setattr(runtime.sys, 'executable', str(tmp_path / 'resources' / 'python' / 'python.exe'))
    monkeypatch.setattr(runtime, 'root', lambda: tmp_path / 'data')
    runtime.root().mkdir()
    ready = runtime.root() / 'ready.json'
    ready.write_text('preserve previous model reference')
    monkeypatch.setattr(runtime.subprocess, 'run', lambda *_a, **_k: pytest.fail('must not invoke a compiler or pip'))
    with pytest.raises(RuntimeError, match='本地组件缺失'):
        runtime.prepare()
    assert ready.read_text() == 'preserve previous model reference'


def test_concurrent_state_updates_are_atomic(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    import time
    monkeypatch.setattr(runtime, 'root', lambda: tmp_path)
    barrier = threading.Barrier(2)
    replace = runtime.os.replace
    active = False
    guard = threading.Lock()
    def synchronized_replace(source, target):
        nonlocal active
        with guard:
            if active:
                raise PermissionError('Windows can reject concurrent replacements')
            active = True
        try:
            time.sleep(.05)
            replace(source, target)
        finally:
            with guard:
                active = False
    def update(state):
        barrier.wait(timeout=5)
        runtime._state(state)
    monkeypatch.setattr(runtime.os, 'replace', synchronized_replace)
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(update, ['installing', 'ready']))
    assert json.loads((tmp_path / 'status.json').read_text())['status'] in {'installing', 'ready'}
    assert not list(tmp_path.glob('*.tmp'))


@pytest.mark.parametrize('document', ['status', 'ready'])
def test_real_concurrent_status_readers_and_writers(tmp_path, monkeypatch, document):
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.setattr(runtime, 'root', lambda: tmp_path)
    def update(index):
        runtime._state('error' if index % 2 else 'ready')
        if document == 'ready':
            runtime._write_document('ready.json', {'version': runtime.VERSION, 'paths': {}})
        assert runtime.status()['status'] in {'error', 'not_installed'}
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(update, range(100)))
    assert json.loads((tmp_path / 'status.json').read_text())['status'] in {'ready', 'error'}
    assert not list(tmp_path.glob('*.tmp'))


@pytest.mark.parametrize('value', [{}, [], None, {'status': 'unknown'}])
def test_malformed_status_is_recoverable(tmp_path, monkeypatch, value):
    monkeypatch.setattr(runtime, 'root', lambda: tmp_path)
    (tmp_path / 'status.json').write_text(json.dumps(value))
    assert runtime.status()['status'] == 'not_installed'


@pytest.mark.parametrize('paths', [[], None, 'invalid'])
def test_malformed_ready_paths_do_not_break_status(tmp_path, monkeypatch, paths):
    monkeypatch.setattr(runtime, 'root', lambda: tmp_path)
    (tmp_path / 'runtime' / 'funasr').mkdir(parents=True)
    (tmp_path / 'runtime' / 'funasr' / '__init__.py').touch()
    (tmp_path / 'ready.json').write_text(json.dumps({'version': runtime.VERSION, 'paths': paths}))
    assert runtime.status()['status'] == 'not_installed'


def test_status_api_is_lightweight_and_install_conflict_is_explicit(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.v1.speech_recognition import router
    monkeypatch.setattr(runtime, 'root', lambda: tmp_path / 'sensevoice')
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        assert client.get('/sensevoice/status').json()['status'] == 'not_installed'
        with runtime.operation():
            assert client.post('/sensevoice/prepare').status_code == 409
            assert client.delete('/sensevoice').status_code == 409


def test_transcribe_srt_and_real_word_sidecar_without_optional_imports(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, 'root', lambda: tmp_path / 'runtime')
    monkeypatch.setattr(runtime, 'status', lambda: {'status': 'ready'})
    raw = fixture()
    def extract(cmd, **kw):
        with wave.open(cmd[-1], 'wb') as target:
            target.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            target.writeframes(b'\0\0' * (16000 * 45))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(runtime.subprocess, 'run', extract)
    def worker(action, result, *args): result.write_text(json.dumps(raw), encoding='utf-8')
    monkeypatch.setattr(runtime, 'worker', worker)
    output = tmp_path / '字幕.srt'
    runtime.transcribe(tmp_path / '源.mp4', output)
    from backend.utils.word_timing import load_word_timing
    assert load_word_timing(output)
    before = output.read_bytes()
    raw[0]['words'].pop()
    from backend.utils.speech_recognizer import SpeechRecognitionError
    with pytest.raises(SpeechRecognitionError): runtime.transcribe(tmp_path / '源.mp4', output)
    assert output.read_bytes() == before
    output.write_text('edited', encoding='utf-8')
    assert load_word_timing(output) is None


def test_sensevoice_error_does_not_point_to_whisper(monkeypatch):
    from backend.pipeline.failures import failure_from_speech_error
    from backend.services import whisper_runtime
    monkeypatch.setattr(whisper_runtime, 'get_status', lambda: pytest.fail('unrelated Whisper probe'))
    failure = failure_from_speech_error('SenseVoice 词与时间戳未完整配对')
    assert failure.code == 'subtitle_setup' and 'SenseVoice' in failure.hint
    assert 'Whisper' not in failure.user_message()


@pytest.mark.parametrize("stage", ["pip", "worker"])
def test_timeout_keeps_bounded_local_dependency_log_and_releases_state(tmp_path, monkeypatch, caplog, stage):
    monkeypatch.setattr(runtime, "root", lambda: tmp_path / "sensevoice")
    marker = "LAST_DEPENDENCY_PHASE_FOR_TIMEOUT_DIAGNOSIS"
    child = [sys.executable, "-c", "import sys,time;print('DISCARDED_PREFIX'+'x'*16000+'" + marker + "',flush=True);time.sleep(60)"]
    real_run = subprocess.run
    calls = []
    def bounded_child(command, **kwargs):
        calls.append(command)
        kwargs["timeout"] = 3  # Allow interpreter startup on cold Windows CI.
        return real_run(child, **kwargs)
    monkeypatch.setattr(runtime.subprocess, "run", bounded_child)
    caplog.set_level("ERROR", logger=runtime.__name__)
    expected = RuntimeError if stage == "pip" else subprocess.TimeoutExpired
    with pytest.raises(expected):
        if stage == "pip": runtime.prepare()
        else: runtime.worker("prepare", tmp_path / "result.json", timeout=1800)
    assert len(calls) == 1
    assert marker in caplog.text
    assert "DISCARDED_PREFIX" not in caplog.text
    assert len(caplog.text) < 12500
    assert not (runtime.root() / "ready.json").exists()
    if stage == "pip":
        state = json.loads((runtime.root() / "status.json").read_text(encoding="utf-8"))
        assert state["status"] == "error"
        assert "组件安装失败" in state["message"]
    with runtime.operation():
        pass


def test_optional_speech_runtime_rejects_incompatible_transformers_major():
    from packaging.requirements import Requirement
    requirements = {Requirement(value).name.replace("_", "-"): Requirement(value) for value in runtime.packages()}
    assert "transformers" in requirements, "Unbounded transitive dependency explores incompatible major releases"
    assert requirements["transformers"].specifier.contains("4.57.6")
    assert not requirements["transformers"].specifier.contains("5.16.0")
    assert requirements["huggingface-hub"].specifier.contains("0.36.2")
    assert not requirements["huggingface-hub"].specifier.contains("1.5.0")


@pytest.mark.parametrize("raises", [False, True])
def test_windows_worker_keeps_bundled_openmp_directory_for_entire_inference(tmp_path, monkeypatch, raises):
    from backend.services import sensevoice_worker as worker
    optional = tmp_path / "runtime"
    dll_dir = optional / "sklearn" / ".libs"
    dll_dir.mkdir(parents=True)
    (dll_dir / "vcomp140.dll").touch()
    handles = []
    class Handle:
        def __init__(self, directory):
            self.directory, self.closed = directory, False
        def __enter__(self): return self
        def __exit__(self, *_): self.closed = True
    def add(directory):
        handle = Handle(directory)
        handles.append(handle)
        return handle
    monkeypatch.setattr(worker, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(worker.os, "add_dll_directory", add, raising=False)
    class InferenceFailure(Exception): pass
    try:
        with worker.native_library_context(optional):
            assert len(handles) == 1
            assert Path(handles[0].directory) == dll_dir.resolve()
            assert not handles[0].closed
            if raises: raise InferenceFailure()
    except InferenceFailure:
        assert raises
    assert handles[0].closed


def test_windows_native_directory_does_not_search_outside_optional_runtime(tmp_path, monkeypatch):
    from backend.services import sensevoice_worker as worker
    optional = tmp_path / "runtime"
    (optional / "sklearn").mkdir(parents=True)
    external = tmp_path / "external"
    external.mkdir()
    (external / "vcomp140.dll").touch()
    (optional / "sklearn" / ".libs").symlink_to(external, target_is_directory=True)
    monkeypatch.setattr(worker, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(worker.os, "add_dll_directory", lambda *_: pytest.fail("external DLL path"), raising=False)
    with worker.native_library_context(optional): pass


def test_non_windows_worker_does_not_change_native_search_paths(tmp_path, monkeypatch):
    from backend.services import sensevoice_worker as worker
    monkeypatch.setattr(worker, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(worker.os, "add_dll_directory", lambda *_: pytest.fail("non-Windows native path"), raising=False)
    with worker.native_library_context(tmp_path / "not-installed"): pass


def test_model_worker_enables_native_crash_trace_in_real_child(monkeypatch, tmp_path):
    monkeypatch.delenv("PYTHONFAULTHANDLER", raising=False)
    real_run = subprocess.run
    def check_runtime_flag(command, **kwargs):
        return real_run([sys.executable, "-S", "-c", "import faulthandler;raise SystemExit(0 if faulthandler.is_enabled() else 43)"], **kwargs)
    monkeypatch.setattr(runtime.subprocess, "run", check_runtime_flag)
    runtime.worker("prepare", tmp_path / "result.json", timeout=5)


def test_worker_silent_crash_records_exit_code_locally(monkeypatch, tmp_path, caplog):
    def failed(command, **kwargs):
        return SimpleNamespace(returncode=3221225477)
    monkeypatch.setattr(runtime.subprocess, "run", failed)
    caplog.set_level("ERROR", logger=runtime.__name__)
    with pytest.raises(RuntimeError, match="SenseVoice"):
        runtime.worker("prepare", tmp_path / "result.json", timeout=5)
    assert "exit=3221225477" in caplog.text

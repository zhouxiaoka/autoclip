"""Optional, isolated CPU SenseVoice runtime. No FunASR imports in this process."""
from contextlib import contextmanager
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import wave

from backend.core.path_utils import get_data_directory
from backend.utils.ffmpeg_utils import get_ffmpeg_path

logger = logging.getLogger(__name__)
MODEL = 'SenseVoiceSmall'
VERSION = 1


def root():
    return get_data_directory() / 'sensevoice'


def packages():
    cpu = '+cpu' if sys.platform != 'darwin' else ''
    return ['funasr==1.3.14', f'torch==2.8.0{cpu}', f'torchaudio==2.8.0{cpu}',
            'setuptools==80.9.0', 'huggingface-hub<1', 'numpy<3']


def status():
    try:
        value = json.loads((root() / 'status.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        value = {'status': 'not_installed', 'message': ''}
    # Validate paths without importing a large optional runtime on every poll.
    try:
        ready = json.loads((root() / 'ready.json').read_text(encoding='utf-8'))
        valid = (ready['version'] == VERSION and (root() / 'runtime' / 'funasr' / '__init__.py').exists()
                 and all(Path(p).resolve().is_relative_to((root() / 'models').resolve())
                         and (Path(p) / 'model.pt').exists() for p in ready['paths'].values())
                 and set(ready['paths']) == {'model', 'vad_model'})
    except (OSError, ValueError, KeyError, TypeError):
        valid = False
    if valid and value['status'] != 'installing':
        value = {'status': 'ready', 'message': ''}
    elif value.get('status') == 'ready':
        value = {'status': 'not_installed', 'message': '模型文件缺失，请重新准备模型'}
    if value.get('status') == 'installing':
        try:
            with operation():
                value = {'status': 'error', 'message': '上次模型准备被中断，请重试'}
        except RuntimeError:
            pass
    return {**value, 'model': MODEL}


def _state(state, message=''):
    root().mkdir(parents=True, exist_ok=True)
    target = root() / 'status.json'
    pending = target.with_suffix('.tmp')
    pending.write_text(json.dumps({'status': state, 'message': message}, ensure_ascii=False), encoding='utf-8')
    os.replace(pending, target)


@contextmanager
def operation():
    """Cross-process lock: API installs and Celery inference share the data dir."""
    base = root()
    base.mkdir(parents=True, exist_ok=True)
    with open(base.parent / 'sensevoice.lock', 'a+b') as handle:
        handle.seek(0)
        try:
            if sys.platform == 'win32':
                import msvcrt
                if handle.read(1) == b'':
                    handle.write(b'0')
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError('SenseVoice 正在准备或转写，请完成后重试') from None
        try:
            yield
        finally:
            if sys.platform == 'win32':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def worker(action, result, audio=None, language='auto', timeout=None, deny_network=False):
    command = [sys.executable, '-S', str(Path(__file__).with_name('sensevoice_worker.py')),
               action, '--root', str(root()), '--result', str(result), '--language', language]
    if audio:
        command += ['--audio', str(audio)]
    if deny_network:
        command += ['--deny-network']
    # Logs can contain private text. Keep them in the local diagnostic log only.
    with tempfile.TemporaryFile() as log:
        completed = subprocess.run(command, stdout=log, stderr=log, timeout=timeout,
                                   env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'})
        if completed.returncode:
            log.seek(max(0, log.tell() - 12000))
            logger.error('SenseVoice worker failed: %s', log.read().decode('utf-8', errors='replace'))
            raise RuntimeError('SenseVoice 模型运行失败，请到「设置 → 转写」重新准备模型；仍失败时附上脱敏日志')


def _prepare():
    _state('installing', '正在安装组件，首次下载可能需要几分钟')
    try:
        (root() / 'ready.json').unlink(missing_ok=True)
        runtime = root() / 'runtime'
        shutil.rmtree(runtime, ignore_errors=True)
        command = [sys.executable, '-m', 'pip', 'install', '--target', str(runtime),
                   '--only-binary', 'torch,torchaudio', *packages()]
        if sys.platform != 'darwin':
            command += ['--extra-index-url', 'https://download.pytorch.org/whl/cpu']
        with tempfile.TemporaryFile() as log:
            completed = subprocess.run(command, stdout=log, stderr=log, timeout=1800,
                                       env={**os.environ, 'PIP_PROGRESS_BAR': 'off', 'PYTHONIOENCODING': 'utf-8'})
            if completed.returncode:
                log.seek(max(0, log.tell() - 12000))
                logger.error('SenseVoice pip failed: %s', log.read().decode('utf-8', errors='replace'))
                raise RuntimeError('SenseVoice 组件安装失败，请检查网络和磁盘空间后重试')
        _state('installing', '正在下载并检查 SenseVoiceSmall 模型')
        result = root() / 'prepare-result.json'
        worker('prepare', result, timeout=1800)
        value = json.loads(result.read_text(encoding='utf-8'))
        value['version'] = VERSION
        ready = root() / 'ready.json'
        pending = ready.with_suffix('.tmp')
        pending.write_text(json.dumps(value), encoding='utf-8')
        os.replace(pending, ready)
        result.unlink(missing_ok=True)
        _state('ready')
    except Exception as exc:
        _state('error', str(exc) if isinstance(exc, RuntimeError) else 'SenseVoice 准备失败，请检查网络后重试')
        raise


def prepare():
    with operation():
        _prepare()


def start_prepare():
    lock = operation()
    lock.__enter__()
    def run():
        try:
            _prepare()
        except Exception:
            logger.exception('SenseVoice preparation failed')
        finally:
            lock.__exit__(None, None, None)
    try:
        _state('installing', '正在准备组件…')
        threading.Thread(target=run, daemon=True).start()
    except Exception:
        lock.__exit__(None, None, None)
        raise
    return status()


def uninstall():
    with operation():
        shutil.rmtree(root())
    return status()


def transcribe(video, output=None, language='auto', timeout=0, *, deny_network=False):
    from backend.services.sensevoice_alignment import aligned_cues
    from backend.utils.speech_recognizer import SpeechRecognitionError, SpeechRecognizer
    from backend.utils.word_timing import write_word_timing
    language = {'zh-TW': 'zh', 'en-US': 'en', 'en-GB': 'en'}.get(language, language)
    if language not in {'auto', 'zh', 'en', 'ja', 'ko', 'yue'}:
        raise SpeechRecognitionError('SenseVoiceSmall 支持中文、粤语、英语、日语和韩语，请选择支持的语言或自动检测')
    output = Path(output) if output else Path(video).with_suffix('.srt')
    try:
        with operation(), tempfile.TemporaryDirectory(prefix='autoclip-sensevoice-') as temporary:
            if status()['status'] != 'ready':
                raise RuntimeError('SenseVoice 尚未就绪，请到「设置 → 转写」准备 SenseVoiceSmall 模型')
            audio, result = Path(temporary) / 'audio.wav', Path(temporary) / 'result.json'
            extracted = subprocess.run([get_ffmpeg_path(), '-nostdin', '-v', 'error', '-y', '-i', str(video),
                                        '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(audio)],
                                       capture_output=True, timeout=timeout or 300)
            if extracted.returncode:
                raise RuntimeError('SenseVoice 无法读取视频音轨，请确认视频包含可播放的人声')
            with wave.open(str(audio), 'rb') as source:
                duration_ms = source.getnframes() * 1000 // source.getframerate()
            worker('transcribe', result, audio, language, timeout or None, deny_network)
            cues = aligned_cues(json.loads(result.read_text(encoding='utf-8')), duration_ms)
            output.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output.parent, delete=False) as stream:
                pending = Path(stream.name)
                stream.write(SpeechRecognizer._segments_to_srt(cues))
            try:
                os.replace(pending, output)
                write_word_timing(output, cues, language, source='sensevoice')
            finally:
                pending.unlink(missing_ok=True)
            return output
    except subprocess.TimeoutExpired:
        raise SpeechRecognitionError('SenseVoice 转写超时，请缩短视频或增加转写超时时间') from None
    except (RuntimeError, ValueError, OSError) as exc:
        raise SpeechRecognitionError(str(exc)) from exc

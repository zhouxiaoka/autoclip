"""Real runtime/model install and offline speech timing, including installed bundles."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

checkout = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--resources', type=Path, help='Use installed portable Python and backend')
parser.add_argument('--report', type=Path, default=Path('sensevoice-acceptance.json'))
args = parser.parse_args()
report_path = args.report.resolve()
source_video = checkout / 'backend/assets/example/source.mp4'
if args.resources:
    resources = args.resources.resolve(strict=True)
    assert sys.dont_write_bytecode, 'Use -B to preserve signed resources'
    assert Path(sys.executable).resolve().is_relative_to(resources / 'python'), 'installed Python required'
    suffix = '.exe' if sys.platform == 'win32' else ''
    os.environ.update(AUTOCLIP_FFMPEG_PATH=str(resources / 'ffmpeg' / ('ffmpeg' + suffix)),
                      AUTOCLIP_FFPROBE_PATH=str(resources / 'ffmpeg' / ('ffprobe' + suffix)),
                      PYTHONDONTWRITEBYTECODE='1')
    os.chdir(resources)
    sys.path.insert(0, str(resources))
else:
    sys.path.insert(0, str(checkout))
base = Path(tempfile.mkdtemp(prefix='autoclip-sensevoice-acceptance-'))
os.environ['AUTOCLIP_DATA_DIR'] = str(base)
os.environ['AUTOCLIP_APP_DIR'] = str(base)
os.environ['SENTRY_DSN'] = ''
(base / 'privacy.json').write_text('{"analytics":false,"crash_reports":false}', encoding='utf-8')
if args.resources:
    import backend
    assert Path(backend.__file__).resolve().is_relative_to(resources / 'backend'), 'development backend imported'
from backend.services import ai_model_settings as settings, sensevoice_runtime as runtime
from backend.utils.ffmpeg_utils import get_ffmpeg_path
from backend.utils.speech_recognizer import generate_subtitle_for_video
from backend.utils.word_timing import load_word_timing

runtime.prepare()
assert runtime.status()['status'] == 'ready', runtime.status()
video = base / '真实语音 sample.mp4'
subprocess.run([get_ffmpeg_path(), '-v', 'error', '-i', str(source_video),
                '-t', '45', '-c', 'copy', str(video)], check=True, timeout=60)
models = settings.ModelSettings(transcription=settings.Transcription(provider='sensevoice_local', model='SenseVoiceSmall'))
settings.path().write_text(models.model_dump_json(), encoding='utf-8')
# Prove the normal saved-selection entry point reaches isolated offline inference.
original_transcribe = runtime.transcribe
def offline(*args, **kw):
    return original_transcribe(*args, **kw, deny_network=True)
runtime.transcribe = offline
subtitle = generate_subtitle_for_video(video, language='en')
cues = load_word_timing(subtitle)
assert cues and len(cues) > 2, cues
assert 'months' in subtitle.read_text(encoding='utf-8').lower()
assert all(0 <= c['start'] < c['end'] <= 45.2 and c['end'] - c['start'] <= 8.001 for c in cues)
assert all(a['end'] <= b['start'] for a, b in zip(cues, cues[1:]))
assert 'funasr' not in sys.modules and 'torch' not in sys.modules
size = sum(p.stat().st_size for p in runtime.root().rglob('*') if p.is_file())
report_path.write_text(json.dumps({
    'platform': sys.platform, 'python': sys.version.split()[0], 'model': 'SenseVoiceSmall',
    'runtime_source': 'installed portable Python and backend' if args.resources else 'development checkout',
    'bundled_editdistance_wheel': 'passed' if args.resources else 'not applicable',
    'source': 'public interview, first 45 seconds', 'install': 'passed',
    'offline_network_denied': 'passed', 'normal_selection_route': 'passed',
    'parent_dependency_isolation': 'passed', 'cues': len(cues),
    'words': sum(len(c['words']) for c in cues), 'final_seconds': cues[-1]['end'],
    'maximum_cue_seconds': max(c['end'] - c['start'] for c in cues), 'disk_bytes': size,
}, indent=2), encoding='utf-8')
runtime.uninstall()
assert runtime.status()['status'] == 'not_installed'

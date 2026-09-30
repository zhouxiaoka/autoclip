"""Acceptance: actual pip runtime install, model download and offline real ASR."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

checkout = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--resources', type=Path, help='Use installed portable Python and backend, not the checkout')
parser.add_argument('--report', type=Path, default=Path('issue-recovery-report.json'))
args = parser.parse_args()
report_path = args.report.resolve()
source_video = checkout / 'backend/assets/example/source.mp4'
if args.resources:
    resources = args.resources.resolve(strict=True)
    assert Path(sys.executable).resolve().is_relative_to(resources / 'python'), 'installed Python required'
    os.chdir(resources)
    sys.path.insert(0, str(resources))
    os.environ.update(AUTOCLIP_FFMPEG_PATH=str(resources / 'ffmpeg/ffmpeg.exe'),
                      AUTOCLIP_FFPROBE_PATH=str(resources / 'ffmpeg/ffprobe.exe'))
else:
    sys.path.insert(0, str(checkout))
root = Path(tempfile.mkdtemp(prefix="autoclip-whisper-acceptance-"))
os.environ.update(AUTOCLIP_DATA_DIR=str(root), AUTOCLIP_APP_DIR=str(root),
                  HF_HUB_DISABLE_PROGRESS_BARS="1", AUTOCLIP_WHISPER_DEVICE="cpu")
from backend.services import whisper_runtime
from backend.services.whisper_model_manager import get_model_manager, ModelStatus
from backend.utils.speech_recognizer import SpeechRecognizer, SpeechRecognitionConfig
from backend.utils.ffmpeg_utils import get_ffmpeg_path
if args.resources:
    import backend
    assert Path(backend.__file__).resolve().is_relative_to(resources / 'backend'), 'development backend imported'

whisper_runtime._do_install("https://pypi.org/simple")
assert whisper_runtime.get_status()["status"] == "installed", whisper_runtime.get_status()
manager = get_model_manager()
manager._download_blocking("tiny")
assert manager.get_model_info("tiny").status == ModelStatus.DOWNLOADED
video = root / "真实语音 sample.mp4"
subprocess.run([get_ffmpeg_path(), "-v", "error", "-i", str(source_video),
                "-t", "12", "-c", "copy", str(video)], check=True, timeout=60)
# Prove the inference path does not call the Hub once its model is ready.
import huggingface_hub
def no_network(*args, **kwargs):
    raise AssertionError("cached inference must not access HuggingFace")
huggingface_hub.snapshot_download = no_network
os.environ["HF_HUB_OFFLINE"] = "1"
subtitle = root / "output.srt"
recognizer = SpeechRecognizer.__new__(SpeechRecognizer)
recognizer._generate_subtitle_whisper_local(video, subtitle, SpeechRecognitionConfig(model="tiny"))
body = subtitle.read_text(encoding="utf-8")
assert "-->" in body and "months" in body.lower(), body
# Also reproduce an already-installed incompatible PyAV in a fresh interpreter.
# Keep the incompatible version separate: Windows locks loaded .pyd files.
av19_dir = root / 'av19-runtime'
subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', '--target',
                str(av19_dir), 'av==19.0.0'], check=True, timeout=180)
subprocess.run([sys.executable, '-c', '''
import os, sys
from pathlib import Path
from backend.services import whisper_runtime
whisper_runtime.ensure_on_path()
sys.path.insert(0, str(Path(os.environ['AUTOCLIP_DATA_DIR']) / 'av19-runtime'))
import av, huggingface_hub
assert av.__version__ == '19.0.0', av.__version__
def offline(*args, **kwargs): raise AssertionError('unexpected Hub access')
huggingface_hub.snapshot_download = offline
from backend.utils.speech_recognizer import SpeechRecognizer, SpeechRecognitionConfig
root = Path(os.environ['AUTOCLIP_DATA_DIR'])
output = root / 'av19.srt'
SpeechRecognizer.__new__(SpeechRecognizer)._generate_subtitle_whisper_local(
    root / '真实语音 sample.mp4', output, SpeechRecognitionConfig(model='tiny'))
assert 'months' in output.read_text(encoding='utf-8').lower()
'''], check=True, timeout=180)
report_path.write_text(json.dumps({
    "platform": sys.platform, "python": sys.version.split()[0],
    "runtime_source": "installed portable Python and installed backend" if args.resources else "development checkout",
    "runtime_install": "passed", "model_download": "passed",
    "offline_real_transcription": "passed", "pyav19_recovery": "passed", "subtitle_cues": body.count("-->"),
}, indent=2), encoding="utf-8")
print("Runtime install, model download, offline speech transcription passed")

"""Acceptance: actual pip runtime install, model download and offline real ASR."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
root = Path(tempfile.mkdtemp(prefix="autoclip-whisper-acceptance-"))
os.environ.update(AUTOCLIP_DATA_DIR=str(root), AUTOCLIP_APP_DIR=str(root),
                  HF_HUB_DISABLE_PROGRESS_BARS="1", AUTOCLIP_WHISPER_DEVICE="cpu")
from backend.services import whisper_runtime
from backend.services.whisper_model_manager import get_model_manager, ModelStatus
from backend.utils.speech_recognizer import SpeechRecognizer, SpeechRecognitionConfig
from backend.utils.ffmpeg_utils import get_ffmpeg_path

whisper_runtime._do_install("https://pypi.org/simple")
assert whisper_runtime.get_status()["status"] == "installed", whisper_runtime.get_status()
manager = get_model_manager()
manager._download_blocking("tiny")
assert manager.get_model_info("tiny").status == ModelStatus.DOWNLOADED
video = root / "真实语音 sample.mp4"
subprocess.run([get_ffmpeg_path(), "-v", "error", "-i", "backend/assets/example/source.mp4",
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
# Imported native modules cannot safely be replaced inside the current process.
subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', '--target',
                str(whisper_runtime.get_install_dir()), 'av==19.0.0'], check=True, timeout=180)
subprocess.run([sys.executable, '-c', '''
import os
from pathlib import Path
from backend.services import whisper_runtime
whisper_runtime.ensure_on_path()
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
Path("issue-recovery-report.json").write_text(json.dumps({
    "platform": sys.platform, "python": sys.version.split()[0],
    "runtime_install": "passed", "model_download": "passed",
    "offline_real_transcription": "passed", "pyav19_recovery": "passed", "subtitle_cues": body.count("-->"),
}, indent=2), encoding="utf-8")
print("Runtime install, model download, offline speech transcription passed")

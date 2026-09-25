"""本地 Whisper 转写失败要留在进程里，并变成客户端能读的错误。

PYTHON-FASTAPI-5：faster-whisper 1.2.1 在 detect_language → encode，
以及 vad_filter 的 onnxruntime，把 RuntimeError / Fail 抛回
``_generate_subtitle_whisper_local``。
"""
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.services import whisper_runtime
from backend.utils.speech_recognizer import (
    SpeechRecognitionConfig,
    SpeechRecognitionError,
    SpeechRecognizer,
    describe_whisper_failure,
    generate_subtitle_for_video,
    resolve_local_whisper_backend,
    vad_backend_failed,
)


class Fail(Exception):
    """与 onnxruntime 的异常类名一致。"""


def test_default_backend_is_cpu_int8(monkeypatch):
    monkeypatch.delenv("AUTOCLIP_WHISPER_DEVICE", raising=False)
    assert resolve_local_whisper_backend() == ("cpu", "int8")


def test_cuda_opt_in_does_not_force_int8(monkeypatch):
    monkeypatch.setenv("AUTOCLIP_WHISPER_DEVICE", "cuda")
    assert resolve_local_whisper_backend() == ("cuda", "float16")
    assert resolve_local_whisper_backend("auto") == ("auto", "default")
    assert resolve_local_whisper_backend("CUDA") == ("cuda", "float16")


def test_vad_failure_is_classified_without_treating_encode_as_vad():
    assert vad_backend_failed(Fail("session.run"))
    encode = RuntimeError("cuBLAS failed with status CUBLAS_STATUS_NOT_SUPPORTED")
    assert vad_backend_failed(encode) is False

    code = compile("def boom():\n    raise RuntimeError('vad')\n", "faster_whisper/vad.py", "exec")
    ns: dict = {}
    exec(code, ns)
    with pytest.raises(RuntimeError) as exc:
        ns["boom"]()
    assert vad_backend_failed(exc.value)


def test_install_error_is_not_reported_as_not_installed(monkeypatch):
    """设置页靠 status=error 显示「重试安装」。轮询不能把它盖成 not_installed。"""
    monkeypatch.setattr(whisper_runtime, "is_installed", lambda: False)
    whisper_runtime._set_state(status="error", progress=12, message="安装失败（pip 退出码 1）", log_tail="boom")
    try:
        status = whisper_runtime.get_status()
        assert status["status"] == "error"
        assert "退出码" in status["message"]
    finally:
        whisper_runtime._set_state(status="unknown", progress=0, message="", log_tail="")


def test_installed_runtime_still_reports_installed_after_a_previous_error(monkeypatch):
    monkeypatch.setattr(whisper_runtime, "is_installed", lambda: True)
    whisper_runtime._set_state(status="error", progress=12, message="安装失败", log_tail="")
    try:
        assert whisper_runtime.get_status()["status"] == "installed"
    finally:
        whisper_runtime._set_state(status="unknown", progress=0, message="", log_tail="")


def test_install_error_is_remembered_after_the_process_forgets(tmp_path, monkeypatch):
    monkeypatch.setattr(whisper_runtime, "_data_dir", lambda: tmp_path)
    monkeypatch.setattr(whisper_runtime, "is_installed", lambda: False)
    whisper_runtime._set_state(status="unknown", progress=0, message="", log_tail="")
    whisper_runtime._write_install_error("安装失败（pip 退出码 1）")
    try:
        status = whisper_runtime.get_status()
        assert status["status"] == "error"
        assert "退出码" in status["message"]
    finally:
        whisper_runtime._clear_install_error()
        whisper_runtime._set_state(status="unknown", progress=0, message="", log_tail="")


def test_missing_runtime_points_at_transcription_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(whisper_runtime, "is_installed", lambda: False)
    recognizer = _recognizer()
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    with pytest.raises(SpeechRecognitionError) as exc:
        recognizer._generate_subtitle_whisper_local(video, tmp_path / "clip.srt", SpeechRecognitionConfig())
    assert "设置 → 转写" in str(exc.value)
    assert "语音识别" not in str(exc.value)
    assert ".srt" in str(exc.value)


def test_failure_text_has_no_local_path():
    message = describe_whisper_failure(RuntimeError(r"failed to open C:\Users\secret\clip.mp4"))
    assert "secret" not in message
    assert "clip.mp4" not in message
    assert "设置 → 转写" in message


def _install_fake_whisper(monkeypatch, factory):
    module = types.ModuleType("faster_whisper")
    module.WhisperModel = factory
    monkeypatch.setitem(sys.modules, "faster_whisper", module)
    monkeypatch.setattr(whisper_runtime, "is_installed", lambda: True)
    monkeypatch.setattr(whisper_runtime, "ensure_on_path", lambda: None)
    monkeypatch.setattr(whisper_runtime, "get_models_dir", lambda: Path("/tmp/autoclip-whisper-models"))


def _recognizer():
    # 跳过 __init__ 里对其它识别后端的探测
    recognizer = SpeechRecognizer.__new__(SpeechRecognizer)
    recognizer.config = SpeechRecognitionConfig()
    recognizer.available_methods = {}
    return recognizer


def test_cpu_encode_error_becomes_readable_and_is_not_logged_with_traceback(tmp_path, monkeypatch, caplog):
    monkeypatch.delenv("AUTOCLIP_WHISPER_DEVICE", raising=False)
    calls = []

    class FakeModel:
        def __init__(self, model, device="auto", compute_type="int8", download_root=None):
            calls.append((device, compute_type))

        def transcribe(self, path, language=None, vad_filter=False):
            raise RuntimeError("cuBLAS failed with status CUBLAS_STATUS_NOT_SUPPORTED")

    _install_fake_whisper(monkeypatch, FakeModel)
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    output = tmp_path / "clip.srt"

    with caplog.at_level("ERROR"):
        with pytest.raises(SpeechRecognitionError) as exc:
            _recognizer()._generate_subtitle_whisper_local(video, output, SpeechRecognitionConfig())

    assert calls == [("cpu", "int8")]
    assert "显卡" in str(exc.value)
    assert not output.exists()
    assert all(record.exc_info in (None, (None, None, None)) for record in caplog.records)


def test_vad_fail_retries_without_filter_and_still_writes_srt(tmp_path, monkeypatch):
    monkeypatch.delenv("AUTOCLIP_WHISPER_DEVICE", raising=False)
    vad_flags = []

    class FakeModel:
        def __init__(self, model, device="auto", compute_type="int8", download_root=None):
            assert (device, compute_type) == ("cpu", "int8")

        def transcribe(self, path, language=None, vad_filter=False):
            vad_flags.append(vad_filter)
            if vad_filter:
                raise Fail("Non-zero status code returned while running")
            return [SimpleNamespace(start=0.0, end=1.5, text="你好")], None

    _install_fake_whisper(monkeypatch, FakeModel)
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    output = tmp_path / "clip.srt"

    result = _recognizer()._generate_subtitle_whisper_local(video, output, SpeechRecognitionConfig())

    assert vad_flags == [True, False]
    assert result == output
    assert "你好" in output.read_text(encoding="utf-8")


def test_generate_subtitle_accepts_import_keyword_arguments(tmp_path):
    """导入任务会传入时间戳、超时和密钥。这些参数不能在进到 Whisper 之前变成 TypeError。"""
    missing = tmp_path / "missing.mp4"
    with pytest.raises(SpeechRecognitionError, match="视频文件不存在"):
        generate_subtitle_for_video(
            missing,
            language="auto",
            model="base",
            method="whisper_local",
            enable_timestamps=True,
            enable_punctuation=True,
            enable_speaker_diarization=False,
            timeout=1800,
        )
    with pytest.raises(SpeechRecognitionError, match="视频文件不存在"):
        generate_subtitle_for_video(
            missing,
            method="openai_api",
            language="auto",
            api_key="sk-test",
            enable_timestamps=True,
            enable_punctuation=True,
        )


def test_blank_segments_are_not_written_as_success(tmp_path, monkeypatch):
    monkeypatch.delenv("AUTOCLIP_WHISPER_DEVICE", raising=False)

    class FakeModel:
        def __init__(self, model, device="auto", compute_type="int8", download_root=None):
            pass

        def transcribe(self, path, language=None, vad_filter=False):
            return [
                SimpleNamespace(start=0.0, end=1.0, text="   "),
                SimpleNamespace(start=1.0, end=2.0, text=""),
            ], None

    _install_fake_whisper(monkeypatch, FakeModel)
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    output = tmp_path / "clip.srt"

    with pytest.raises(SpeechRecognitionError, match="未识别出任何语音"):
        _recognizer()._generate_subtitle_whisper_local(video, output, SpeechRecognitionConfig())

    assert not output.exists()


def test_existing_blank_srt_is_transcribed_again(tmp_path, monkeypatch):
    monkeypatch.delenv("AUTOCLIP_WHISPER_DEVICE", raising=False)
    calls = []

    class FakeModel:
        def __init__(self, model, device="auto", compute_type="int8", download_root=None):
            pass

        def transcribe(self, path, language=None, vad_filter=False):
            calls.append(vad_filter)
            return [SimpleNamespace(start=0.0, end=1.2, text="有人声")], None

    _install_fake_whisper(monkeypatch, FakeModel)
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    output = tmp_path / "clip.srt"
    output.write_text("\n", encoding="utf-8")

    result = _recognizer()._generate_subtitle_whisper_local(video, output, SpeechRecognitionConfig())

    assert calls == [True]
    assert result == output
    assert "有人声" in output.read_text(encoding="utf-8")


def test_existing_srt_with_cue_text_skips_whisper(tmp_path, monkeypatch):
    class FakeModel:
        def __init__(self, model, device="auto", compute_type="int8", download_root=None):
            raise AssertionError("已有字幕正文时不应再加载 Whisper")

    _install_fake_whisper(monkeypatch, FakeModel)
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    output = tmp_path / "clip.srt"
    output.write_text("1\n00:00:00,000 --> 00:00:01,000\n已有\n", encoding="utf-8")

    result = _recognizer()._generate_subtitle_whisper_local(video, output, SpeechRecognitionConfig())

    assert result == output
    assert "已有" in output.read_text(encoding="utf-8")


def test_gpu_runtime_error_retries_on_cpu(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCLIP_WHISPER_DEVICE", "cuda")
    constructed = []

    class FakeModel:
        def __init__(self, model, device="auto", compute_type="int8", download_root=None):
            self.device = device
            constructed.append((device, compute_type))

        def transcribe(self, path, language=None, vad_filter=False):
            if self.device != "cpu":
                raise RuntimeError("CUDA failed with error out of memory")
            return [SimpleNamespace(start=0.2, end=0.8, text="ok")], None

    _install_fake_whisper(monkeypatch, FakeModel)
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    output = tmp_path / "clip.srt"

    result = _recognizer()._generate_subtitle_whisper_local(video, output, SpeechRecognitionConfig())

    assert constructed[0] == ("cuda", "float16")
    assert ("cpu", "int8") in constructed
    assert result == output
    assert "ok" in output.read_text(encoding="utf-8")

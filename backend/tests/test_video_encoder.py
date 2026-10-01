"""Hardware H.264 when it works, libx264 otherwise; a failed hardware encode retries in software."""
import subprocess

from backend.services import video_encoder as v


def test_bitrate_scales_with_the_frame_and_software_keeps_crf():
    hd = v.h264_args(1080, 1920, 'h264_videotoolbox')
    assert hd[:2] == ['-c:v', 'h264_videotoolbox'] and hd[hd.index('-b:v') + 1] == str(int(1080 * 1920 * 30 * 0.13))
    assert v.h264_args(1080, 1920, 'libx264') == ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p']


def test_forcing_software_skips_the_probe(monkeypatch):
    monkeypatch.setenv('AUTOCLIP_VIDEO_ENCODER', 'x264')
    monkeypatch.setattr(v, '_works', lambda *_: (_ for _ in ()).throw(AssertionError('no probe')))
    assert v.encoder() == 'libx264'


def test_a_failed_hardware_encode_retries_in_software_and_sticks(monkeypatch):
    monkeypatch.delenv('AUTOCLIP_VIDEO_ENCODER', raising=False)
    monkeypatch.setattr(v, '_chosen', None)
    monkeypatch.setattr(v, '_broken', set())
    monkeypatch.setattr(v, '_candidates', lambda: ['h264_videotoolbox'])
    monkeypatch.setattr(v, '_works', lambda _ffmpeg, name: True)
    runs = []

    def run(cmd):
        runs.append(cmd[0])
        return subprocess.CompletedProcess(cmd, 1 if cmd[0] == 'h264_videotoolbox' else 0)

    assert v.run_with_fallback(lambda name: [name], run).returncode == 0
    assert runs == ['h264_videotoolbox', 'libx264'] and v.encoder() == 'libx264'


def test_a_stalled_hardware_encoder_falls_back_and_a_bad_input_does_not_disable_it(monkeypatch):
    from backend.services import video_encoder as v
    monkeypatch.delenv('AUTOCLIP_VIDEO_ENCODER', raising=False)
    monkeypatch.setattr(v, '_chosen', None)
    monkeypatch.setattr(v, '_broken', set())
    monkeypatch.setattr(v, '_candidates', lambda: ['h264_videotoolbox'])
    monkeypatch.setattr(v, '_works', lambda _ffmpeg, name: True)

    def stalls(cmd):
        if cmd[0] == 'h264_videotoolbox':
            raise subprocess.TimeoutExpired(cmd, 1)
        return subprocess.CompletedProcess(cmd, 0)
    assert v.run_with_fallback(lambda name: [name], stalls).returncode == 0
    monkeypatch.setattr(v, '_chosen', None)
    monkeypatch.setattr(v, '_broken', set())
    assert v.run_with_fallback(lambda name: [name], lambda cmd: subprocess.CompletedProcess(cmd, 1)).returncode == 1
    assert v.encoder() == 'h264_videotoolbox', 'a source that fails both encoders keeps hardware encoding on'

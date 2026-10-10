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


def test_probe_covers_nvenc_qsv_amf_and_videotoolbox_then_libx264(monkeypatch):
    import sys
    monkeypatch.setattr(sys, 'platform', 'darwin')
    assert v._candidates() == ['h264_videotoolbox']
    monkeypatch.setattr(sys, 'platform', 'win32')
    assert v._candidates() == ['h264_nvenc', 'h264_qsv', 'h264_amf']
    monkeypatch.setattr(sys, 'platform', 'linux')
    assert v._candidates() == ['h264_nvenc', 'h264_qsv', 'h264_amf']

    monkeypatch.delenv('AUTOCLIP_VIDEO_ENCODER', raising=False)
    monkeypatch.setattr(v, '_candidates', lambda: ['h264_nvenc', 'h264_qsv', 'h264_amf'])
    monkeypatch.setattr(v, '_chosen', None)
    monkeypatch.setattr(v, '_broken', set())
    seen = []

    def works(_ffmpeg, name):
        seen.append(name)
        return name == 'h264_qsv'

    monkeypatch.setattr(v, '_works', works)
    assert v.encoder() == 'h264_qsv'
    assert seen == ['h264_nvenc', 'h264_qsv']

    monkeypatch.setattr(v, '_chosen', None)
    monkeypatch.setattr(v, '_broken', set())
    seen.clear()

    def name_is_amf(_ffmpeg, name):
        seen.append(name)
        return name == 'h264_amf'

    monkeypatch.setattr(v, '_works', name_is_amf)
    assert v.encoder() == 'h264_amf'
    assert seen == ['h264_nvenc', 'h264_qsv', 'h264_amf']

    monkeypatch.setattr(v, '_candidates', lambda: ['h264_videotoolbox'])
    monkeypatch.setattr(v, '_chosen', None)
    monkeypatch.setattr(v, '_broken', set())
    seen.clear()
    monkeypatch.setattr(v, '_works', lambda _ffmpeg, name: seen.append(name) or True)
    assert v.encoder() == 'h264_videotoolbox'
    assert seen == ['h264_videotoolbox']

    monkeypatch.setattr(v, '_candidates', lambda: ['h264_nvenc', 'h264_qsv', 'h264_amf'])
    monkeypatch.setattr(v, '_chosen', None)
    monkeypatch.setattr(v, '_broken', set())
    monkeypatch.setattr(v, '_works', lambda *_args: False)
    assert v.encoder() == 'libx264'


def test_a_probe_oserror_is_a_miss_and_software_args_stay_veryfast(monkeypatch):
    monkeypatch.setattr(subprocess, 'run', lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError('device node')))
    assert v._works('ffmpeg', 'h264_nvenc') is False
    assert v.h264_args(64, 64, 'libx264') == ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p']


def test_each_hardware_encoder_falls_back_to_libx264_veryfast(monkeypatch):
    monkeypatch.delenv('AUTOCLIP_VIDEO_ENCODER', raising=False)
    for name in ('h264_nvenc', 'h264_qsv', 'h264_amf', 'h264_videotoolbox'):
        monkeypatch.setattr(v, '_chosen', None)
        monkeypatch.setattr(v, '_broken', set())
        monkeypatch.setattr(v, '_candidates', lambda name=name: [name])
        monkeypatch.setattr(v, '_works', lambda *_args: True)
        calls = []

        def run(cmd, calls=calls):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0 if 'libx264' in cmd else 1)

        assert v.run_with_fallback(lambda encoder: v.h264_args(320, 568, encoder), run).returncode == 0
        assert calls[0][1] == name
        assert calls[-1][1:6] == ['libx264', '-preset', 'veryfast', '-crf', '20']


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

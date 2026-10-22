"""Sample-aligned original audio with short cut fades and silent-range padding."""
import json
import subprocess
from backend.utils.ffmpeg_utils import get_ffprobe_path


def has_audio(video):
    result = subprocess.run([get_ffprobe_path(), '-v', 'error', '-select_streams', 'a:0',
        '-show_entries', 'stream=index', '-of', 'json', str(video)], capture_output=True,
        text=True, check=True, timeout=30)
    return bool(json.loads(result.stdout).get('streams'))


def scene_duration(scene):
    # All video cuts are 30 fps; align audio to the same whole-frame durations.
    return max(1, round((scene.end-scene.start)*30)) / 30


def cut_filters(silence_input, duration):
    # The silence input is finite via atrim. It also covers ranges after the
    # original audio track ends, where apad alone receives no input frames.
    fade_in = min(.008, duration/4)
    fade_out = min(.012, duration/4)
    return (
        '[0:a:0]aresample=48000:async=1:first_pts=0,'
        'aformat=sample_fmts=fltp:channel_layouts=stereo[original];'
        f'[{silence_input}:a:0][original]amix=inputs=2:duration=longest:normalize=0,'
        f'atrim=duration={duration},asetpts=PTS-STARTPTS,'
        f'afade=t=in:st=0:d={fade_in},afade=t=out:st={duration-fade_out}:d={fade_out}[audioout]'
    )


# The social target the loudness QA checks: -14 LUFS integrated, true peak at or below -1 dBTP.
# The second pass aims 1 dB under the ceiling so the AAC encode's overshoot stays at or below -1 dBTP.
LOUDNORM_TARGET = {'I': -14.0, 'TP': -2.0, 'LRA': 11.0}
_RESAMPLE = 'aresample=48000:async=1:first_pts=0'


def _loudnorm(extra: str = '') -> str:
    target = LOUDNORM_TARGET
    return f"loudnorm=I={target['I']}:TP={target['TP']}:LRA={target['LRA']}{extra}"


def parse_loudnorm(text: str) -> dict | None:
    """The measured block loudnorm prints with print_format=json, or None."""
    end = text.rfind('}')
    start = text.rfind('{', 0, end)
    if start < 0 or end < 0:
        return None
    try:
        data = json.loads(text[start:end + 1])
        values = {key: float(data[key]) for key in ('input_i', 'input_tp', 'input_lra', 'input_thresh', 'target_offset')}
    except (KeyError, TypeError, ValueError):
        return None
    # Silence measures -inf / -70; a second pass would only add noise gain.
    if values['input_i'] <= -60 or any(value != value or abs(value) == float('inf') for value in values.values()):
        return None
    return values


def loudnorm_filter(measured: dict | None) -> str:
    """The final mix's audio filter: two-pass loudnorm when measured, else the plain resample."""
    if not measured:
        return _RESAMPLE
    second = (
        f":measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
        f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
        f":offset={measured['target_offset']}:linear=true"
    )
    # loudnorm works at 192 kHz; bring it back to the 48 kHz the encode uses.
    return f'{_RESAMPLE},{_loudnorm(second)},aresample=48000'


def measure_loudnorm(input_args: list[str], run, timeout: float) -> dict | None:
    """First pass over the joined audio. Any failure keeps the plain mix."""
    from backend.utils.ffmpeg_utils import get_ffmpeg_path
    cmd = [get_ffmpeg_path(), '-hide_banner', '-nostats', *input_args, '-map', '0:a:0', '-vn', '-sn', '-dn',
           '-af', f'{_RESAMPLE},{_loudnorm(":print_format=json")}', '-f', 'null', '-']
    try:
        proc = run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode:
        return None
    return parse_loudnorm(proc.stderr or '')

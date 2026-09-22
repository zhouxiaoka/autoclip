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

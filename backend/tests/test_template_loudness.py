"""Exported audio is loudness-normalised to the preview's -14 LUFS / -1 dBTP."""
import subprocess

from backend.services.studio import audio
from backend.services.studio.qa.loudness import parse_summary
from backend.utils.ffmpeg_utils import get_ffmpeg_path


def _speechlike(path, gain_db):
    # Pink noise gated like syllables, about -22 LUFS like dad_suit e.
    subprocess.run([
        get_ffmpeg_path(), '-v', 'error', '-f', 'lavfi', '-i', 'anoisesrc=color=pink:duration=12:sample_rate=48000:seed=7',
        '-af', f"volume='if(lt(mod(t,0.5),0.3),1,0.05)':eval=frame,volume={gain_db}dB,aformat=channel_layouts=stereo",
        '-c:a', 'pcm_s16le', '-y', str(path),
    ], check=True)


def _levels(path):
    proc = subprocess.run([get_ffmpeg_path(), '-hide_banner', '-nostats', '-i', str(path), '-map', '0:a:0', '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                          capture_output=True, text=True, check=True)
    return parse_summary(proc.stderr)


def test_two_pass_loudnorm_lands_on_minus_14_lufs_under_minus_1_dbtp(tmp_path):
    source = tmp_path / 'part.wav'
    _speechlike(source, -12)
    before, _ = _levels(source)
    assert before < -18, before
    concat = tmp_path / 'parts.txt'
    concat.write_text(f"file '{source}'\nduration 12.0\n")
    measured = audio.measure_loudnorm(['-f', 'concat', '-safe', '0', '-i', str(concat)], subprocess.run, 60)
    assert measured and abs(measured['input_i'] - before) < 1.0, measured
    out = tmp_path / 'out.m4a'
    subprocess.run([get_ffmpeg_path(), '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(concat), '-map', '0:a:0',
                    '-af', audio.loudnorm_filter(measured), '-c:a', 'aac', '-b:a', '160k', '-y', str(out)], check=True)
    lufs, peak = _levels(out)
    assert abs(lufs + 14.0) <= 1.0, lufs
    assert peak <= -1.0, peak


def test_without_a_measurement_the_mix_is_the_old_filter():
    # Classic and a failed first pass keep the exact filter the RC used.
    assert audio.loudnorm_filter(None) == 'aresample=48000:async=1:first_pts=0'
    assert audio.parse_loudnorm('no json here') is None
    assert audio.parse_loudnorm('{"input_i": "-inf", "input_tp": "-inf", "input_lra": "0", "input_thresh": "-70", "target_offset": "0"}') is None


def test_render_normalises_the_final_mix():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / 'services' / 'studio' / 'render.py').read_text(encoding='utf-8')
    start = source.index('Preview and QA both expect -14 LUFS')
    block = source[start:source.index("'-c:a', 'aac', '-b:a', '160k']", start)]
    assert 'measure_loudnorm' in block and 'loudnorm_filter' in block
    assert 'html_template in HTML_TEMPLATE_IDS' not in block

"""Installed runtime acceptance for speaker framing and local covers; no paid calls."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--resources', type=Path, required=True)
parser.add_argument('--report', type=Path, default=Path('installed-publishing-report.json'))
args = parser.parse_args()
report_path = args.report.resolve()
source = Path(__file__).resolve().parents[1] / 'backend/assets/example/source.mp4'
resources = args.resources.resolve(strict=True)
assert Path(sys.executable).resolve().is_relative_to(resources / 'python'), 'installed Python required'
root = Path(tempfile.mkdtemp(prefix='autoclip-publishing-acceptance-'))
os.environ.update(AUTOCLIP_DATA_DIR=str(root), AUTOCLIP_APP_DIR=str(root),
                  AUTOCLIP_FFMPEG_PATH=str(resources / 'ffmpeg/ffmpeg.exe'),
                  AUTOCLIP_FFPROBE_PATH=str(resources / 'ffmpeg/ffprobe.exe'))
os.chdir(resources)
sys.path.insert(0, str(resources))
import backend
assert Path(backend.__file__).resolve().is_relative_to(resources / 'backend')
from PIL import Image
from backend.services.studio import framing
from backend.services.studio.models import Draft, Scene
from backend.services.studio.render import render_draft
from backend.services.studio.store import directory
from backend.services.publish_export import _probe
from backend.services.studio.audio import has_audio
from backend.services import cover

framing._do_install('https://pypi.org/simple')
assert framing.get_status()['status'] == 'installed', framing.get_status()
info = _probe(source)
draft = Draft(id='speaker', title='公开访谈人物取景验收', aspect='portrait', layout='crop',
              subtitles=False, scenes=[Scene(id='speech', start=0, end=6)])
result = framing.auto_frame(source, draft, info['width'], info['height'])
scene = result['scenes'][0]
assert scene['faces'] > 0 and scene['crop_track'], result
draft.scenes = [Scene(id='speech', start=0, end=6, crop_x=scene['crop_x'],
                      crop_track=scene['crop_track'], framing_source='auto')]
pid = 'publishing-acceptance'
project = directory(pid)
(project / 'metadata').mkdir(parents=True)
render_draft(pid, source, draft, 'speaker', lambda _: None)
video = project / 'output/studio/speaker.mp4'
rendered = _probe(video)
assert (rendered['width'], rendered['height']) == (1080, 1920)
assert 5.9 <= rendered['duration'] <= 6.1 and has_audio(video)
(project / 'metadata/clips_metadata.json').write_text(json.dumps([{
    'id': '1', 'generated_title': '公开访谈', 'start_time': '00:00:00,000',
    'end_time': '00:00:06,000', 'source_type': 'studio', 'video_path': str(video),
}]), encoding='utf-8')
# Isolated disabled cover configuration and a hard guard against any paid call.
cover.save_config(enabled=False, provider='openai', model='', api_key='')
def no_image_calls(*args, **kwargs):
    raise AssertionError('paid image generation is outside this acceptance')
cover.generate_image = no_image_calls
covers = {}
for platform, size in [('bilibili', (1146, 717)), ('douyin', (1080, 1920))]:
    generated = cover.generate_cover(project_id=pid, clip_id='1', platform=platform,
                                     title='公开访谈', subtitle='人物取景验收')
    assert generated['ok'] and generated['method'] in ('local_overlay', 'frame'), generated
    with Image.open(generated['path']) as img:
        assert img.size == size
    covers[platform] = {'method': generated['method'], 'width': size[0], 'height': size[1]}
report_path.write_text(json.dumps({
    'runtime_source': 'installed portable Python and installed backend',
    'source': 'repository public interview, first six seconds',
    'framing_runtime_install': 'passed', 'actual_face_detection': 'passed',
    'samples': scene['samples'], 'faces': scene['faces'], 'crop_track': scene['crop_track'],
    'portrait_render': rendered, 'original_audio': 'passed', 'covers': covers, 'paid_calls': 0,
}, ensure_ascii=False, indent=2), encoding='utf-8')
print('Installed face detection, portrait render and both local covers passed')

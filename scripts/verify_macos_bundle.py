#!/usr/bin/env python3
"""Validate the shipped runtime without developer dependencies or model calls.

Produces isolated evidence in a new temporary directory. Does not install the
app, test native UI/updater/signatures, or evaluate creative/ad quality.
"""
import os,sys,json,subprocess,time,select
from pathlib import Path
from urllib.request import urlopen
import argparse
import hashlib
import tempfile

parser = argparse.ArgumentParser(description="Offline macOS bundled-runtime smoke check; run with the bundle's python/bin/python3.")
parser.add_argument('--resources', type=Path, required=True, help='App Contents/Resources/resources directory')
parser.add_argument('--output-parent', type=Path, default=Path(tempfile.gettempdir()))
args = parser.parse_args()
resources = args.resources.resolve(strict=True)
if not Path(sys.executable).resolve().is_relative_to(resources / 'python'):
    parser.error('Use the Python executable inside this bundle, not a development virtualenv.')
args.output_parent.mkdir(parents=True, exist_ok=True)
root = Path(tempfile.mkdtemp(prefix='autoclip-bundle-smoke-', dir=args.output_parent)).resolve()
print('Isolated evidence directory:', root, flush=True)
for required in ['backend/desktop_main.py', 'ffmpeg/ffmpeg', 'ffmpeg/ffprobe']:
    if not (resources / required).is_file():
        parser.error('Missing bundled runtime file: ' + required)
os.environ.update(AUTOCLIP_DATA_DIR=str(root/'data'),AUTOCLIP_APP_DIR=str(root/'data'),AUTOCLIP_DESKTOP_MODE='true',AUTOCLIP_MODE='desktop',DATABASE_URL='sqlite:///'+str(root/'isolated.sqlite'),SENTRY_DSN='',AUTOCLIP_FFMPEG_PATH=str(resources/'ffmpeg/ffmpeg'),AUTOCLIP_FFPROBE_PATH=str(resources/'ffmpeg/ffprobe'))
(root/'data').mkdir(exist_ok=True);(root/'data/privacy.json').write_text('{"crash_reports":false}')
os.chdir(resources);sys.path.insert(0,str(resources))
import backend
assert Path(backend.__file__).resolve().is_relative_to(resources), "Backend imported outside the app bundle"
from backend.services.studio.models import Draft,Scene
from backend.services.studio.render import render_draft
from backend.services.studio.store import directory
from backend.services.studio.title_art import png_bytes
from backend.services.publish_export import _probe
pid='bundle-smoke';directory(pid).mkdir(parents=True,exist_ok=True)
for style in ['comic','neon','arena','editorial','pixel','frosted']:
 assert png_bytes('极限过弯\nCAN YOU ESCAPE?',style,1080,1920,version=6).startswith(b'\x89PNG')
d=Draft(id='bundle',title='Bundle smoke',hook='极限过弯\nCAN YOU ESCAPE?',title_style='comic',title_template_version=6,title_motion=False,aspect='portrait',subtitles=False,scenes=[Scene(id='fixture',start=0,end=1)])
source=root/'fixture.mp4'
subprocess.run([str(resources/'ffmpeg/ffmpeg'), '-v', 'error', '-f', 'lavfi', '-i',
                'testsrc2=size=640x360:rate=30:duration=1.2', '-f', 'lavfi', '-i',
                'sine=frequency=440:sample_rate=48000:duration=1.2', '-c:v', 'libx264',
                '-c:a', 'aac', '-shortest', str(source)], check=True, timeout=30)
render_draft(pid,source,d,'bundle-output',lambda _:None)
out=directory(pid)/'output/studio/bundle-output.mp4';info=_probe(out)
assert info['width']==1080 and info['height']==1920
assert .9 <= info['duration'] <= 1.1
from backend.services.studio.audio import has_audio
assert has_audio(out), 'Rendered original audio is missing'
proc=subprocess.Popen([sys.executable,'-m','backend.desktop_main'],cwd=resources,env=os.environ.copy(),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
try:
 port=None;deadline=time.time()+35
 while time.time()<deadline:
  ready,_,_=select.select([proc.stdout],[],[],.5)
  if ready:
   line=proc.stdout.readline()
   if line.startswith('PORT='):port=int(line.split('=')[1]);break
  if proc.poll() is not None:break
 assert port,'bundled backend failed to start'
 with urlopen(f'http://127.0.0.1:{port}/health',timeout=5) as r:assert r.status==200
 report={'source':'synthetic offline fixture','backend_sha256':hashlib.sha256((resources/'backend/services/studio/render.py').read_bytes()).hexdigest(),'python':sys.version.split()[0],'six_templates':'passed','portrait_render':info,'desktop_health':'passed','output':str(out)}
 (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
finally:
 proc.terminate()
 try:proc.wait(timeout=5)
 except subprocess.TimeoutExpired:proc.kill();proc.wait()

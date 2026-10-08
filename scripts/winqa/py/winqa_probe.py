"""AutoClip Windows QA probe. Runs with the INSTALLED app's bundled Python against the live
desktop backend (port from %APPDATA%\\AutoClip\\backend.port). No paid model calls: the only
model endpoints used are a loopback fixture on 127.0.0.1 and a closed local port.

  python winqa_probe.py seed    --media DIR
  python winqa_probe.py check   --expect-version X.Y.Z --updater-url URL
  python winqa_probe.py failure --media DIR
"""
import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

OUT = Path(os.environ.get('WINQA_OUT', r'C:\winqa\out'))
RES = Path(os.environ['WINQA_RESOURCES']) if os.environ.get('WINQA_RESOURCES') else Path(sys.executable).resolve().parents[1]
DATA = Path(os.environ['APPDATA']) / 'AutoClip'
W = {'Origin': 'http://tauri.localhost'}  # the desktop UI's own origin (writes from other origins get 403)
SEED_KEY = 'sk-winqa-dummy-not-a-real-key-0000'
# The settings API refuses to save without an analysis model ('请选择高光分析模型'), so the "no key yet"
# state is: an OpenAI connection with an explicitly empty key (what a user has before pasting one).
NO_KEY = {'version': 1, 'connections': [{'id': 'winqa-nokey', 'name': 'WinQA no key', 'provider': 'openai', 'api_key': ''}],
          'analysis': {'connection_id': 'winqa-nokey', 'model': 'gpt-4o-mini', 'capability': 'text'},
          'analysis_mode': 'auto', 'allow_visual_screening': True, 'cover_enabled': False, 'allow_send_frame': False}


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%S%z')


def base():
    return 'http://127.0.0.1:' + (DATA / 'backend.port').read_text().strip()


def get(path, **kw):
    return requests.get(base() + path, timeout=kw.pop('timeout', 30), **kw)


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    print('saved', OUT / name, flush=True)


def body(r, limit=4000):
    try:
        return r.json()
    except ValueError:
        return r.text[:limit]


def redact(text):
    text = re.sub(r'sk-[A-Za-z0-9_\-]{6,}', 'sk-***', text)
    text = re.sub(r'(?i)(api[_-]?key|authorization|bearer)(["\'=:\s]+)[^\s"\',]+', r'\1\2***', text)
    return re.sub(r'C:\\\\?Users\\\\?[^\\\\]+', r'C:\\Users\\<user>', text)


# ---------------------------------------------------------------- media
def media(src_dir, seconds, tag):
    ffmpeg = RES / 'ffmpeg' / 'ffmpeg.exe'
    work = OUT / 'media'
    work.mkdir(exist_ok=True)
    video = work / f'公开访谈 {tag} {seconds}秒.mp4'
    srt = work / f'公开访谈 {tag} {seconds}秒.srt'
    if not video.exists():
        subprocess.run([str(ffmpeg), '-v', 'error', '-y', '-i', str(Path(src_dir) / 'source.mp4'), '-t', str(seconds), '-c', 'copy', str(video)],
                       check=True, timeout=120)
    def sec(t):
        h, m, s = t.replace(',', '.').split(':')
        return int(h) * 3600 + int(m) * 60 + float(s)
    def fmt(x):
        ms = int(round(x * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
        return f'{h:02}:{m:02}:{s:02},{ms:03}'
    blocks = re.split(r'\r?\n\r?\n', (Path(src_dir) / 'source.srt').read_text(encoding='utf-8-sig').strip())
    rows = []
    for b in blocks:
        lines = b.strip().splitlines()
        if len(lines) < 3 or '-->' not in lines[1]:
            continue
        a, z = [x.strip() for x in lines[1].split('-->')]
        if sec(a) < seconds:
            rows.append(f'{len(rows) + 1}\n{fmt(sec(a))} --> {fmt(min(seconds, sec(z)))}\n' + '\n'.join(lines[2:]) + '\n')
    srt.write_text('\n'.join(rows), encoding='utf-8')
    return video, srt


def studio_import(video, srt, name, auto_start):
    with video.open('rb') as v, srt.open('rb') as s:
        r = requests.post(base() + '/api/v1/studio/import',
                          data={'name': name, 'auto_start': 'true' if auto_start else 'false', 'platforms': 'douyin'},
                          files={'video': (video.name, v, 'video/mp4'), 'subtitle': (srt.name, s, 'application/x-subrip')},
                          headers=W, timeout=180)
    r.raise_for_status()
    return r.json()['project_id']


def projects_index():
    r = get('/api/v1/projects/')
    data = body(r)
    items = data.get('items') or data.get('projects') or data.get('data') or [] if isinstance(data, dict) else data
    return r.status_code, [{'id': p.get('id'), 'name': p.get('name'), 'status': p.get('status'),
                            'studio_generation_status': (p.get('processing_config') or {}).get('studio_generation_status')}
                           for p in items if isinstance(p, dict)]


# ---------------------------------------------------------------- phases
def seed(args):
    out = {'phase': 'seed', 'started_at': now(), 'base': base()}
    out['health'] = body(get('/health'))
    st = body(get('/api/v1/settings/'))
    out['app_version'] = (st.get('basic') or {}).get('app_version') if isinstance(st, dict) else None
    r = requests.put(base() + '/api/v1/settings/privacy', json={'crash_reports': False}, headers=W, timeout=20)
    out['privacy_put'] = [r.status_code, body(r)]
    cfg = {'version': 1,
           'connections': [{'id': 'winqa-seed', 'name': 'WinQA seed (dummy key, never called)', 'provider': 'openai', 'api_key': SEED_KEY}],
           'analysis': {'connection_id': 'winqa-seed', 'model': 'gpt-winqa-dummy', 'capability': 'text'},
           'analysis_mode': 'subtitle', 'allow_visual_screening': False, 'cover_enabled': False, 'allow_send_frame': False}
    r = requests.put(base() + '/api/v1/settings/ai-models', json=cfg, headers=W, timeout=20)
    out['ai_models_put'] = r.status_code
    out['ai_models_get'] = body(get('/api/v1/settings/ai-models'))
    video, srt = media(args.media, 20, 'seed')
    pid = studio_import(video, srt, 'WinQA 升级保留项目', auto_start=False)
    out['seed_project_id'] = pid
    time.sleep(8)
    ws = body(get(f'/api/v1/studio/{pid}'))
    out['seed_project_analysis'] = (ws.get('analysis') if isinstance(ws, dict) else ws)
    out['projects'] = projects_index()
    out['finished_at'] = now()
    save('seed.json', out)


def check(args):
    out = {'phase': 'check', 'started_at': now(), 'base': base(), 'assertions': {}}
    A = out['assertions']
    h = get('/health')
    out['health'] = [h.status_code, body(h)]
    A['backend_health_200'] = h.status_code == 200
    st = get('/api/v1/settings/')
    sj = body(st)
    out['settings_status'] = st.status_code
    out['app_version'] = (sj.get('basic') or {}).get('app_version') if isinstance(sj, dict) else None
    A['settings_endpoint_200'] = st.status_code == 200
    A['reported_version_matches'] = out['app_version'] == args.expect_version
    pr = body(get('/api/v1/settings/privacy'))
    out['privacy'] = pr
    seedf = OUT / 'seed.json'
    if seedf.exists():
        seedv = json.loads(seedf.read_text(encoding='utf-8'))
        A['upgrade_kept_privacy_off'] = isinstance(pr, dict) and pr.get('crash_reports') is False
        ai = body(get('/api/v1/settings/ai-models'))
        conn = next((c for c in (ai.get('connections') or []) if c.get('id') == 'winqa-seed'), None) if isinstance(ai, dict) else None
        out['upgrade_ai_models_seed_connection'] = conn
        A['upgrade_kept_model_connection_and_key'] = bool(conn and conn.get('has_key') and (ai.get('analysis') or {}).get('model') == 'gpt-winqa-dummy')
        pid = seedv.get('seed_project_id')
        r = get(f'/api/v1/studio/{pid}')
        out['upgrade_seed_project_status'] = r.status_code
        code, items = projects_index()
        A['upgrade_kept_project'] = r.status_code == 200 and any(p['id'] == pid for p in items)
        rd = get('/api/v1/studio/readiness')
        out['readiness_with_seed_settings'] = [rd.status_code, body(rd)]
    # "No key, no Whisper" state (see NO_KEY).
    r = requests.put(base() + '/api/v1/settings/ai-models', json=NO_KEY, headers=W, timeout=20)
    out['clear_ai_models'] = [r.status_code, body(r, 500) if r.status_code != 200 else 'ok']
    rd = get('/api/v1/studio/readiness')
    rj = body(rd)
    out['readiness_no_model'] = [rd.status_code, rj]
    A['readiness_endpoint_200'] = rd.status_code == 200
    A['no_key_settings_saved'] = r.status_code == 200
    if isinstance(rj, dict):
        c = rj.get('checks') or {}
        A['readiness_not_ready_without_model'] = rj.get('ready') is False
        A['readiness_analysis_fix_entry'] = (c.get('analysis') or {}).get('ok') is False and (c.get('analysis') or {}).get('repair') == 'settings_ai'
        A['readiness_whisper_fix_entry'] = (c.get('transcription') or {}).get('ok') is False and (c.get('transcription') or {}).get('repair') == 'install_whisper'
        A['readiness_ffmpeg_ok'] = (c.get('ffmpeg') or {}).get('ok') is True
        A['readiness_visual_optional_in_auto'] = (c.get('visual') or {}).get('ok') is True
    # Updater manifest the app is configured with (tauri.conf.json plugins.updater.endpoints is compiled into the exe).
    exe = next((p for p in RES.parent.glob('*.exe') if 'uninstall' not in p.name.lower()), None)
    out['exe'] = exe.name if exe else None
    if exe:
        raw = exe.read_bytes()
        found = sorted({m.decode() for m in re.findall(rb'https://[A-Za-z0-9./_\-]*latest\.json', raw)})
        out['updater_endpoints_in_exe'] = found
        A['updater_endpoint_embedded'] = args.updater_url in found
    t0 = time.monotonic()
    try:
        u = requests.get(args.updater_url, timeout=60, allow_redirects=True)
        uj = u.json()
        out['updater_fetch'] = {'status': u.status_code, 'final_url': re.sub(r'\?.*', '', u.url), 'seconds': round(time.monotonic() - t0, 1),
                                'version': uj.get('version'), 'pub_date': uj.get('pub_date'), 'platforms': sorted((uj.get('platforms') or {}).keys()),
                                'windows_url': ((uj.get('platforms') or {}).get('windows-x86_64') or {}).get('url')}
        A['updater_manifest_readable'] = u.status_code == 200 and bool(uj.get('version')) and 'windows-x86_64' in (uj.get('platforms') or {})
    except Exception as e:  # network from mainland VM to GitHub can be flaky; record exact error
        out['updater_fetch'] = {'error': f'{type(e).__name__}: {e}'[:400], 'seconds': round(time.monotonic() - t0, 1)}
        A['updater_manifest_readable'] = False
    code, items = projects_index()
    out['projects'] = items
    A['no_project_stuck_processing'] = code == 200 and not any(p['status'] == 'processing' for p in items)
    out['log_celery_lines'] = log_lines(r'(?i)celery')
    out['finished_at'] = now()
    out['ok'] = all(A.values())
    save(f'check-{args.label}.json', out)


def log_lines(pattern, tail=8):
    rows = []
    for p in sorted((DATA / 'logs').glob('*.log')):
        try:
            text = p.read_text(encoding='utf-8', errors='replace').splitlines()
        except OSError:
            continue
        rows += [f'{p.name}: ' + redact(l)[:300] for l in text if re.search(pattern, l)]
    return rows[-tail:]


# ---------------------------------------------------------------- failure / fallback probes
class Fixture(BaseHTTPRequestHandler):
    mode = 'fixture'
    calls = []

    def log_message(self, *_):
        pass

    def send_json(self, data, status=200):
        raw = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.send_json({'object': 'list', 'data': [{'id': 'winqa-model', 'object': 'model'}]})

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        content = req['messages'][-1]['content']
        has_image = isinstance(content, list) and any(isinstance(c, dict) and c.get('type') == 'image_url' for c in content)
        if Fixture.mode == 'all500' or (Fixture.mode == 'screening500' and has_image):
            Fixture.calls.append(('image' if has_image else 'text', 500))
            return self.send_json({'error': {'message': 'winqa injected failure', 'type': 'server_error'}}, 500)
        text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        data = None
        if '\n\n输入内容：\n' in text:
            try:
                data = json.loads(text.rsplit('\n\n输入内容：\n', 1)[1])
            except ValueError:
                data = None
        if isinstance(data, dict) and 'srt_text' in data:
            stage = 'timeline'
            out = [{'outline': row['title'], 'start_time': '00:00:00,000', 'end_time': '00:00:40,000', 'content': 'Public interview excerpt'} for row in data['outline']]
        elif isinstance(data, dict) and 'text' in data:
            stage, out = 'outline', '1. **Public interview**\n   - Public speech excerpt'
        elif isinstance(data, list) and data and 'outline' in data[0]:
            stage = 'score'
            out = [{'id': row.get('id'), 'outline': row['outline'], 'final_score': 0.9, 'recommend_reason': 'fixture'} for row in data]
        elif isinstance(data, list) and data and 'title' in data[0]:
            stage, out = 'title', {str(row['id']): 'WinQA sample' for row in data}
        elif '视频切片列表' in text:
            stage, out = 'collections', []
        else:
            stage, out = 'other', 'OK'
        Fixture.calls.append((stage, 200))
        self.send_json({'id': 'winqa', 'object': 'chat.completion', 'model': 'winqa-model',
                        'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)}, 'finish_reason': 'stop'}],
                        'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}})


def run_scenario(name, cfg, video, srt, timeout):
    r = requests.put(base() + '/api/v1/settings/ai-models', json=cfg, headers=W, timeout=20)
    res = {'scenario': name, 'settings_put': r.status_code}
    rd = body(get('/api/v1/studio/readiness'))
    res['readiness'] = rd
    Fixture.calls = []
    t0 = time.monotonic()
    pid = studio_import(video, srt, f'WinQA {name}', auto_start=True)
    res['project_id'] = pid
    ws = {}
    while time.monotonic() - t0 < timeout:
        ws = body(get(f'/api/v1/studio/{pid}'))
        if isinstance(ws, dict) and (ws.get('generation') or {}).get('status') in ('completed', 'partial', 'failed'):
            break
        time.sleep(2)
    g = (ws.get('generation') or {}) if isinstance(ws, dict) else {}
    plan = (ws.get('plan') or {}) if isinstance(ws, dict) else {}
    an = (ws.get('analysis') or {}) if isinstance(ws, dict) else {}
    res['seconds'] = round(time.monotonic() - t0, 1)
    res['generation'] = {k: g.get(k) for k in ('status', 'error_code', 'failure_stage', 'http_status', 'route', 'completed_variant_count')}
    res['generation_error'] = redact(str(g.get('error') or ''))[:300]
    res['plan'] = {k: plan.get(k) for k in ('mode', 'recommended_analysis', 'confirmed_analysis')}
    rec = plan.get('recommendation') or {}
    res['plan_reason'] = (rec.get('reason') if isinstance(rec, dict) else None) or plan.get('reason')
    res['analysis'] = {k: an.get(k) for k in ('status', 'phase', 'error_code', 'outcome')}
    res['jobs'] = [{'status': j.get('status'), 'error_code': j.get('error_code')} for j in (ws.get('jobs') or [])] if isinstance(ws, dict) else []
    res['fixture_calls'] = [f'{s}:{c}' for s, c in Fixture.calls]
    return res


def failure(args):
    out = {'phase': 'failure', 'started_at': now(), 'scenarios': [], 'assertions': {}}
    A = out['assertions']
    server = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    fx = f'http://127.0.0.1:{server.server_port}/v1'
    video, srt = media(args.media, 45, 'fail')
    def cfg(url, capability, mode, screening):
        return {'version': 1, 'connections': [{'id': 'winqa-fx', 'name': 'WinQA loopback fixture', 'provider': 'compatible', 'base_url': url, 'api_key': ''}],
                'analysis': {'connection_id': 'winqa-fx', 'model': 'winqa-model', 'capability': capability},
                'analysis_mode': mode, 'allow_visual_screening': screening, 'cover_enabled': False, 'allow_send_frame': screening}
    try:
        # 1) CHANGELOG #1: optional auto screening (vision call) gets HTTP 500 -> run continues on the subtitle route.
        Fixture.mode = 'screening500'
        s = run_scenario('screening-500-fallback', cfg(fx, 'multimodal', 'auto', True), video, srt, args.timeout)
        out['scenarios'].append(s)
        A['readiness_ready_with_loopback_model'] = isinstance(s['readiness'], dict) and s['readiness'].get('ready') is True
        A['screening_failed_with_500'] = 'image:500' in s['fixture_calls']
        A['fallback_generation_finished_ok'] = s['generation']['status'] in ('completed', 'partial')
        A['fallback_route_subtitle'] = s['generation']['route'] == 'subtitle'
        # 2) CHANGELOG #3: provider HTTP 500 on the subtitle route -> failed event carries stage / http_status / route.
        Fixture.mode = 'all500'
        s = run_scenario('analysis-http-500', cfg(fx, 'text', 'subtitle', False), video, srt, args.timeout)
        out['scenarios'].append(s)
        A['http500_generation_failed'] = s['generation']['status'] == 'failed'
        A['http500_failure_stage_present'] = bool(s['generation']['failure_stage'])
        A['http500_http_status_500'] = s['generation']['http_status'] == 500
        A['http500_route_subtitle'] = s['generation']['route'] == 'subtitle'
        # 3) Unreachable provider (closed local port): stage + route, no HTTP status.
        s = run_scenario('unreachable-provider', cfg('http://127.0.0.1:9/v1', 'text', 'subtitle', False), video, srt, args.timeout)
        out['scenarios'].append(s)
        A['unreachable_generation_failed'] = s['generation']['status'] == 'failed'
        A['unreachable_failure_stage_present'] = bool(s['generation']['failure_stage'])
        A['unreachable_no_http_status'] = s['generation']['http_status'] is None
    finally:
        out['restore_no_key'] = requests.put(base() + '/api/v1/settings/ai-models', json=NO_KEY, headers=W, timeout=20).status_code
        server.shutdown()
    time.sleep(3)
    code, items = projects_index()
    out['projects_after'] = items
    by_id = {p['id']: p for p in items}
    rows = []
    for s in out['scenarios']:
        p = by_id.get(s['project_id']) or {}
        rows.append({'scenario': s['scenario'], 'generation': s['generation']['status'], 'index_status': p.get('status')})
    out['index_vs_generation'] = rows
    A['project_index_terminal_not_processing'] = all(r['index_status'] not in (None, 'processing', 'pending') for r in rows)
    out['log_failure_lines'] = log_lines(r'(?i)(failure_stage|studio.*fail|Traceback)', 12)
    out['finished_at'] = now()
    out['ok'] = all(A.values())
    save('failure.json', out)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('phase', choices=['seed', 'check', 'failure'])
    ap.add_argument('--media', default=r'C:\winqa\repo\backend\assets\example')
    ap.add_argument('--expect-version', default='')
    ap.add_argument('--updater-url', default='https://github.com/zhouxiaoka/autoclip/releases/latest/download/latest.json')
    ap.add_argument('--label', default='candidate')
    ap.add_argument('--timeout', type=int, default=420)
    a = ap.parse_args()
    {'seed': seed, 'check': check, 'failure': failure}[a.phase](a)

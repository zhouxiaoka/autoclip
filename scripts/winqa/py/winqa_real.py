"""AutoClip Windows QA: REAL-model scenarios against the installed desktop backend (127.0.0.1).
Runs with the installed app's bundled Python. The API key is read ONLY from stdin (--key-stdin) in the
`model` phase, sent to the app's own settings API, and never printed or written: every saved JSON is
scrubbed of the key and of the app's masked form (first/last 3 chars).

  python winqa_real.py model --key-stdin [--base-url URL --model ID]   # save + connection test + #266 + readiness
  python winqa_real.py whisper                                          # readiness gate, install Whisper via app route, model download
  python winqa_real.py local  --seconds 150                             # local video (no SRT) -> Whisper -> clips -> exports
  python winqa_real.py link   --url https://www.bilibili.com/video/BV...  # B站 link import -> progress -> clips
  python winqa_real.py final                                            # project list: nothing stuck in processing
"""
import argparse, json, os, re, subprocess, sys, time
from pathlib import Path
import requests

for s in (sys.stdout, sys.stderr):
    try: s.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError): pass

OUT = Path(os.environ.get('WINQA_OUT', r'C:\winqa\out')) / 'real'
OUT.mkdir(parents=True, exist_ok=True)
RES = Path(os.environ['WINQA_RESOURCES']) if os.environ.get('WINQA_RESOURCES') else Path(sys.executable).resolve().parents[1]
DATA = Path(os.environ['APPDATA']) / 'AutoClip'
W = {'Origin': 'http://tauri.localhost'}
CONN_ID = 'winqa-real-model'
SECRETS = []


def now(): return time.strftime('%Y-%m-%dT%H:%M:%S%z')
def base(): return 'http://127.0.0.1:' + (DATA / 'backend.port').read_text().strip()
def get(p, **kw): return requests.get(base() + p, timeout=kw.pop('timeout', 30), **kw)
def put(p, **kw): return requests.put(base() + p, headers=W, timeout=kw.pop('timeout', 60), **kw)
def post(p, **kw): return requests.post(base() + p, headers=W, timeout=kw.pop('timeout', 60), **kw)


def body(r):
    try: return r.json()
    except ValueError: return r.text[:2000]


def scrub_text(t):
    for s in SECRETS:
        if s: t = t.replace(s, '***')
    t = re.sub(r'("api_key_masked"\s*:\s*")[^"]*(")', r'\1***\2', t)
    t = re.sub(r'(^|[^A-Za-z0-9])sk-[A-Za-z0-9_-]{6,}', r'\1sk-***', t)
    return re.sub(r'(?i)(bearer\s+)[A-Za-z0-9._-]{8,}', r'\1***', t)


def save(name, value):
    (OUT / name).write_text(scrub_text(json.dumps(value, ensure_ascii=False, indent=2)), encoding='utf-8')
    print('saved', OUT / name, flush=True)


def ffprobe(path):
    info = json.loads(subprocess.check_output([str(RES / 'ffmpeg' / 'ffprobe.exe'), '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)], encoding='utf-8'))
    v = next((s for s in info['streams'] if s['codec_type'] == 'video'), {})
    a = next((s for s in info['streams'] if s['codec_type'] == 'audio'), {})
    return {'duration_sec': round(float(info['format'].get('duration', 0)), 2), 'bytes': int(info['format'].get('size', 0)),
            'video': v.get('codec_name'), 'width': v.get('width'), 'height': v.get('height'), 'fps': v.get('avg_frame_rate'),
            'audio': a.get('codec_name'), 'sample_rate': a.get('sample_rate')}


LOG_TS = re.compile(r'(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)')


def log_since(t0, pattern):
    """Lines from the app logs at/after local time t0 (struct epoch) matching pattern."""
    since = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t0))
    rows = []
    for p in sorted((DATA / 'logs').glob('*.log')):
        try: lines = p.read_text(encoding='utf-8', errors='replace').splitlines()
        except OSError: continue
        for l in lines:
            m = LOG_TS.search(l)
            if m and m.group(1) >= since and re.search(pattern, l):
                rows.append(l)
    return rows


def spend(t0):
    usage = log_since(t0, r'LLM usage')
    # Provider requests logged by the app's HTTP client (any host; the loopback fixtures are not used here).
    http = log_since(t0, r'HTTP Request: POST https?://\S+/(chat/completions|embeddings|images)')
    toks = [int(x) for l in usage for x in re.findall(r'total_tokens=(\d+)', l)]
    return {'llm_usage_log_lines': len(usage), 'total_tokens_logged': sum(toks),
            'http_posts_to_endpoint_logged': len(http),
            'http_by_path': {k: sum(1 for l in http if k in l) for k in ('/chat/completions', '/embeddings', '/images')}}


def readiness():
    return body(get('/api/v1/studio/readiness'))


def submission_block(rd, has_subtitle):
    """Same rule as frontend/src/features/studio/importReadiness.ts submissionBlock()."""
    if not isinstance(rd, dict): return None
    c = rd['checks']
    if not c['analysis']['ok']: return 'analysis'
    if not c['transcription']['ok'] and not has_subtitle: return 'transcription'
    if not c['visual']['ok']: return 'visual'
    if not c['ffmpeg']['ok']: return 'ffmpeg'
    return None


def strip_conn(c):  # what the UI holds after GET: no api_key field at all
    return {k: v for k, v in c.items() if k not in ('has_key', 'api_key_masked', 'api_key')}


def ui_payload(s):
    s = {k: v for k, v in s.items() if k not in ('saved', 'migration_warnings')}
    s['connections'] = [strip_conn(c) for c in s['connections']]
    return s


def conn_state(s):
    c = next((c for c in s.get('connections', []) if c['id'] == CONN_ID), None) if isinstance(s, dict) else None
    return None if c is None else {'has_key': c.get('has_key'), 'masked': c.get('api_key_masked'), 'base_url': c.get('base_url'), 'provider': c.get('provider')}


# ---------------------------------------------------------------- A1-A3
def model(a):
    if not a.base_url or not a.model:
        sys.exit('model phase needs --base-url and --model')
    key = sys.stdin.readline().strip() if a.key_stdin else ''
    SECRETS.append(key)
    out = {'phase': 'model', 'started_at': now(), 'key_received': bool(key),
           'base_url': a.base_url, 'model': a.model, 'provider': a.provider, 'assertions': {}}
    A = out['assertions']
    t0 = time.time()
    conn = {'id': CONN_ID, 'name': 'WinQA real model', 'provider': a.provider, 'base_url': a.base_url, 'api_key': key}
    out['readiness_before'] = readiness()
    # 1) UI flow: test with the typed key, then save.
    r = post('/api/v1/settings/ai-models/test', json={'connection': conn, 'model': a.model}, timeout=90)
    out['test_before_save'] = {'http': r.status_code, 'body': body(r)}
    cfg = {'version': 1, 'connections': [conn], 'analysis': {'connection_id': CONN_ID, 'model': a.model, 'capability': 'auto'},
           'transcription': {'provider': 'whisper_local', 'model': 'base'},
           'analysis_mode': 'auto', 'allow_visual_screening': True, 'cover_enabled': False, 'allow_send_frame': False}
    r = put('/api/v1/settings/ai-models', json=cfg)
    out['save'] = {'http': r.status_code, 'body': body(r) if r.status_code != 200 else 'ok'}
    s1 = body(get('/api/v1/settings/ai-models'))
    st1 = conn_state(s1)
    out['after_save'] = {k: v for k, v in (st1 or {}).items() if k != 'masked'}
    out['after_save_analysis'] = s1.get('analysis') if isinstance(s1, dict) else None
    out['after_save_transcription'] = s1.get('transcription') if isinstance(s1, dict) else None
    no_key_conn = strip_conn(next(c for c in s1['connections'] if c['id'] == CONN_ID))
    r = post('/api/v1/settings/ai-models/test', json={'connection': no_key_conn, 'model': a.model}, timeout=90)
    out['test_after_save'] = {'http': r.status_code, 'body': body(r)}
    A['save_200'] = out['save']['http'] == 200
    A['saved_has_key'] = bool(st1 and st1['has_key'])
    A['connection_test_with_typed_key'] = out['test_before_save']['http'] == 200 and (out['test_before_save']['body'] or {}).get('success') is True
    A['connection_test_after_save_stored_key'] = out['test_after_save']['http'] == 200 and (out['test_after_save']['body'] or {}).get('success') is True
    # 2) #266: re-save exactly as the UI does with the key field left empty (field absent), then with explicit null.
    for label, mutate in (('field_absent', lambda c: c), ('explicit_null', lambda c: {**c, 'api_key': None})):
        payload = ui_payload(body(get('/api/v1/settings/ai-models')))
        payload['connections'] = [mutate(c) for c in payload['connections']]
        r = put('/api/v1/settings/ai-models', json=payload)
        s2 = body(get('/api/v1/settings/ai-models'))
        st2 = conn_state(s2)
        r2 = post('/api/v1/settings/ai-models/test', json={'connection': strip_conn(next(c for c in s2['connections'] if c['id'] == CONN_ID)), 'model': a.model}, timeout=90)
        out[f'resave_{label}'] = {'http': r.status_code, 'has_key': st2 and st2['has_key'], 'masked_unchanged': bool(st1 and st2 and st1['masked'] == st2['masked']),
                                  'test_http': r2.status_code, 'test_body': body(r2)}
        A[f'issue266_{label}_key_kept'] = r.status_code == 200 and bool(st2 and st2['has_key']) and out[f'resave_{label}']['masked_unchanged']
        A[f'issue266_{label}_test_passes'] = r2.status_code == 200 and (body(r2) or {}).get('success') is True
    # 3) readiness again
    rd = readiness()
    out['readiness_after'] = rd
    A['readiness_analysis_ok'] = isinstance(rd, dict) and rd['checks']['analysis']['ok'] is True and rd['checks']['analysis']['code'] == 'configured'
    out['frontend_block_without_srt'] = submission_block(rd, False)
    out['spend'] = spend(t0)
    out['finished_at'] = now()
    out['ok'] = all(A.values())
    save('model.json', out)
    return 0 if out['ok'] else 1


# ---------------------------------------------------------------- whisper
def whisper(a):
    out = {'phase': 'whisper', 'started_at': now(), 'assertions': {}}
    rd = readiness()
    out['readiness_before'] = rd
    out['frontend_block_before_install_no_srt'] = submission_block(rd, False)
    out['frontend_block_before_install_with_srt'] = submission_block(rd, True)
    out['runtime_status_before'] = body(get('/api/v1/whisper/runtime-status'))
    t0 = time.monotonic()
    r = post('/api/v1/whisper/install')
    out['install_post'] = {'http': r.status_code, 'body': body(r)}
    st, samples = {}, []
    while time.monotonic() - t0 < a.timeout:
        st = body(get('/api/v1/whisper/runtime-status'))
        if isinstance(st, dict):
            samples.append({'t': round(time.monotonic() - t0), 'status': st.get('status'), 'progress': st.get('progress'), 'message': st.get('message')})
            if st.get('status') in ('installed', 'error'): break
        time.sleep(5)
    out['install_seconds'] = round(time.monotonic() - t0, 1)
    out['install_samples'] = samples[::max(1, len(samples) // 15)] + samples[-1:]
    out['runtime_status_after'] = {k: v for k, v in st.items() if k != 'log_tail'} if isinstance(st, dict) else st
    if isinstance(st, dict) and st.get('status') == 'error':
        out['install_log_tail'] = str(st.get('log_tail'))[-1500:]
    # The runtime alone is not "ready": readiness reports whisper_model_missing until the model is on
    # disk (RC156 #5). Record that state, download the model, and only then check readiness (Win QA #17).
    rd_runtime = readiness()
    out['readiness_after_install'] = rd_runtime
    out['transcription_after_install'] = (rd_runtime.get('checks') or {}).get('transcription') if isinstance(rd_runtime, dict) else None
    out['models_before'] = body(get('/api/v1/whisper-models'))
    t1 = time.monotonic()
    try:
        r = post('/api/v1/whisper-models/download', json={'model': a.whisper_model}, timeout=120)
        out['model_download_post'] = {'http': r.status_code, 'body': body(r)}
    except requests.RequestException as e:
        out['model_download_post'] = {'error': type(e).__name__}
    ms = {}
    while time.monotonic() - t1 < a.timeout:  # the route only STARTS a background snapshot_download; poll the real state
        ms = body(get(f'/api/v1/whisper-models/{a.whisper_model}/status'))
        if not isinstance(ms, dict) or ms.get('status') in ('downloaded', 'error'): break
        time.sleep(5)
    out['model_download'] = {'status': ms.get('status') if isinstance(ms, dict) else ms, 'error': (ms.get('errorMessage') or '')[:300] if isinstance(ms, dict) else None,
                             'seconds': round(time.monotonic() - t1, 1), 'hf_endpoint_env_of_probe': os.environ.get('HF_ENDPOINT')}
    rd2 = readiness()
    out['readiness_after'] = rd2
    out['frontend_block_after_install_no_srt'] = submission_block(rd2, False)
    A = out['assertions']
    if (out['runtime_status_before'] or {}).get('status') != 'installed':  # only meaningful on the first install
        A['import_blocked_before_whisper_without_srt'] = out['frontend_block_before_install_no_srt'] == 'transcription'
    A['whisper_installed_via_app_route'] = isinstance(st, dict) and st.get('status') == 'installed'
    A['readiness_transcription_ok_after'] = isinstance(rd2, dict) and rd2['checks']['transcription']['ok'] is True
    A['import_unblocked_after_install'] = out['frontend_block_after_install_no_srt'] is None
    A['whisper_model_downloaded'] = out['model_download']['status'] == 'downloaded'
    out['finished_at'] = now()
    out['ok'] = all(A.values())
    save(f'{a.label}.json', out)
    return 0 if out['ok'] else 1


# ---------------------------------------------------------------- generation helpers
def watch(pid, timeout, t0):
    samples, last, ws = [], None, {}
    while time.monotonic() - t0 < timeout:
        try: ws = body(get(f'/api/v1/studio/{pid}', timeout=30))
        except requests.RequestException: time.sleep(5); continue
        if not isinstance(ws, dict): time.sleep(5); continue
        an, g = ws.get('analysis') or {}, ws.get('generation') or {}
        sig = (an.get('status'), an.get('phase'), an.get('progress'), an.get('message'), g.get('status'), g.get('progress'), g.get('stage'),
               len(ws.get('drafts') or []), sum(1 for j in ws.get('jobs') or [] if j.get('status') == 'completed'))
        if sig != last:
            samples.append({'t': round(time.monotonic() - t0), 'analysis': sig[:4], 'generation': sig[4:7], 'drafts': sig[7], 'jobs_done': sig[8]})
            last = sig
        if g.get('status') in ('completed', 'partial', 'failed') or an.get('status') == 'failed':
            break
        time.sleep(4)
    return ws, samples


def collect(pid, ws, tag, out):
    g, an = ws.get('generation') or {}, ws.get('analysis') or {}
    out['generation'] = {k: g.get(k) for k in ('status', 'error_code', 'failure_stage', 'http_status', 'route', 'completed_variant_count')}
    out['generation_error'] = scrub_text(str(g.get('error') or ''))[:400]
    out['analysis'] = {k: an.get(k) for k in ('status', 'phase', 'error_code', 'outcome', 'message')}
    out['plan'] = {k: (ws.get('plan') or {}).get(k) for k in ('mode', 'recommended_analysis', 'confirmed_analysis')}
    def scene_sum(d):
        try: return round(sum(float(x['end']) - float(x['start']) for x in d.get('scenes') or []), 2)
        except (KeyError, TypeError, ValueError): return None
    out['drafts'] = [{'id': d.get('id'), 'title': d.get('title'), 'scenes': len(d.get('scenes') or []), 'scene_seconds': scene_sum(d)}
                     for d in ws.get('drafts') or []]
    out['output_variants'] = [{'id': v.get('id'), 'draft_id': v.get('draft_id'), 'platform': v.get('platform'), 'status': v.get('status'), 'render_job_id': v.get('render_job_id')}
                              for v in ws.get('output_variants') or []]
    exports = []
    for j in ws.get('jobs') or []:
        if j.get('status') != 'completed' or not j.get('job_id'): continue
        hits = list(DATA.glob(f'**/{pid}/output/studio/{j["job_id"]}.mp4'))
        e = {'job_id': j['job_id'], 'draft_id': j.get('draft_id'), 'path': str(hits[0]).replace(os.environ.get('USERNAME', '~'), '<user>') if hits else None}
        if hits: e['ffprobe'] = ffprobe(hits[0])
        exports.append(e)
    out['exports'] = exports
    out['clip_count'] = len(exports)
    out['clip_durations_sec'] = [e['ffprobe']['duration_sec'] for e in exports if e.get('ffprobe')]
    if exports and exports[0].get('path'):
        j = exports[0]['job_id']
        r = get(f'/api/v1/studio/{pid}/exports/{j}/video?download=true', timeout=300, stream=True)
        out['export_route_http'] = r.status_code
        if r.status_code == 200:
            dst = OUT / f'{tag}-clip1.mp4'
            with dst.open('wb') as f:
                for chunk in r.iter_content(1 << 20): f.write(chunk)
            out['evidence_clip'] = dst.name
            thumb = OUT / f'{tag}-clip1-thumb.jpg'
            subprocess.run([str(RES / 'ffmpeg' / 'ffmpeg.exe'), '-v', 'error', '-y', '-ss', '3', '-i', str(dst), '-frames:v', '1', '-vf', 'scale=480:-2', str(thumb)], timeout=60)
            out['evidence_thumb'] = thumb.name if thumb.exists() else None
        v = next((v for v in ws.get('output_variants') or [] if v.get('id')), None)
        if v:
            r = get(f'/api/v1/studio/{pid}/output-variants/{v["id"]}/cover', timeout=60)
            out['app_cover_http'] = r.status_code
            if r.status_code == 200 and r.headers.get('content-type', '').startswith('image/'):
                ext = '.png' if 'png' in r.headers['content-type'] else '.jpg'
                (OUT / f'{tag}-app-cover{ext}').write_bytes(r.content)
                out['evidence_app_cover'] = f'{tag}-app-cover{ext}'
    return out


def run_import(a, tag, files=None, data=None):
    t0w, t0 = time.time(), time.monotonic()
    out = {'phase': tag, 'started_at': now(), 'assertions': {}}
    rd = readiness()
    out['readiness'] = rd
    out['frontend_block'] = submission_block(rd, False)
    d = {'name': f'WinQA {tag}', 'auto_start': 'true', 'platforms': 'douyin', **(data or {})}
    r = requests.post(base() + '/api/v1/studio/import', data=d, files=files, headers=W, timeout=600)
    out['import_http'] = r.status_code
    if r.status_code != 200:
        out['import_body'] = body(r)
        out['ok'] = False
        save(f'{tag}.json', out)
        return out, None
    pid = r.json()['project_id']
    out['project_id'] = pid
    ws, samples = watch(pid, a.timeout, t0)
    out['seconds'] = round(time.monotonic() - t0, 1)
    out['progress_samples'] = samples
    collect(pid, ws, tag, out)
    out['spend'] = spend(t0w)
    out['transcription_log'] = [scrub_text(l)[-220:] for l in log_since(t0w, r'(?i)(faster-whisper|whisper|转写|字幕生成)')][-8:]
    out['error_log'] = [scrub_text(l)[-300:] for l in log_since(t0w, r'(?i)(ERROR|Traceback|失败)')][-10:]
    return out, pid


def local(a):
    src = Path(a.media) / 'source.mp4'
    work = OUT / 'media'; work.mkdir(exist_ok=True)
    video = work / f'公开访谈 {a.seconds}秒（无字幕）.mp4'
    if not video.exists():
        subprocess.run([str(RES / 'ffmpeg' / 'ffmpeg.exe'), '-v', 'error', '-y', '-i', str(src), '-t', str(a.seconds), '-c', 'copy', str(video)], check=True, timeout=120)
    with video.open('rb') as v:
        out, pid = run_import(a, 'local', files={'video': (video.name, v, 'video/mp4')})
    out['input'] = {'name': video.name, **ffprobe(video), 'subtitle': None}
    A = out['assertions']
    if pid:
        A['generation_completed'] = out['generation']['status'] in ('completed', 'partial')
        A['has_clips'] = out['clip_count'] > 0
        A['clips_h264_aac'] = all(e.get('ffprobe', {}).get('video') == 'h264' and e['ffprobe'].get('audio') == 'aac' for e in out['exports']) and bool(out['exports'])
        A['transcribed_with_local_whisper'] = any('faster-whisper' in l for l in out['transcription_log'])
        A['evidence_clip_pulled'] = bool(out.get('evidence_clip'))
    out['finished_at'] = now()
    out['ok'] = bool(A) and all(A.values())
    save('local.json', out)
    return 0 if out['ok'] else 1


def link(a):
    out, pid = run_import(a, 'link', data={'url': a.url})
    out['url'] = a.url
    A = out['assertions']
    if pid:
        A['progress_moved'] = len(out['progress_samples']) >= 3
        A['generation_completed'] = out['generation']['status'] in ('completed', 'partial')
        A['has_clips'] = out['clip_count'] > 0
    out['finished_at'] = now()
    out['ok'] = bool(A) and all(A.values())
    save('link.json', out)
    return 0 if out['ok'] else 1


def final(a):
    r = get('/api/v1/projects/')
    data = body(r)
    items = (data.get('items') or data.get('projects') or data.get('data') or []) if isinstance(data, dict) else data
    rows = [{'id': p.get('id'), 'name': p.get('name'), 'status': p.get('status')} for p in items if isinstance(p, dict)]
    stuck = [p for p in rows if p['status'] == 'processing']  # 'pending' = never started (e.g. the upgrade seed project), not stuck
    out = {'phase': 'final', 'at': now(), 'http': r.status_code, 'projects': rows, 'stuck_winqa_projects': stuck,
           'assertions': {'no_winqa_project_stuck_processing': not stuck and r.status_code == 200}}
    out['ok'] = all(out['assertions'].values())
    save('final.json', out)
    return 0 if out['ok'] else 1


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('phase', choices=['model', 'whisper', 'local', 'link', 'final'])
    ap.add_argument('--key-stdin', action='store_true')
    # Model endpoint/model/provider are passed by run_winqa.sh (--model-base-url / --model / --model-provider);
    # there is no built-in endpoint so account-specific URLs never live in the repository.
    ap.add_argument('--base-url', default='')
    ap.add_argument('--model', default='')
    ap.add_argument('--provider', default='dashscope')
    ap.add_argument('--whisper-model', default='base')
    ap.add_argument('--media', default=r'C:\winqa\repo\backend\assets\example')
    ap.add_argument('--seconds', type=int, default=150)
    ap.add_argument('--url', default='')
    ap.add_argument('--label', default='whisper')
    ap.add_argument('--timeout', type=int, default=1800)
    a = ap.parse_args()
    sys.exit({'model': model, 'whisper': whisper, 'local': local, 'link': link, 'final': final}[a.phase](a))

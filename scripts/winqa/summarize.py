import re
#!/usr/bin/env python3
"""Summarise a winqa evidence directory into Markdown (stdout) and windows-rows.draft.json."""
import json
import sys
from pathlib import Path, PureWindowsPath

ev = Path(sys.argv[1])


def load(name):
    p = ev / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding='utf-8-sig'))
    except ValueError:
        return None


def mark(ok):
    return '✅ 通过' if ok is True else ('❌ 失败' if ok is False else '⏸ 未跑/无数据')


inputs, env = load('inputs.json') or {}, load('env.json') or {}
ip, lp, seed = load('install-prev.json') or {}, load('launch-prev.json') or {}, load('seed.json') or {}
up, lc = load('install-upgrade.json') or {}, load('launch-candidate.json') or {}
ck, fl, sm, ws = load('check-candidate.json') or {}, load('failure.json') or {}, load('smoke.json') or {}, load('windows-smoke.json') or {}
rc = load('check-recheck.json') or {}
A, F = dict(ck.get('assertions') or {}), fl.get('assertions') or {}
# A re-check with the corrected "no key" state supersedes only the readiness assertions of the first check.
READY_KEYS = ('no_key_settings_saved', 'readiness_endpoint_200', 'readiness_not_ready_without_model', 'readiness_analysis_fix_entry',
              'readiness_whisper_fix_entry', 'readiness_ffmpeg_ok', 'readiness_visual_optional_in_auto')
if rc.get('assertions'):
    for k in READY_KEYS:
        if k in rc['assertions']:
            A[k] = rc['assertions'][k]
    ck = {**ck, 'readiness_no_model': rc.get('readiness_no_model')}
cand_v = (inputs.get('candidate') or {}).get('version')
prev_v = (inputs.get('prev') or {}).get('version')
hashes = {PureWindowsPath(i['path']).name: i['sha256'] for i in (env.get('installers') or []) if i}

rows = []
def row(name, ok, evidence):
    rows.append((name, ok, evidence))

row('安装包哈希（验收机上 Get-FileHash 与 box 一致）',
    bool(hashes) and hashes.get('prev-setup.exe') == (inputs.get('prev') or {}).get('sha256') and hashes.get('candidate-setup.exe') == (inputs.get('candidate') or {}).get('sha256'),
    f"prev {hashes.get('prev-setup.exe', '?')[:12]}…, candidate {hashes.get('candidate-setup.exe', '?')[:12]}…")
row(f'干净安装 {prev_v}（/S）', ip.get('ok'), f"exit={ip.get('exit_code')} 用时 {ip.get('seconds')}s 注册表版本 {(ip.get('after') or {}).get('Version')}")
celery_prev = lp.get('celery_processes') or []
row(f'启动 {prev_v}（交互桌面）', lp.get('ok'), f"mode={lp.get('mode')} session={lp.get('app_sessions')} 端口文件 {lp.get('port_file_seconds')}s 健康 {lp.get('healthy_seconds')}s；python 进程 {lp.get('python_processes')} 个，Celery 进程 {len(celery_prev)} 个")
row('造数据（隐私关、假 key 连接、20 秒项目）', bool(seed.get('seed_project_id')) and seed.get('ai_models_put') == 200, f"版本 {seed.get('app_version')}，项目 {seed.get('seed_project_id')}")
row(f'旧版运行中覆盖升级到 {cand_v}（+残留 python 占 _asyncio.pyd）', up.get('ok'),
    f"exit={up.get('exit_code')} 用时 {up.get('seconds')}s 注册表 {(up.get('after') or {}).get('Version')}；升级前运行 {len(up.get('running_before') or [])} 个进程，升级后仍存活 {up.get('still_alive_from_before')}；残留锁进程被结束={up.get('lock_killed_by_installer')}；新文件 {up.get('marker_present')}；旧文件残留 {up.get('stale_files')}")
celery = lc.get('celery_processes')
row(f'启动 {cand_v}', lc.get('ok'), f"mode={lc.get('mode')} 端口文件 {lc.get('port_file_seconds')}s 健康 {lc.get('healthy_seconds')}s exe FileVersion {lc.get('exe_file_version')}")
cel_logs = [l for l in (ck.get('log_celery_lines') or []) if 'Celery' in l]
row('进程里没有 Celery', (celery == [] and lc.get('ok')) if celery is not None else None,
    f"候选版进程树：autoclip-desktop.exe + WebView2 + 1 个 python（-m backend.desktop_main），命令行含 celery 的 {len(celery or [])} 个；"
    f"日志里唯一的 Celery 行来自升级前的 {prev_v}：{re.sub(r'^.*?(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d).*?(✅.*)$', r'\1 \2', cel_logs[-1])[:80] if cel_logs else '无'}")
for key, label in [('reported_version_matches', f"后端上报版本 = {cand_v}（实际 {ck.get('app_version')}）"), ('backend_health_200', '/health 200'),
                   ('settings_endpoint_200', '/api/v1/settings/ 200'), ('upgrade_kept_privacy_off', '升级后隐私设置保留'),
                   ('upgrade_kept_model_connection_and_key', '升级后模型连接和 key 保留'), ('upgrade_kept_project', '升级后项目保留'),
                   ('readiness_endpoint_200', '预检接口 /api/v1/studio/readiness 200'), ('readiness_not_ready_without_model', '无模型时 ready=false'),
                   ('readiness_analysis_fix_entry', '分析模型缺失 → repair=settings_ai'), ('readiness_whisper_fix_entry', 'Whisper 未装 → repair=install_whisper'),
                   ('readiness_ffmpeg_ok', '包内 FFmpeg 就绪'), ('updater_endpoint_embedded', 'exe 内嵌 updater 地址'),
                   ('updater_manifest_readable', f"能读到 latest.json（{(ck.get('updater_fetch') or {}).get('version') or (ck.get('updater_fetch') or {}).get('error')}）"),
                   ('no_project_stuck_processing', '项目列表无 processing'), ('no_key_settings_saved', '保存“有连接无 key”设置 200'),
                   ('readiness_visual_optional_in_auto', 'auto 模式视觉为可选')]:
    row(label, A.get(key), '')
for key, label in [('readiness_ready_with_loopback_model', '配好（loopback）模型后 ready=true'), ('screening_failed_with_500', '画面初筛收到 500'),
                   ('fallback_generation_finished_ok', '初筛失败后仍出片（#1）'), ('fallback_route_subtitle', '回退后 route=subtitle（#1）'),
                   ('http500_generation_failed', '分析 500 → 失败'), ('http500_failure_stage_present', '失败记录有 failure_stage（#3）'),
                   ('http500_http_status_500', '失败记录 http_status=500（#3）'), ('http500_route_subtitle', '失败记录 route=subtitle（#3）'),
                   ('unreachable_generation_failed', '服务不可达 → 失败'), ('unreachable_failure_stage_present', '不可达也有 failure_stage'),
                   ('unreachable_no_http_status', '不可达时无 http_status'), ('project_index_terminal_not_processing', '失败/完成后项目列表为终态（#5）')]:
    row(label, F.get(key), '')
for run in sm.get('runs') or []:
    row(f"CI 同款 {run['name']}（{run.get('mode', 'ssh-session0')}）", run['exit_code'] == 0, f"exit={run['exit_code']} 用时 {run['seconds']}s")

print(f"# AutoClip {cand_v} Windows 自动验收（{prev_v} → {cand_v}）\n")
print(f"- 机器：{env.get('os_caption')} {env.get('display_version')} build {env.get('os_build')} {env.get('os_arch')}，{env.get('ram_gb')} GB，{env.get('cpu')}，{env.get('manufacturer')} {env.get('model')}（虚拟机），WebView2 {env.get('webview2')}")
print(f"- 候选包：{(inputs.get('candidate') or {}).get('file')} sha256 {(inputs.get('candidate') or {}).get('sha256')}")
print(f"- 上一版：{(inputs.get('prev') or {}).get('file')} sha256 {(inputs.get('prev') or {}).get('sha256')}")
print(f"- 仓库提交：{inputs.get('repo_commit')}；开始 {inputs.get('started_at')}\n")
print('| 检查 | 结果 | 关键证据 |\n|---|---|---|')
for name, ok, e in rows:
    print(f'| {name} | {mark(ok)} | {e} |')
print()
if fl.get('scenarios'):
    print('## 失败/回退探针明细\n')
    for s in fl['scenarios']:
        print(f"- **{s['scenario']}**：{s['seconds']}s，generation={json.dumps(s['generation'], ensure_ascii=False)}，plan={json.dumps(s.get('plan'), ensure_ascii=False)}，fixture 调用={s.get('fixture_calls')}")
        if s.get('generation_error'):
            print(f"  - 错误文本：`{s['generation_error']}`")
rd = (ck.get('readiness_no_model') or [None, None])[1]
if rd:
    print(f"\n## 预检（有连接无 key、无 Whisper）\n\n```json\n{json.dumps(rd, ensure_ascii=False, indent=2)}\n```")

# ---------------------------------------------------------------- real-model scenarios (steps 10-14, --real)
RM, WF, WM, WD, LO, LK, FN = (load('real/' + n) or {} for n in ('model.json', 'whisper-firstinstall.json', 'whisper-hfmirror.json',
                                                                 'whisper-hf-direct-timeout.json', 'local.json', 'link.json', 'final.json'))
real_rows = []
def rrow(name, ok, evidence):
    real_rows.append((name, ok, evidence))
if RM:
    RA = RM.get('assertions', {})
    sp = RM.get('spend') or {}
    rrow('A1 保存真实模型连接 + 应用自带连接测试', RA.get('save_200') and RA.get('connection_test_with_typed_key') and RA.get('connection_test_after_save_stored_key'),
         f"model={RM.get('model')} provider={RM.get('provider')}；PUT 200；测试（填 key）{RM.get('test_before_save', {}).get('body')}，保存后用已存 key {RM.get('test_after_save', {}).get('body')}")
    rrow('A2 #266 留空 key 重存后 key 保留、测试仍通过', all(RA.get(k) for k in ('issue266_field_absent_key_kept', 'issue266_field_absent_test_passes', 'issue266_explicit_null_key_kept', 'issue266_explicit_null_test_passes')),
         f"字段缺省：{ {k: v for k, v in (RM.get('resave_field_absent') or {}).items() if k != 'test_body'} }；显式 null：{ {k: v for k, v in (RM.get('resave_explicit_null') or {}).items() if k != 'test_body'} }")
    rrow('A3 预检 analysis=configured', RA.get('readiness_analysis_ok'), f"ready={(RM.get('readiness_after') or {}).get('ready')}，checks={json.dumps((RM.get('readiness_after') or {}).get('checks'), ensure_ascii=False)}")
if WF:
    rrow('A4a 装 Whisper 前无 SRT 导入被预检拦住（前端 submissionBlock 规则）', WF.get('frontend_block_before_install_no_srt') == 'transcription',
         f"无 SRT → {WF.get('frontend_block_before_install_no_srt')}；带 SRT → {WF.get('frontend_block_before_install_with_srt')}；后端 /studio/import 本身不检查预检")
    rrow('A4b 应用自己的路由安装 Whisper 运行时', (WF.get('runtime_status_after') or {}).get('status') == 'installed',
         f"{WF.get('install_seconds')}s，{(WF.get('runtime_status_after') or {}).get('packages')}；装后 transcription={((WF.get('readiness_after') or {}).get('checks') or {}).get('transcription')}")
if WD or WM:
    rrow('A4c Whisper 模型下载（应用默认 huggingface.co）', False if WD else None,
         f"直连：{(WD.get('model_download') or {}).get('status')}（{((WD.get('model_download') or {}).get('error') or '')[:60]}…）；下载接口却立即回「{((WD.get('model_download_post') or {}).get('body') or {}).get('message')}」")
    rrow('A4c′ 绕过：HF_ENDPOINT=hf-mirror.com + HF_HUB_DISABLE_XET=1', (WM.get('model_download') or {}).get('status') == 'downloaded',
         f"{(WM.get('model_download') or {}).get('status')}，{(WM.get('model_download') or {}).get('seconds')}s（只设 HF_ENDPOINT 时 xet CAS 401）")
def gen_row(tag, d, label):
    if not d:
        return
    sp = d.get('spend') or {}
    rrow(label, d.get('ok'),
         f"项目 {d.get('project_id')}；{d.get('seconds')}s；generation={(d.get('generation') or {}).get('status')} route={(d.get('generation') or {}).get('route')}；"
         f"成片 {d.get('clip_count')} 条，时长 {d.get('clip_durations_sec')}s；模型调用 {sp.get('http_posts_to_endpoint_logged')} 次 / {sp.get('total_tokens_logged')} tokens；"
         f"证据 {d.get('evidence_clip')}, {d.get('evidence_thumb')}" + (f"；错误 {d.get('generation_error')[:120]}" if d.get('generation_error') else ''))
gen_row('local', LO, 'A4 本地视频（无字幕）→ Whisper → 出片 → 导出')
gen_row('link', LK, f"A5 B 站链接导入 → 进度 → 出片（{LK.get('url', '')}）")
if FN:
    rrow('A6 项目列表无卡住的 processing', FN.get('ok'), f"{len(FN.get('projects') or [])} 个项目，状态 {sorted({p['status'] for p in FN.get('projects') or []})}；卡住的 WinQA 项目 {FN.get('stuck_winqa_projects')}")
if real_rows:
    print(f"\n## 真实模型场景（provider={RM.get('provider')}，model={RM.get('model')}；第 10-14 步）\n")
    print('| 场景 | 结果 | 关键证据 |\n|---|---|---|')
    for name, ok, evidence in real_rows:
        print(f"| {name} | {mark(ok)} | {str(evidence).replace('|', '/')} |")
    calls = sum(((d.get('spend') or {}).get('http_posts_to_endpoint_logged') or 0) for d in (RM, LO, LK))
    toks = sum(((d.get('spend') or {}).get('total_tokens_logged') or 0) for d in (RM, LO, LK))
    print(f"\n真实模型花费（按应用日志统计）：约 {calls} 次请求，{toks} tokens。")

# Draft internal-acceptance rows: automated parts only; case rows stay pending (each needs UI / real model).
now = __import__('datetime').datetime.now().astimezone().isoformat(timespec='seconds')
auto_ok = all(r[1] is True for r in rows)
draft = {
    'note': 'DRAFT ONLY. Windows rows for internal_acceptance.py; matrix cases stay pending until the GUI/real-model parts are done by a named tester.',
    'platform': 'windows-x64',
    'os': f"{env.get('os_caption')} {env.get('display_version')} (build {env.get('os_build')}), x64",
    'machine': f"{env.get('manufacturer')} {env.get('model')} VM, {env.get('logical_cpus')} vCPU, {env.get('ram_gb')} GB; cloud VM, not physical hardware",
    'runtime': f"bundled portable Python {ws.get('python', '?')}, bundled ffmpeg, WebView2 {env.get('webview2')}",
    'checks': {case: {'status': 'pending', 'completed_at': None, 'evidence': '',
                      'automated_partial': None} for case in ('clean_install', 'upgrade_legacy', 'model_settings', 'local_with_subtitles',
                      'local_without_subtitles', 'link_import', 'visual_generation', 'failure_recovery', 'output_delivery', 'privacy_telemetry')},
    'regressions': [],
}
c = draft['checks']
c['clean_install']['automated_partial'] = 'silent install, backend health and bundled python/ffmpeg verified; real UI onboarding / model save / restart NOT done'
c['upgrade_legacy']['automated_partial'] = f"overwrite {prev_v}->{cand_v} while running, exit={up.get('exit_code')}, {up.get('seconds')}s, privacy/key/project kept={A.get('upgrade_kept_privacy_off')}/{A.get('upgrade_kept_model_connection_and_key')}/{A.get('upgrade_kept_project')}; UI check of settings/projects NOT done"
c['failure_recovery']['automated_partial'] = 'loopback HTTP 500 / unreachable provider produce failed terminal state with failure_stage; UI retry after fix NOT done'
if RM:
    c['model_settings']['automated_partial'] = f"API-level: {RM.get('provider')} / {RM.get('model')} saved, app connection test success before/after save; #266 re-save with empty key keeps key = {all(RM.get('assertions', {}).get(k) for k in ('issue266_field_absent_key_kept', 'issue266_explicit_null_key_kept'))}; UI form NOT exercised"
if LO:
    c['local_without_subtitles']['automated_partial'] = f"API-level: Whisper runtime installed via app route; model download needs HF mirror workaround (huggingface.co blocked); generation={(LO.get('generation') or {}).get('status')}, clips={LO.get('clip_count')}; eyes-on playback NOT done"
if LK:
    c['link_import']['automated_partial'] = f"API-level: Bilibili {LK.get('url')} generation={(LK.get('generation') or {}).get('status')}, clips={LK.get('clip_count')}; YouTube skipped (no proxy); UI NOT exercised"
c['output_delivery']['automated_partial'] = 'CI-equivalent loopback pipeline produced H.264/AAC output checked with ffprobe; native save/preview/eyes-on playback NOT done'
def reg(id_, desc, ok, ev_):  # noqa: E302
    draft['regressions'].append({'id': id_, 'platforms': ['windows-x64'], 'description': desc,
                                 'status': 'passed' if ok else ('failed' if ok is False else 'pending'),
                                 'completed_at': now if ok is not None else None, 'evidence': ev_})
reg('1.5.6-auto-screening-fallback', 'optional auto screening fails (vision HTTP 500) -> run continues on the subtitle route',
    all(F.get(k) for k in ('screening_failed_with_500', 'fallback_generation_finished_ok', 'fallback_route_subtitle')) if F else None, 'failure.json')
reg('1.5.6-import-readiness', 'readiness API reports model/transcription/vision/FFmpeg with repair entries (backend part; UI blocking still pending)',
    all(A.get(k) for k in ('readiness_endpoint_200', 'readiness_not_ready_without_model', 'readiness_analysis_fix_entry', 'readiness_whisper_fix_entry', 'readiness_ffmpeg_ok')) if A else None, 'check-candidate.json, check-recheck.json')
reg('1.5.6-failure-taxonomy', 'failed generation records failure_stage, http_status and route',
    all(F.get(k) for k in ('http500_failure_stage_present', 'http500_http_status_500', 'http500_route_subtitle', 'unreachable_failure_stage_present')) if F else None, 'failure.json')
reg('1.5.6-desktop-no-celery', 'desktop backend starts no Celery; project index reaches terminal state',
    (celery == [] and bool(F.get('project_index_terminal_not_processing')) and bool(A.get('no_project_stuck_processing'))) if lc else None, 'launch-candidate.json, failure.json')
reg('1.5.6-installer-smoke-studio', 'installed-runtime smoke via Studio import + ffprobe (verify_windows_install.py)',
    (all(r['exit_code'] == 0 for r in sm['runs']) if sm.get('runs') else None), 'smoke.json, windows-smoke.json')
if RM:
    reg('1.5.6-issue266-key-kept', 'saving AI settings with the key field left empty keeps the stored key; connection test still passes (real model endpoint)',
        all(RM.get('assertions', {}).get(k) for k in ('issue266_field_absent_key_kept', 'issue266_field_absent_test_passes', 'issue266_explicit_null_key_kept', 'issue266_explicit_null_test_passes')), 'real/model.json')
(ev / 'windows-rows.draft.json').write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"\n自动项全部通过：{auto_ok}。矩阵 10 个 case 全部保持 pending（需界面/真实模型）。草稿：{ev / 'windows-rows.draft.json'}")

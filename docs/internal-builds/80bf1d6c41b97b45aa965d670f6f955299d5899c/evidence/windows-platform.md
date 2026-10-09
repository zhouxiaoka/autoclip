# Windows x64 — AutoClip 1.5.6 internal acceptance

- Package: Desktop Build run 37937536440 @ 80bf1d6c41b97b45aa965d670f6f955299d5899c
- Installer SHA-256: aa03dd906296bb964ce7d4adc0bec6504de938f92d592a1ba6b9ca5a41467143
- Environment: Windows Server 2025 Datacenter 24H2 (build 26100) x64, Tencent Cloud CVM 2vCPU/8GB
- Runtime: bundled portable Python 3.13.13, bundled FFmpeg, WebView2

## Matrix (automated / harness)

- clean_install: silent and interactive install; backend /health 1.5.6; bundled python+ffmpeg present; desktop window smoke passed on tag package (tag smoke 2026-10-09T23:53+08).
- upgrade_legacy: 1.5.5→1.5.6 overwrite while running (FINAL2 ae67a70f) kept privacy/key/projects; tag package 80bf1d6c interactive upgrade 179.7s, exe 295dd7bd…, stale=none, python+ffmpeg ok.
- model_settings: DashScope qwen3.8-flash saved; connection test ok; empty-key keep (#266) verified.
- local_with_subtitles: covered on earlier RC candidates with SRT; reconfirmed via Studio smoke path producing ffprobe-valid H.264 output on tag package.
- local_without_subtitles: Whisper runtime + hf-mirror model download; 150s local video completed with clips; 35min long video completed after thinking-off.
- link_import: Bilibili public short BV1yf8XzmEV8 exercised; site 412 classified with Chinese source_blocked guidance (#297).
- visual_generation: no-audio source took visual route; source_no_audio messaging verified (#305/#19). Full two-stage vision optional path covered on earlier candidates.
- failure_recovery: provider HTTP 500 records http_status; mid-delete aborts render; LLM/render kill9 → service_restarted with retry (#301/#311).
- output_delivery: exported clips decode (ffprobe); Chinese paths exercised in harness; ZIP/export CRC checks on earlier candidates.
- privacy_telemetry: analytics OFF → zero PostHog requests; Settings has no「实验功能」in production bundle (#308). Analytics ON usage events accepted by Charlie (#27).

Local raw evidence retained under /workspace/rc156/final2 and /workspace/rc156/tag (not published).

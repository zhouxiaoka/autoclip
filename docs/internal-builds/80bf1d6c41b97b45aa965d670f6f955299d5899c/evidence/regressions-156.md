# AutoClip 1.5.6 CHANGELOG regression evidence (sanitized)

Source commit 80bf1d6c41b97b45aa965d670f6f955299d5899c / Desktop Build 37937536440.
Product code identical to ae67a70f except CHANGELOG (#308) credit line. Full dual-platform re-verification on ae67a70f (FINAL2) plus tag smoke on 80bf1d6c.

| ID | Result | Notes |
|---|---|---|
| auto-screening-fallback | passed | subtitle fallback when auto visual precheck fails |
| import-readiness | passed | missing model/runtime/FFmpeg blocked with action |
| failure-taxonomy | passed | failure_stage + http_status + route recorded |
| installer-smoke-studio | passed | Studio one-click + ffprobe on CI smoke + tag smoke |
| desktop-no-celery | passed | no Celery; studio.json drives list status |
| remove-legacy-import | passed | unused import page / Celery trial files removed (source) |
| #297 http/health/source_blocked | passed | http_status kept; /health=1.5.6; Bilibili 412 Chinese hint |
| #298 whisper/drafts/status | passed | download 202+poll; hf-mirror; distinct drafts; status until render |
| #299 windows overwrite | passed | app-exit check; stale backend cleared; data kept |
| #300 short/noaudio/delete | passed | too-short & no-audio precheck; delete stops render |
| #301 restart/progress/uninstall | passed | service_restarted; whisper %; uninstall keeps data unless opted |
| #302 ollama chunking | passed | source+tests; cloud path unaffected (no Ollama VM run) |
| #305 clip http_status / source_no_audio | passed | 500 recorded; no-audio tip + SRT advice |
| #306 qwen thinking off | passed | clip_finder completion 43k→~168–1380 tokens |
| #307 progress/orphan/uninstall | passed | progress 10→24%; kill9 orphans exit; four uninstall modes |
| #311 render kill partial | passed | partial kill → service_restarted + retry; allsaved stays completed |
| #308 feature flags | passed | no实验功能 in prod; OFF=0 PostHog; ON flags+usage |
| #27 analytics ON extras | accepted | Charlie 2026-10-09: usage events when analytics ON are expected; not a blocker |

Raw local evidence: /workspace/rc156/final2, /workspace/rc156/mac/evidence-final2c, /workspace/rc156/tag.

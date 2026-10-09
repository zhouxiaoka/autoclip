# macOS arm64 — AutoClip 1.5.6 internal acceptance

- Package: Desktop Build run 37937536440 @ 80bf1d6c41b97b45aa965d670f6f955299d5899c
- DMG SHA-256: 3af84c6240592f8feecd4d36a6c3b88720a6eb55766c699b967aa08ab2653533
- Environment: macOS 26.6.2 (25G83) arm64, Apple M4 MacBook Pro 24GB (physical)
- Runtime: bundled Python 3.13.13 / ffmpeg 7.1.1; app 1.5.6 adhoc-signed

## Matrix (automated / harness)

- clean_install / upgrade_legacy: isolated-dir installs; 1.5.5→1.5.6 upgrade kept seed/sentinel/keys/analysis; tag bundle-smoke desktop_health passed.
- model_settings: qwen3.8-flash + empty-key keep (#266).
- local_with_subtitles / local_without_subtitles: 150s Whisper local completed; clips decode; 35min long video 356s end-to-end after thinking-off.
- link_import: exercised on earlier RC; tag smoke focused on local Studio path.
- visual_generation: no-audio visual route → source_no_audio (#305).
- failure_recovery: interrupt-render-kill9 after #311 → project failed +「服务已重启」, kept clip playable, interrupted clip retryable → completed 2/2; allsaved kill stays completed.
- output_delivery: export decode ok; bundle-smoke portrait render 1080x1920 h264.
- privacy_telemetry: production JS has no「实验功能」; analytics OFF no PostHog; ON flags path noted; Charlie accepted ON usage events (#27).

80bf1d6c is DOC-ONLY vs ae67a70f (CHANGELOG credit only); FINAL2 @ ae67a70f + tag smoke @ 80bf1d6c bind the package.

# Windows x64 full e2e — tip b706c76d — PASS

Sanitized summary of the product e2e. No API keys, tokens, user media, or machine-local paths.

| Item | Result |
|---|---|
| Version | 1.5.8 |
| Source | `b706c76d231c801884405b663183cb75ae867004` (`integration/1.5.8-rc`) |
| Desktop Build | 41394663920 (SUCCESS, untagged `workflow_dispatch`, updated 2026-11-02T06:08:59Z) |
| Windows artifact | 13120011234 `autoclip-desktop-windows-x64` |
| Installer sha256 | `5ea61eba21de5055584ac7294507dadbb14416c5b85083d75ed8cbc7b3a81649` |
| macOS artifact (bound, not this matrix) | 13119484020 `autoclip-desktop-macos-arm64` |
| Finished | 2026-11-02T17:09:53+08:00 (Asia/Shanghai) |

Hard gates M1–M5 and soft gates N1–N4 all PASS. T3 cookies was SKIP and does not by itself fail the matrix. This note does not create a tag or a GitHub Release.

| Gate | Result | What was observed |
|---|---|---|
| M1 tip-fresh install | PASS | Interactive install reached 1.5.8 |
| M2 ACL backend start | PASS | Backend came up |
| M3 quitGuard | PASS | Quit guard verdict recorded |
| M4 #491 fail copy | PASS | Message: 应用刚重启，这次制作已中断，请重试。 |
| M5 #487 kill to respawn | PASS | Process killed, progress kept, auto respawn, `service_restarted` |
| T1 #428 home | PASS | Home UI shown |
| T2 #434 captions | PASS | exports=1 |
| T3 #481 cookies | SKIP | Not triggered; catalog-only |
| T4 #410 rename | PASS | Rename path unblocked |
| D2.1 local+SRT | PASS | Generation status=completed |
| N1 EN45 Bilibili | PASS | status=completed |
| N2 EN531 Bilibili | PASS | status=completed |
| N3 YouTube long | PASS | At least one 1920x1080 output, duration >= 180 |
| N4 YouTube long under 3 min | PASS | Creative Import UI showed only 知道了; no import and no generation |

Point N4 (same tip and Windows artifact, before the full matrix) also PASS at 2026-11-02 15:23:47 Asia/Shanghai: Creative Import required 知道了 only, and an API `status=failed` was not treated as PASS.

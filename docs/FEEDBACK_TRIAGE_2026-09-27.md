# 最新反馈排查 — 2026-09-27

基线：`origin/main` / `0241198c`（1.4.0）。反馈来自 1.3.3–1.3.5。
代码在独立分支 `codex/recent-feedback-fixes`，未修改原工作目录。

## 结论

| Issue | 复现与处理 |
| --- | --- |
| [#217](https://github.com/zhouxiaoka/autoclip/issues/217)、[#198](https://github.com/zhouxiaoka/autoclip/issues/198) 时间线为空 | 复现同类确定性故障：3 个相邻 10 秒话题在 30 秒字幕中被全部丢弃。修复为先尝试与后续相邻段合并，再决定丢弃；仍遵守合并间隔与最大时长限制。 |
| [#195](https://github.com/zhouxiaoka/autoclip/issues/195) 时间戳无法对齐 | 复现标准点号时间戳、无毫秒时间戳及 MM:SS 被拒绝。现在统一为 SRT 时间戳，并拒绝倒序、无交集及分钟/秒溢出的区间。同样可能影响 #198/#217。 |
| [#197](https://github.com/zhouxiaoka/autoclip/issues/197) YouTube invalid link | 复现 Shorts、live、m.youtube、music.youtube 及 watch 的 v 参数不在首位时被前端拒绝。提取单一 URL 解析函数供校验和平台识别共用，支持这些格式，保留 B 站及既有 YouTube 格式。 |
| [#200](https://github.com/zhouxiaoka/autoclip/issues/200)、[#181](https://github.com/zhouxiaoka/autoclip/issues/181) 未配置模型 | 反馈错误属于缺少 API Key / 服务地址的配置前置检查。已有失败与配置持久化测试通过；没有用户配置证据可确认是保存丢失等代码故障，此次未更改。 |
| [#183](https://github.com/zhouxiaoka/autoclip/issues/183) 导入长期显示 5% | 主线已包含下载进度持久化修复。相关数据库与前端进度测试通过。无法凭此确认 15 小时未完成的真实下载原因。 |
| [#182](https://github.com/zhouxiaoka/autoclip/issues/182) 短广告无法出片 | 相邻短片段误丢弃及时间戳格式修复同样适用，但不等于广告改写/混剪能力已满足；不足 20 秒的素材仍受原有时长策略限制。 |

## 验证

修复前：新增链接用例 6 个失败、时间线用例 7 个失败。
修复后：

- 后端 55 个测试通过：`test_recent_feedback.py`、`test_quality.py`、`test_pipeline_failures.py`、`test_llm_provider_config.py`、`test_download_progress_persist.py`、`test_youtube_download_isolation.py`、`test_youtube_subtitle_fallback.py`。
- 前端 `node --test tests/*.test.cjs`：129 个通过。
- `npm run typecheck` 与 `npm run build` 通过。构建存在现有 bundle 大小提示。
- 完整 step2 流程用合成字幕和固定模型响应验证，生成一个 30 秒候选及质量报告。
- 边界覆盖：长静音间隔、最大时长、不到 20 秒的整条素材、越界/倒序时间戳、伪域名及非视频链接。

## 限制与后续验证

没有反馈者的视频、字幕、模型原始响应或 #197 的原始 URL，因此以上是相同失败条件的复现，不是对每条用户反馈根因的最终确认。
未进行真实 Gemini/Ollama 调用、YouTube 在线下载或 Windows 安装包端到端验证。
前端解析接口的网络错误目前仍可能显示通用链接错误，本次链接格式修复不覆盖网络、Cookies、区域限制或 yt-dlp 上游变化。
未降低默认 20 秒最短时长，未自动把任意短素材整段返回以伪装成切片成功。
未发布版本、关闭 issue 或向反馈者发送消息。


## 后续项目审查补充

1.4 当前入口已经改为 Studio 导入，`BilibiliDownload` 未被其他组件引用。因此 #197 的修复范围是保留的旧组件（对应旧版报错路径），不代表新 Studio 入口存在相同校验缺陷。新的项目审查与独立复现结果见 [PROJECT_REVIEW_2026-09-27.md](PROJECT_REVIEW_2026-09-27.md)。

# 在 AutoClip 中使用 88API

[English](88API_SETUP.en.md) · [返回 README](../README.md)

88API Token聚合平台是 AutoClip 的赞助合作伙伴，可通过 OpenAI 兼容接口用于字幕分析、封面生图和字幕转写。

## 注册与获取 API Key

通过 [AutoClip 专属推广链接](https://88api.ai/sign-up?aff=2PIc)注册，在控制台创建 API Key。新用户注册赠送体验额度，具体金额、领取条件与服务条款以平台页面为准；站内提供人工客服。推广链接含分成，用于支持项目维护。

## 配置 AutoClip

### 新版本：直接选择 88API

1. 打开「设置 → AI 模型 → AI 服务」，在「推荐」分组选择 **88API**；首次使用也可在首页配置。
2. 填入 88API Key。接口地址已预设为 `https://88api.ai/v1`，无需手动填写。
3. 等待账号模型列表加载，选择用于字幕分析的模型；需要画面识别时，选择支持图片输入的多模态模型。
4. 点击「测试连接」，然后保存。先用一小段素材验证实际分析效果。

不预设默认文本模型或账号可用名单，准确模型 ID 与访问权限以账号返回的列表为准。无 Key 时显示的图片、语音目录只是参考，不代表账号权限。

- **封面**：可复用 AI 服务的 Key，选择支持 OpenAI Images 接口的型号，例如账号列表中的 `gpt-image-1`、`dall-e-3`。其他图片模型是否可用取决于实际接口及返回的能力信息。
- **字幕转写**：选择 88API 和账号可用的 `whisper-1`，通过 OpenAI 音频接口获取带时间戳字幕。
- 平台也提供视频生成和 TTS；这些平台能力不等于 AutoClip 已提供对应功能。

### 旧版本：通过 OpenAI 兼容接口接入

如果提供商列表还没有 88API，选择「自定义 OpenAI 兼容接口」，填写以下内容：

| 配置项 | 内容 |
| --- | --- |
| 提供商 | 自定义 OpenAI 兼容接口 |
| 接口地址（Base URL） | `https://88api.ai/v1` |
| API Key | 在 88API 控制台创建的 API Key |
| 模型 | 当前账号可用、支持 Chat Completions 的准确模型 ID |

地址中的 `/v1` 只填写一次，不要追加 `/chat/completions`。选择模型后点击「测试连接」，然后保存。

## CLI / MCP

```bash
export API88_API_KEY="你的 API Key"
autoclip run video.mp4 --provider api88 --model "账号可用的模型 ID"
```

也支持 `API_API88_API_KEY` 或 `--api-key`。MCP 使用 `provider="api88"`。

## 排查与参考

- 401：检查 Key、令牌状态、额度及前后空格。
- 404：检查接口地址和模型 ID，确认模型支持所选接口。
- 模型列表为空或获取失败：检查账号权限，刷新列表或输入控制台中的准确模型 ID。
- 测试连接成功后仍应验证一次实际分析、封面或转写；不同接口可能有不同权限。

[官方接入指南](https://88api.ai/zh/docs/apps/) · [图像接口](https://88api.ai/zh/docs/api/image/openai-image/) · [音频与时间戳格式](https://88api.ai/zh/docs/api/audio/openai-audio/)

分析内容会发送至所选服务商，调用费用由该平台账户结算。不要将 API Key 放进截图或公开反馈。

[返回 README](../README.md)

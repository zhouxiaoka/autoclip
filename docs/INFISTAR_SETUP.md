# 在 AutoClip 中使用 Infistar 无限星河

[English](INFISTAR_SETUP.en.md) · [返回 README](../README.md)

Infistar 是 AutoClip 的赞助合作伙伴，可通过现有 OpenAI 兼容接口配置使用。

## 注册与获取 API Key

通过 [AutoClip 专属推广链接](https://www.infistar.cc/register?aff=XLK3BCM6&ref_source=link)注册，在 Infistar 控制台创建 API Key。根据合作方提供的活动说明，该渠道可领取 $5 体验额度；领取条件及活动变化以合作方页面为准。

## 配置 AutoClip

### 新版本（1.4.1 起）：直接选择 Infistar

1. 打开「设置 → 模型」，提供商选 **Infistar**。接口地址已预设为 `https://infistar.cc/v1`，不用填。
2. 还没有账号时，点「注册并领取体验额度」，用专属链接注册并在控制台创建 API Key。
3. 把 API Key 粘贴进来。模型下拉会自动列出这个账号可用的型号，选一个。
4. 点「测试连接」，再保存。

命令行 / MCP：`autoclip run video.mp4 --provider infistar --api-key sk-… --model <模型 ID>`，也可以设置环境变量 `INFISTAR_API_KEY`。

### 旧版本：用 OpenAI 兼容接口手动填写

打开「设置 → 模型」，填写以下内容：

| 配置项 | 内容 |
| --- | --- |
| 提供商 | OpenAI / 兼容接口 |
| 接口地址 | `https://infistar.cc/v1` |
| API Key | 你在 Infistar 创建的 API Key |
| 模型 | 当前账号可用、支持 Chat Completions 的真实模型 ID |

接口地址中的 `/v1` 只填写一次，不要追加 `/chat/completions`。国际网络也可使用 `https://infistar.ai/v1`（新版本选 OpenAI 兼容接口手动填写即可），参见 [Infistar 网关配置文档](https://doc.infistar.cc/integration-guides/gateway-config)。

从模型列表选择或手动输入真实模型 ID，执行「测试连接」并保存。不要直接沿用 OpenAI 官方默认模型名，具体可用型号由 Infistar 账号权限和模型目录决定。

先用一段较短的视频或已有字幕完成一次分析，确认能生成高光片段、标题和时间范围，再进行长视频批量处理。测试连接成功仅说明测试请求通过，不能替代实际素材验证。

## 常见问题

- **401 / 鉴权失败**：检查 API Key 是否有效、是否属于 Infistar，以及复制时是否带入空格。
- **404 / 路径不存在**：检查接口地址是否为上述 `/v1` 地址，且没有重复拼接路径。
- **模型不存在或不支持接口**：核对模型 ID 和账号权限，并选择支持 Chat Completions 的型号。不同模型不一定支持相同端点或参数，参见 [官方兼容说明](https://infistar.cc/openai-compatible-api)。

模型请求会将分析所需内容发送到所配置的服务商，调用费用由该服务商账户结算。API Key 请仅填写在设置中，不要放进截图、公开文档或反馈记录。

[返回 README](../README.md)

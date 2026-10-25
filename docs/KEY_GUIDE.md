# 密钥引导（1.5.8）

把从任意网站复制来的 API 密钥，确认后填进对应的服务商设置。不绑定某一家中转站，也不在未确认时写入。

相关代码：`frontend/src/features/settings/keyGuide.ts`、`KeyGuidePrompt.tsx`、`keyGuideWatch.ts`，桌面协议在 `src-tauri`。

## 剪贴板

窗口获得焦点时读一次剪贴板。像密钥的内容会在底部出现一条提示，点「填入服务商」后才打开确认。设置 → AI 模型里的「识别剪贴板中的密钥」做同一次检查。

能认出的形式：带厂商前缀的密钥（`AIza`、`xai-`、`sk-proj-`、`sk-svcacct-`、`sk-or-v1-`）、足够长的 `sk-`、以及带 `api key` / `token` / `secret` / `密钥` 标签或 `Bearer` 的一段文本。普通句子、网址、短字符串不会被当成密钥。

前缀或接口主机能对上唯一一家预置服务商时，确认框会预选它。对不上、或两边互相矛盾时，由用户自己选。看不出来源时也不会落到赞助服务商。自定义兼容接口要自己填地址。

已有密钥时，主按钮是「替换已保存的密钥」。取消保留原来的。在某个服务商的密钥框里直接打字不会拦截；只有粘贴出的前缀明确属于另一家时，才会改问要不要填到那边。

忽略之后，同一次会话里焦点扫描不再提起同一段密钥。记住的是哈希，不是密钥本身。

## autoclip://

可选。中转站若支持 New API「聊天应用」占位符 `{key}` 和 `{address}`，加一行即可，不必改 AutoClip：

```json
{"AutoClip":"autoclip://import?key={key}&base_url={address}/v1"}
```

`{address}` 不含末尾斜杠，也不含 `/v1`。也接受查询参数 `api_key` / `token`，以及 `url` / `server` / `address`。可选 `provider` 为预置 id；它和地址、前缀冲突时仍要用户选择。

链接只打开确认框。密钥不进路由、不进日志、不进埋点。页面上报只使用 `/settings?section=ai`，需要时再加 `provider=<预置 id>`。

协议名是 `autoclip`。注册方式：

| 平台 | 安装包 | 开发运行 |
| --- | --- | --- |
| macOS | 打包进 `.app` 的 Info.plist。系统只把链接交给已安装的应用，通常在 `/Applications`。 | `tauri dev` 收不到协议。用安装后的包验证：`open "autoclip://import?key=...&base_url=https://example.com/v1"` |
| Windows | 安装器写入协议。第一次启动也会 `register_all`。 | 开发进程启动时 `register_all`。`start autoclip://import?key=...&base_url=https://example.com/v1` |
| Linux | 打包时注册。运行时同样 `register_all`。 | `xdg-open "autoclip://import?key=...&base_url=https://example.com/v1"` |

Windows 和 Linux 要靠单实例把第二次启动收进已经打开的窗口，否则系统会再开一个进程，链接到不了当前界面。macOS 也使用同一插件，第二次打开会把已有窗口带到前台。启动参数里可能含有密钥，原生层不打印这些参数。

## 校验失败

保存仍然会记下失败状态，生成在校验失败时继续被拦住。无效密钥、权限拒绝或额度不足时，不再只提示「已保存」，而会说明密钥没有通过校验。网络超时一类暂时失败会提示这次没能确认。阿里云百炼走同一条保存路径，401 记为无效密钥。

自定义接口在还没有分析模型时，会先放一个用于探测的模型 id，以便发出校验请求；之后可以在设置里改掉。

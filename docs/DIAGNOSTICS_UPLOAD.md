# 失败诊断上传

状态：代码在 1.5.9 分支，**没有部署**，也没有创建 Cloudflare 资源。桌面端地址为空时不会上传。

## 用户能做什么

- 设置「帮助改进 AutoClip」默认关闭。第一次打开是明确同意：只用于排查和改进产品，不用于训练模型。
- 同意只覆盖这之后的新失败。已经失败的任务不会被补传。
- 片段开关默认关。完整原片还要再同意一次。后台不会自动带字幕文本。
- 没开设置时，失败卡上的「提交诊断」会先列出将要发送的字段，素材默认不勾选。
- 关掉设置会停掉新的上传，取消队列，并尽量中止正在进行的上传。撤销之后不会再申请新的上传许可。
- 每个 case 有一次性能力令牌，可以删除已上传的内容。
- 没有地址、或网络失败时，同一次提交可以改存本机。本机导出不是主路径。

## 不会发送的东西

API 密钥、Authorization、带查询参数的 URL、个人路径、项目名、转写正文、原始日志目录、`settings.json`、cookie、数据库。日志只保留能通过行格式和脱敏的短句。

素材只来自该项目的 `raw/input.*` 和已有 `input.srt`。符号链接和逃出项目目录的路径会被拒绝。

## 和服务端的关系

提议中的名字（都还没创建）：

- Worker `autoclip-diagnostics-api`
- 私有桶 `autoclip-diagnostics`，绑定 `DIAGNOSTICS_BUCKET`
- D1 `autoclip-diagnostics-meta`，绑定 `DIAGNOSTICS_DB`

不使用现有的 `autoclip-media` 桶。模板和限制说明在 `services/diagnostics-api/README.md`。

待批的提议上限：清单 256KB，字幕 2MB，片段 200MB，完整原片 2GB，已落地 4GiB，在途 2GiB，保留 14 天，未完成的 multipart 1 天后中止。账号免费层的 10GB·月不是硬性花费上限。

## 成功率

诊断条数不是分子，也不是分母。分母仍然是 `docs/analytics/success_rate.sql` 里的 attempt。

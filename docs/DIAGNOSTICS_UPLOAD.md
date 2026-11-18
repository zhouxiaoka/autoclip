# 失败诊断上传

状态：生产 Worker 已上线。桌面端内置地址是 `https://autoclip-diagnostics-api.autoclip-val-3f71ee83.workers.dev`。没有保存过选择时，「帮助改进 AutoClip」、短片段和完整原片都显示为打开。自动上传要等用户看到并确认首次说明之后才会开始。已经保存的关闭保持关闭。

## 用户能做什么

- 没有 `diagnostics/consent.json` 时，总开关、短片段和完整原片都按打开处理。这不是以前的单独同意。
- 应用启动时会先弹出说明：脱敏诊断和完整原片默认会在失败后自动发送，只用于排查和改进，不用于训练；保留 14 天；可以关掉总开关或单独关掉素材。点背景或按 Esc 不会记成已确认，在确认之前不会自动上传。确认之后的新失败才会进入队列，更早的失败不会补传。
- 已经写成关闭的选择会原样保留，不会因为这次默认打开而被重新打开。读不出来的同意文件也不会被当成新的打开。
- 后台自动上传在完整原片打开时发送完整原片，不发送字幕正文。关掉完整原片且片段仍打开时，只发送片头短片段。关掉总开关会取消尚未完成的上传。只关掉某一类素材时，取消带有该类素材的队列，不取消只有脱敏清单的项目。
- 失败卡上的「提交诊断」仍会先列出将要发送的字段，素材复选框默认不勾选。
- 关掉设置会停掉新的上传，取消队列，并尽量中止正在进行的上传。撤销之后不会再申请新的上传许可。
- 确认删除或取消之后，会删掉该诊断自己的 `excerpts/<id>`。远端删除已经确认、或从未需要远端清理时，一并删掉能力令牌和恢复凭据。远端删除还要重试时，这两份凭据留着。项目里的原片不会删。
- 每个 case 有一次性能力令牌，可以删除已上传的内容。
- 用户选择保存到本机时，不走上传。网络失败时，同一次提交可以改存本机。本机导出不是主路径。

## 不会发送的东西

API 密钥、Authorization、带查询参数的 URL、个人路径、项目名、转写正文、原始日志目录、`settings.json`、cookie、数据库。日志只保留能通过行格式和脱敏的短句。

素材只来自该项目的 `raw/input.*` 和已有 `input.srt`。符号链接和逃出项目目录的路径会被拒绝。

## 和服务端的关系

已创建的资源：

- Worker `autoclip-diagnostics-api`：`https://autoclip-diagnostics-api.autoclip-val-3f71ee83.workers.dev`
- 私有桶 `autoclip-diagnostics`，绑定 `DIAGNOSTICS_BUCKET`
- D1 `autoclip-diagnostics-meta`，id `91ac62f9-8b47-4f88-af93-08c2706caace`，绑定 `DIAGNOSTICS_DB`

不使用现有的 `autoclip-media` 桶。模板和限制说明在 `services/diagnostics-api/README.md`。

桌面端地址优先级：环境变量 `AUTOCLIP_DIAGNOSTICS_ENDPOINT`，然后是数据目录里的 `diagnostics/endpoint.json`，最后是上面的内置地址。空的环境变量或空的文件值不会关掉内置地址。

已部署的上限：清单 256KB，字幕 2MB，片段 200MB，完整原片 2GB，已落地 4GiB，在途 2GiB，保留 14 天，未完成的 multipart 1 天后中止。账号免费层的 10GB·月不是硬性花费上限。

## 成功率

诊断条数不是分子，也不是分母。分母仍然是 `docs/analytics/success_rate.sql` 里的 attempt。

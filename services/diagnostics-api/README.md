# autoclip-diagnostics-api

私有诊断上传的 Worker。生产资源已经创建，桌面端内置这个地址。没有保存过选择时，诊断和压缩短片段按默认上传，完整原片关闭；说明只是告知和退出。已经保存的关闭保持关闭。生产服务是否已包含来源链接清洗，仍待核对。

| 资源 | 名字 | 标识 |
|---|---|---|
| Worker | `autoclip-diagnostics-api` | `https://autoclip-diagnostics-api.autoclip-val-3f71ee83.workers.dev` |
| R2（私有） | `autoclip-diagnostics` | 绑定 `DIAGNOSTICS_BUCKET` |
| D1 | `autoclip-diagnostics-meta` | 绑定 `DIAGNOSTICS_DB`，id `91ac62f9-8b47-4f88-af93-08c2706caace` |

不引用、不修改现有的 `autoclip-media` 桶。继续用 `workers.dev`，不另买域名。`wrangler.jsonc` 里的体积上限是已部署的值。`QUOTA_APPROVAL` 仍是 `pending`，它不是密钥；账号免费层的 10GB·月仍然不是硬性花费上限。

## 配额不是账单封顶

账号免费层的 10GB·月**不是**硬性花费上限。这里的 4GiB 已落地 + 2GiB 在途是应用自己的预留，超限就拒绝签名。2GB 原片必须同时放进剩余的落地额度和在途额度，否则拒绝。这不保证落在免费层里，也不保证不会产生费用。

## 字节上限怎么卡住

大文件不能穿过 Worker（请求体远小于 2GB）。客户端直传 R2。R2 绑定本身不会签发预签名 URL，所以 Worker 用**仅存在于 Worker secret** 的 S3 API 令牌签名。开源客户端里没有这块静态凭证。

签名前先在 D1 里做条件更新：`landed + reserved + new <= landed cap` 且 `reserved + new <= inflight cap`，`changes = 1` 才继续。每个 PUT 的 `Content-Length` 写进 SigV4 规范请求，URL 约 900 秒过期，不能拿去传另一种大小。完成时先看对象元数据里的长度，不把对象正文读进 Worker。长度对得上就记账一次；临时的元数据或数据库错误保持原对象可重试，只有确认长度不对或分片标识无效才删除。不对正文做哈希。不完整的 multipart 由 cron 在 1 天后 abort。

Worker **不会**把整个对象再读一遍做哈希（免费层 CPU / 内存不够）。单段上传会把调用方声明的 SHA-256 签进 `x-amz-checksum-sha256`。这依赖 R2 真的执行被签名的校验头。本仓库没有对真实桶做过这项验证。尺寸上限不依赖这项校验。

服务端不根据客户端提供的 URL 去拉取，也不解压归档包。

## 创建恢复与删除

客户端在第一次创建请求前，把随机恢复凭据写入本机独立的 0600 文件；队列、导出包和 manifest 不含它。创建响应丢失或应用退出后，`POST /v1/cases/cancel` 用原幂等键和凭据清理，不重新发送 manifest 或素材。服务端只保存凭据哈希；取消先到时保存不含内容的取消记录，阻止迟到的创建请求重新上传。此取消记录长期保留，不随 14 天素材保留期删除；未知请求的取消接口有速率限制。

D1 的身份认领与配额预留、文件完成与配额转移、最终删除与配额释放均使用事务。删除先写 `deleting`，远端清理暂时失败时由重试/cron 继续；完成、刷新和旧快照不能覆盖删除。`0002_recovery.sql` 增加恢复字段和取消记录，并按持久化对象状态修复旧版分步写入遗留的配额差异，不改变素材和凭据。

上传计划返回独立的 `upload_expires_at`。客户端在到期或 PUT 返回 401/403 后按同一请求刷新，保留原 object ID、分片布局和已完成分片的 ETag。新协议的凭据在刷新时保持稳定，刷新响应丢失也能继续删除；持续鉴权失败最多刷新两次，第三次失败终止。

## 本地测试

需要 Node 22.22+（内置 SQLite）和项目测试依赖。在仓库根目录运行：

```bash
npm ci --prefix services/diagnostics-api
python scripts/quality_gate.py --group diagnostics --report /absolute/local/path/diagnostics.json
python -m pytest -c backend/pytest.ini -o addopts= backend/tests/test_diagnostics_upload.py backend/tests/test_diagnostics_recovery.py
```

回归执行生产 D1 SQL，覆盖逐条写入失败和真实事务回滚；另用真实 Python HTTP 客户端对接本机 Worker handler / SQLite，复现创建丢响应和上传授权失效。测试只用合成字节，没有连接真实 R2/D1，不能代替部署前的预签名、校验头与 multipart 验证。

真实对象存储验证的开关、配额和凭据要求见 `live/README.md`。那个脚本默认不联网。不要运行 `wrangler deploy`，除非 Charlie 明确授权。生产 D1 id 和 Worker 地址已经写在 `wrangler.jsonc` 里，这里没有密钥。

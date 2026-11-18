# autoclip-diagnostics-api

私有诊断上传的 Worker 模板。**还没有创建** Cloudflare 资源，桌面端上传地址默认为空，空地址不会上传。

提议中的名字（未创建，也未购买域名）：

| 资源 | 名字 | 绑定 |
|---|---|---|
| Worker | `autoclip-diagnostics-api` | — |
| R2（私有） | `autoclip-diagnostics` | `DIAGNOSTICS_BUCKET` |
| D1 | `autoclip-diagnostics-meta` | `DIAGNOSTICS_DB` |

不引用、不修改现有的 `autoclip-media` 桶。以后若用 `workers.dev`，也不要买域名。生产部署、预算和真实 URL 都要 Charlie 另批。`wrangler.jsonc` 里的上限是**提议**，`QUOTA_APPROVAL=pending`。

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

真实对象存储验证的开关、配额和凭据要求见 `live/README.md`。那个脚本默认不联网。不要运行 `wrangler deploy`，也不要按这份模板去创建桶或数据库，除非 Charlie 明确授权。

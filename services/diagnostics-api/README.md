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

签名前先在 D1 里做条件更新：`landed + reserved + new <= landed cap` 且 `reserved + new <= inflight cap`，`changes = 1` 才继续。每个 PUT 的 `Content-Length` 写进 SigV4 规范请求，URL 约 900 秒过期，不能拿去传另一种大小。完成时用 HEAD 或 ListParts 核对实际字节；不一致就删除或 abort multipart，预留释放，不计入落地。不完整的 multipart 由 cron 在 1 天后 abort。

Worker **不会**把整个对象再读一遍做哈希（免费层 CPU / 内存不够）。单段上传会把调用方声明的 SHA-256 签进 `x-amz-checksum-sha256`。这依赖 R2 真的执行被签名的校验头。本仓库没有对真实桶做过这项验证。尺寸上限不依赖这项校验。

服务端不根据客户端提供的 URL 去拉取，也不解压归档包。

## 本地测试

```bash
node --experimental-strip-types --test services/diagnostics-api/test/*.test.ts
```

不要运行 `wrangler deploy`，也不要按这份模板去创建桶或数据库，除非 Charlie 明确授权。

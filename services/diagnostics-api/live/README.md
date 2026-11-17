# Isolated validation handoff

Reviewed worker behavior is commit `b26bcb7ce094c62f6ede1fc06b90797bf62602c3`. This directory does not deploy, mint tokens, or upload. The parent executor deploys the compiled bundle with the approved OAuth connector.

## Resources

The 2026-11-17 staging bucket, D1, Worker, and token were deleted after the first live run. The account is still `3f71ee831844494b715377dd40a5cd47`. The workers.dev subdomain `autoclip-val-3f71ee83` remained. Recreate the isolated bucket, D1, and Worker before the next run; this package does not create them. Use the new D1 id in `metadata.json` before upload. Do not reuse a deleted database id.

Do not touch `autoclip-media`. Do not enable a public bucket, custom domain, or r2.dev.

## What the signer sends

`presignPut` signs `PUT`, the object path, and query names `X-Amz-Algorithm`, `X-Amz-Credential`, `X-Amz-Date`, `X-Amz-Expires`, `X-Amz-SignedHeaders`, plus `partNumber` and `uploadId` when the upload is multipart. The canonical payload line is `UNSIGNED-PAYLOAD`. The body is not part of the signature.

Signed headers on a single-part URL are `content-length` and `x-amz-checksum-sha256` (base64 of the declared 32-byte SHA-256). Multipart part URLs sign `content-length`, `content-md5`, and `host`. The client sends that MD5 with the part body. A missing or altered `content-md5` is an authorization failure. A body that does not match the signed MD5 is a payload failure. Completion still checks object size only.

`presignGet` signs `GET` with header `host` only. `presignHead` signs `HEAD` the same way. The two URLs are not interchangeable: a HEAD request that presents the GET signature fails signature verification. The read endpoint returns both `url` and `head_url`. Neither is a credential dump, and neither ETag is a SHA-256.

Session tokens are unsupported. `SignInput` has no session-token field, and neither presign function writes `X-Amz-Security-Token`. Do not use R2 temporary credentials whose response includes a session token; this signer cannot send it.

These names are not signed. Treating a 200 without them as checksum enforcement would be wrong:

`x-amz-checksum-crc32`, `x-amz-checksum-crc32c`, `x-amz-checksum-sha1`, `x-amz-checksum-mode`, `x-amz-sdk-checksum-algorithm`, `x-amz-trailer`, `x-amz-content-sha256`.

`content-md5` is signed on multipart parts only. It is not signed on a single-part URL; that URL uses `x-amz-checksum-sha256`.

A mismatched `x-amz-checksum-sha256` or a corrupted body is an observation. If the object store returns 200, checksum enforcement is not proven and stays a blocker. Signature rejection (tampered query or a missing signed header) is authorization, not payload proof. An ETag is not a SHA-256.

## Quota

Reviewed production inflight cap is 2147483648. The validation Worker uses that same cap. A 2147483648-byte object plus its manifest does not fit, so create returns 413 and uploads nothing. The largest original that can be reserved is that cap minus the manifest's own byte length. Landed cap stays 4294967296. This file does not change `wrangler.jsonc`.

The harness uploads at most the bytes in `planUploads`, which is under 3GiB. `ORIGINAL_MAX` plus the manifest is larger than the frozen in-flight cap of 2147483648, so that create is expected to return 413 `inflight_cap` and to upload nothing. The separate `fitting-original-under-inflight` case is the largest original that fits with its manifest. It is not an exact 2GiB object. Part size stays 8388608. The staging Worker uses the same in-flight cap as production. A create may send `part_ttl_seconds` no higher than the server TTL; the expiry case uses 2 seconds and refuses to sleep longer than 20 seconds. Replay after a created case is cancelled returns 404 and no upload plan. 410 remains the response only when the cancellation tombstone exists and no case row was stored.

## One execute for the bucket token

Run this on the parent executor, not on the agent VM. Do not print the token value, the derived secret, or the access key.

1. `GET /accounts/3f71ee831844494b715377dd40a5cd47/tokens/permission_groups` and select the groups named Workers R2 Storage Bucket Item Read and Workers R2 Storage Bucket Item Write.
2. `POST /accounts/3f71ee831844494b715377dd40a5cd47/tokens` with a policy whose resource is `com.cloudflare.edge.r2.bucket.3f71ee831844494b715377dd40a5cd47_default_autoclip-diagnostics-validation` and those two groups only.
3. From the response, if `access_key_id` and `secret_access_key` are present, use them. If the response has only `id` and `value`, the access key id is `id` and the secret access key is the lowercase hex SHA-256 of the UTF-8 token value. Do not hash a secret that is already the access-key secret.
4. After the Worker script exists, `PUT /accounts/3f71ee831844494b715377dd40a5cd47/workers/scripts/autoclip-diagnostics-validation-api/secrets` twice, type `secret_text`, names `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY`. `R2_ACCOUNT_ID` is the plain text account id `3f71ee831844494b715377dd40a5cd47`.
5. Drop the token value and the secret from the process. Return only the token id so it can be revoked with `DELETE /accounts/3f71ee831844494b715377dd40a5cd47/tokens/{token_id}`.

`main` and `executeLive` do not read those secrets. `signedSinglePut` and the harness `presignGet` export can sign if a caller passes the secrets in. After complete, the execute path asks `POST /v1/cases/{case_id}/files/{object_id}/read-url` with the case capability. It sends HEAD to `head_url` and GET to `url`, then compares the HEAD content-length with the streamed GET hash. Neither URL is written to the result or to `queue.json`.

The local HTTPS fixture recomputes SigV4 itself. It does not treat a present signature as authorization, and it does not call the production signer to check a request. A GET URL used as HEAD is 403. A changed signed header is 403 when the server returns HTTP. A body that does not match the unchanged signed checksum or content-md5 is 400 when the server returns HTTP. Each PUT opens a new connection and yields after the first 16KiB, so an early HTTP status is kept if the socket then resets. A reset with no status stays `transportUnverified` and is not a 400 or a 403. The fifth live run had two of those resets: the 64KiB single-part body did not match its signed SHA-256, and an 8MiB part was sent with a changed content-md5. The same run's multipart body mismatch did return 400 BadDigest. Those two resets stay unverified.

Any failed or unverified case stops the later cases. Cleanup DELETE still runs. Before the exact-cap create and the fitting upload, the harness calls `GET /admin/quota` with `AUTOCLIP_DIAGNOSTICS_ADMIN_TOKEN`. That token is not stored in this package. `reserved: 0` with 413 `inflight_cap` is the frozen cap. A nonzero `reserved` is leftover reservation. The fixture multipart ETag is a SHA-256 of that part for the local adapter only. It is not an R2 ETag and not the content hash. The fixture is not R2 and not production D1.

## Apply schema, then upload the bundle

Apply `migrations/0001_init.sql`, then `migrations/0002_recovery.sql`, then `migrations/0003_guard.sql`, to the new D1 id. Put that id in `metadata.json` before upload. The compiled Worker does not contain a database id. Do not apply `0002` or `0003` twice. The previous validation database was deleted. `0003` adds `write_guard`. A broken accounting batch writes `ok = 0` there, the CHECK fails, and that failed statement is what aborts the batch. A zero-row update alone does not.

A 16MiB two-part control must complete and its streamed GET hash must match before the negative cases, the 200MiB object, or the fitting-original upload. The fitting upload is the cap minus the manifest. It is not named or treated as an exact 2GiB object. The Worker converts a quoted HTTP ETag into the unquoted `R2UploadedPart.etag` before `complete()`. A 409 names `etag_mismatch`, `missing_part`, or `size_mismatch` and includes `expectedBytes` and `actualBytes`. Those numbers are captured before the object is deleted. An HTTP 0 result is `transportUnverified`, not an integrity result. The readback GET uses the response kept in memory; the evidence copy does not contain the URL.

The harness appends redacted events to `events.jsonl` and rewrites `evidence.json` after each step. A dropped connection still leaves those files, writes the same JSON to stdout and stderr, and exits nonzero. Bytes counted are bytes handed to the socket, not a server-acked total. A part may be retried twice. The next write is refused when it would pass 3GiB. 200MiB must complete and its streamed hash must match before the fitting-original upload starts. There is no exact-2GiB upload under the frozen cap. The 900 second part TTL is unchanged. Large uploads refresh part URLs when less than 60 seconds remain. That is not a claim that the second run's connection reset was caused by the TTL.

Upload `worker.mjs` as module `index.js` with `metadata.json`. Set the cron `17 * * * *` with the schedules API. Do not attach `autoclip-media`.

## Run the harness

```bash
node live/harness.mjs
AUTOCLIP_DIAGNOSTICS_LIVE=1 AUTOCLIP_DIAGNOSTICS_LIVE_APPROVED=staging \
  AUTOCLIP_DIAGNOSTICS_LIVE_ENDPOINT=https://THE_WORKER_HOST \
  node live/harness.mjs --execute
```

The first command prints `not-run` and exits 0. `--execute` exits 1 when any required case is missing or fails. A mock adapter passing is not a live pass. The 503 from the first run had no response body, so its storage error text is unknown; the next run records `phase`, `detail`, and `cf-ray` without the presigned URL.

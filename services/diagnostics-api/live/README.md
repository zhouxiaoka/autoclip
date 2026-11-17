# Isolated validation handoff

Reviewed worker behavior is commit `b26bcb7ce094c62f6ede1fc06b90797bf62602c3`. This directory does not deploy, mint tokens, or upload. The parent executor deploys the compiled bundle with the approved OAuth connector.

## Resources

The 2026-11-17 staging bucket, D1, Worker, and token were deleted after the first live run. The account is still `3f71ee831844494b715377dd40a5cd47`. The workers.dev subdomain `autoclip-val-3f71ee83` remained. Recreate the isolated bucket, D1, and Worker before the next run; this package does not create them. Use the new D1 id in `metadata.json` before upload. Do not reuse a deleted database id.

Do not touch `autoclip-media`. Do not enable a public bucket, custom domain, or r2.dev.

## What the signer sends

`presignPut` signs `PUT`, the object path, and query names `X-Amz-Algorithm`, `X-Amz-Credential`, `X-Amz-Date`, `X-Amz-Expires`, `X-Amz-SignedHeaders`, plus `partNumber` and `uploadId` when the upload is multipart. The canonical payload line is `UNSIGNED-PAYLOAD`. The body is not part of the signature.

Signed headers on a single-part URL are `content-length` and `x-amz-checksum-sha256` (base64 of the declared 32-byte SHA-256). Multipart part URLs sign `content-length`, `content-md5`, and `host`. The client sends that MD5 with the part body. A missing or altered `content-md5` is an authorization failure. A body that does not match the signed MD5 is a payload failure. Completion still checks object size only.

`presignGet` signs `GET` with header `host` only. It exists so a case capability can obtain one short-lived read URL. It is not a credential dump.

Session tokens are unsupported. `SignInput` has no session-token field, and neither presign function writes `X-Amz-Security-Token`. Do not use R2 temporary credentials whose response includes a session token; this signer cannot send it.

These names are not signed. Treating a 200 without them as checksum enforcement would be wrong:

`x-amz-checksum-crc32`, `x-amz-checksum-crc32c`, `x-amz-checksum-sha1`, `x-amz-checksum-mode`, `x-amz-sdk-checksum-algorithm`, `x-amz-trailer`, `x-amz-content-sha256`.

`content-md5` is signed on multipart parts only. It is not signed on a single-part URL; that URL uses `x-amz-checksum-sha256`.

A mismatched `x-amz-checksum-sha256` or a corrupted body is an observation. If the object store returns 200, checksum enforcement is not proven and stays a blocker. Signature rejection (tampered query or a missing signed header) is authorization, not payload proof. An ETag is not a SHA-256.

## Quota

Reviewed production inflight cap is 2147483648. A 2147483648-byte object plus its manifest does not fit that cap, so create returns 413 and uploads nothing. The validation Worker var `INFLIGHT_BYTES_CAP` is 2147745792 (that cap plus the 262144 manifest ceiling) so the approved 2GiB object can be reserved once. Landed cap stays 4294967296. This file does not change `wrangler.jsonc`.

The harness uploads at most the bytes in `planUploads`, which is under 3GiB. It deletes the 200MiB case and checks the reservation is released before creating the 2GiB object. A 413 with `inflight_cap` means that reservation is still held; it is not evidence that the object store rejects 2GiB. Part size stays 8388608. A create may send `part_ttl_seconds` no higher than the server TTL; the expiry case uses 2 seconds and refuses to sleep longer than 20 seconds. Replay after a created case is cancelled returns 404 and no upload plan. 410 remains the response only when the cancellation tombstone exists and no case row was stored.

## One execute for the bucket token

Run this on the parent executor, not on the agent VM. Do not print the token value, the derived secret, or the access key.

1. `GET /accounts/3f71ee831844494b715377dd40a5cd47/tokens/permission_groups` and select the groups named Workers R2 Storage Bucket Item Read and Workers R2 Storage Bucket Item Write.
2. `POST /accounts/3f71ee831844494b715377dd40a5cd47/tokens` with a policy whose resource is `com.cloudflare.edge.r2.bucket.3f71ee831844494b715377dd40a5cd47_default_autoclip-diagnostics-validation` and those two groups only.
3. From the response, if `access_key_id` and `secret_access_key` are present, use them. If the response has only `id` and `value`, the access key id is `id` and the secret access key is the lowercase hex SHA-256 of the UTF-8 token value. Do not hash a secret that is already the access-key secret.
4. After the Worker script exists, `PUT /accounts/3f71ee831844494b715377dd40a5cd47/workers/scripts/autoclip-diagnostics-validation-api/secrets` twice, type `secret_text`, names `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY`. `R2_ACCOUNT_ID` is the plain text account id `3f71ee831844494b715377dd40a5cd47`.
5. Drop the token value and the secret from the process. Return only the token id so it can be revoked with `DELETE /accounts/3f71ee831844494b715377dd40a5cd47/tokens/{token_id}`.

The harness does not read those secrets. After complete it asks `POST /v1/cases/{case_id}/files/{object_id}/read-url` with the case capability and streams the returned URL. The URL is not written to the result.

## Apply schema, then upload the bundle

Apply `migrations/0001_init.sql`, then `migrations/0002_recovery.sql`, to database `3b9da920-588d-493d-ac00-cfdeab985dd1`. The database currently has no tables. Do not apply `0002` twice.

Upload `worker.mjs` as module `index.js` with `metadata.json`. Set the cron `17 * * * *` with the schedules API. Do not attach `autoclip-media`.

## Run the harness

```bash
node live/harness.mjs
AUTOCLIP_DIAGNOSTICS_LIVE=1 AUTOCLIP_DIAGNOSTICS_LIVE_APPROVED=staging \
  AUTOCLIP_DIAGNOSTICS_LIVE_ENDPOINT=https://THE_WORKER_HOST \
  node live/harness.mjs --execute
```

The first command prints `not-run` and exits 0. `--execute` exits 1 when any required case is missing or fails. A mock adapter passing is not a live pass. The 503 from the first run had no response body, so its storage error text is unknown; the next run records `phase`, `detail`, and `cf-ray` without the presigned URL.

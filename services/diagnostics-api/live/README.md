# Isolated validation handoff

Reviewed worker behavior is commit `b26bcb7ce094c62f6ede1fc06b90797bf62602c3`. This directory does not deploy, mint tokens, or upload. The parent executor deploys the compiled bundle with the approved OAuth connector.

## Resources already provisioned

| Resource | Name | Id |
|---|---|---|
| Account | — | `3f71ee831844494b715377dd40a5cd47` |
| R2, private, r2.dev off | `autoclip-diagnostics-validation` | `a5c1a5126bed42daa31684e26bbc35b0` |
| D1, empty | `autoclip-diagnostics-validation-meta` | `3b9da920-588d-493d-ac00-cfdeab985dd1` |
| Worker | `autoclip-diagnostics-validation-api` | not created yet |

Do not touch `autoclip-media`. Do not enable a public bucket, custom domain, or r2.dev.

## What the signer sends

`presignPut` signs `PUT`, the object path, and query names `X-Amz-Algorithm`, `X-Amz-Credential`, `X-Amz-Date`, `X-Amz-Expires`, `X-Amz-SignedHeaders`, plus `partNumber` and `uploadId` when the upload is multipart. The canonical payload line is `UNSIGNED-PAYLOAD`. The body is not part of the signature.

Signed headers on a single-part URL are `content-length` and `x-amz-checksum-sha256` (base64 of the declared 32-byte SHA-256). Multipart part URLs sign only `content-length` and `host`. The client then sends those headers plus the raw bytes. It does not send `Content-MD5`.

`presignGet` signs `GET` with header `host` only. It exists so a case capability can obtain one short-lived read URL. It is not a credential dump.

Session tokens are unsupported. `SignInput` has no session-token field, and neither presign function writes `X-Amz-Security-Token`. Do not use R2 temporary credentials whose response includes a session token; this signer cannot send it.

These names are not signed and are not sent. Treating a 200 without them as checksum enforcement would be wrong:

`content-md5`, `x-amz-checksum-crc32`, `x-amz-checksum-crc32c`, `x-amz-checksum-sha1`, `x-amz-checksum-mode`, `x-amz-sdk-checksum-algorithm`, `x-amz-trailer`, `x-amz-content-sha256`.

A mismatched `x-amz-checksum-sha256` or a corrupted body is an observation. If the object store returns 200, checksum enforcement is not proven and stays a blocker. Signature rejection (tampered query or a missing signed header) is authorization, not payload proof. An ETag is not a SHA-256.

## Quota

Reviewed production inflight cap is 2147483648. A 2147483648-byte object plus its manifest does not fit that cap, so create returns 413 and uploads nothing. The validation Worker var `INFLIGHT_BYTES_CAP` is 2147745792 (that cap plus the 262144 manifest ceiling) so the approved 2GiB object can be reserved once. Landed cap stays 4294967296. This file does not change `wrangler.jsonc`.

Planned bytes with both streams: five 64KiB probes, one 16MiB wrong-etag object, 200MiB, and 2GiB. The sum is under 3GiB. Concurrency is one. Part size is 8388608, so 200MiB and 2GiB are multipart and have no checksum header.

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

From this directory, with no credentials in the command line:

```bash
node live/harness.mjs
AUTOCLIP_DIAGNOSTICS_LIVE=1 AUTOCLIP_DIAGNOSTICS_LIVE_APPROVED=staging \
  AUTOCLIP_DIAGNOSTICS_LIVE_ENDPOINT=https://THE_WORKER_HOST \
  node live/harness.mjs --execute
```

The first command prints `not-run`. `--execute` is the live phase and is not run by the agent that built this bundle.

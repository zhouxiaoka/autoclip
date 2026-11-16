/**
 * Worker entry. No resources are created by this file.
 * Bindings (proposed, not provisioned): DIAGNOSTICS_BUCKET, DIAGNOSTICS_DB.
 * R2 S3 signing secrets stay in Worker secrets, never in the desktop client.
 */
import { handle, sweep, type Bucket, type Deps, type Signer } from './app.ts'
import { D1Repo, type D1 } from './d1.ts'
import { limitsFrom } from './quota.ts'
import { presignPut, sha256Base64 } from './sign.ts'

interface Env {
  DIAGNOSTICS_BUCKET: Bucket & { list: (options?: { prefix?: string }) => Promise<{ objects: { key: string }[] }> }
  DIAGNOSTICS_DB: D1
  ADMIN_TOKEN?: string
  R2_ACCOUNT_ID?: string
  R2_ACCESS_KEY_ID?: string
  R2_SECRET_ACCESS_KEY?: string
  R2_BUCKET_NAME?: string
  LANDED_BYTES_CAP?: string
  INFLIGHT_BYTES_CAP?: string
  RETENTION_SECONDS?: string
  INCOMPLETE_SECONDS?: string
  MANIFEST_MAX?: string
  SUBTITLE_MAX?: string
  EXCERPT_MAX?: string
  ORIGINAL_MAX?: string
  RATE_PER_HOUR?: string
  PART_TTL_SECONDS?: string
  PART_BYTES?: string
}

function signer(env: Env, bucketName: string): Signer | null {
  if (!env.R2_ACCOUNT_ID || !env.R2_ACCESS_KEY_ID || !env.R2_SECRET_ACCESS_KEY) return null
  return {
    async sign(input) {
      const signed = await presignPut({
        accountId: env.R2_ACCOUNT_ID!,
        accessKeyId: env.R2_ACCESS_KEY_ID!,
        secretAccessKey: env.R2_SECRET_ACCESS_KEY!,
        bucket: bucketName,
        key: input.key,
        contentLength: input.contentLength,
        checksumSha256Base64: input.sha256Hex ? sha256Base64(input.sha256Hex) : undefined,
        expiresSeconds: Number(env.PART_TTL_SECONDS || 900),
        uploadId: input.uploadId,
        partNumber: input.partNumber,
      })
      return signed
    },
  }
}

function deps(env: Env): Deps {
  const bucketName = env.R2_BUCKET_NAME || 'autoclip-diagnostics'
  if (bucketName === 'autoclip-media') throw new Error('refusing_media_bucket')
  const bucket = env.DIAGNOSTICS_BUCKET
  if (!env.DIAGNOSTICS_DB) throw new Error('DIAGNOSTICS_DB missing')
  return {
    repo: new D1Repo(env.DIAGNOSTICS_DB, () => new Date().toISOString()),
    bucket: {
      put: (key, body) => bucket.put(key, body),
      head: (key) => bucket.head(key),
      delete: (key) => bucket.delete(key),
      createMultipartUpload: (key) => bucket.createMultipartUpload(key),
      listParts: (key, uploadId) => bucket.listParts(key, uploadId),
      abortMultipart: (key, uploadId) => bucket.abortMultipart(key, uploadId),
      list: async (prefix) => (await bucket.list({ prefix })).objects.map((object) => object.key),
    },
    limits: limitsFrom(env as Record<string, string | undefined>),
    now: () => new Date(),
    signer: signer(env, bucketName),
    adminToken: env.ADMIN_TOKEN || '',
    bucketName,
    partBytes: Number(env.PART_BYTES || 8 * 1024 * 1024),
  }
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    return handle(request, deps(env))
  },
  async scheduled(_event: unknown, env: Env): Promise<void> {
    await sweep(deps(env))
  },
}


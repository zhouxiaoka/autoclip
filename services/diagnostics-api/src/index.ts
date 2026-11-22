/**
 * Worker entry. This file does not create Cloudflare resources.
 * Bindings: DIAGNOSTICS_BUCKET (autoclip-diagnostics), DIAGNOSTICS_DB (autoclip-diagnostics-meta).
 * Object-storage signing secrets stay in Worker secrets, never in the desktop client.
 */
import type { R2Bucket, R2MultipartUpload, R2UploadedPart } from '@cloudflare/workers-types'
import { handle, sweep, type Bucket, type Deps, type MultipartUpload, type Signer } from './app.ts'
import { D1Repo, type D1 } from './d1.ts'
import { limitsFrom } from './quota.ts'
import { presignGet, presignHead, presignPut, sha256Base64 } from './sign.ts'

interface Env {
  DIAGNOSTICS_BUCKET: R2Bucket
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
      return presignPut({
        accountId: env.R2_ACCOUNT_ID!,
        accessKeyId: env.R2_ACCESS_KEY_ID!,
        secretAccessKey: env.R2_SECRET_ACCESS_KEY!,
        bucket: bucketName,
        key: input.key,
        contentLength: input.contentLength,
        checksumSha256Base64: input.sha256Hex ? sha256Base64(input.sha256Hex) : undefined,
        contentMd5Base64: input.contentMd5Base64,
        expiresSeconds: input.expiresSeconds || Number(env.PART_TTL_SECONDS || 900),
        uploadId: input.uploadId,
        partNumber: input.partNumber,
      })
    },
    signGet(key) {
      return presignGet({
        accountId: env.R2_ACCOUNT_ID!,
        accessKeyId: env.R2_ACCESS_KEY_ID!,
        secretAccessKey: env.R2_SECRET_ACCESS_KEY!,
        bucket: bucketName,
        key,
        expiresSeconds: 120,
      })
    },
    signHead(key) {
      return presignHead({
        accountId: env.R2_ACCOUNT_ID!,
        accessKeyId: env.R2_ACCESS_KEY_ID!,
        secretAccessKey: env.R2_SECRET_ACCESS_KEY!,
        bucket: bucketName,
        key,
        expiresSeconds: 120,
      })
    },
  }
}

function wrapUpload(upload: R2MultipartUpload): MultipartUpload {
  return {
    key: upload.key,
    uploadId: upload.uploadId,
    uploadPart: (partNumber, value) => upload.uploadPart(partNumber, value),
    abort: () => upload.abort(),
    complete: async (uploadedParts: R2UploadedPart[]) => {
      const assembled = await upload.complete(uploadedParts)
      return { size: assembled.size, httpEtag: assembled.httpEtag }
    },
  }
}

export function adaptBucket(bucket: R2Bucket): Bucket {
  return {
    put: async (key, body) => { await bucket.put(key, body) },
    head: async (key) => {
      const head = await bucket.head(key)
      return head ? { size: head.size } : null
    },
    delete: (key) => bucket.delete(key),
    createMultipartUpload: async (key) => wrapUpload(await bucket.createMultipartUpload(key)),
    resumeMultipartUpload: (key, uploadId) => wrapUpload(bucket.resumeMultipartUpload(key, uploadId)),
    list: async (prefix, uploadedBefore) => {
      const keys: string[] = []
      let cursor: string | undefined
      for (let page = 0; page < 1000; page += 1) {
        const listed = await bucket.list({ prefix, cursor, limit: 1000 })
        for (const object of listed.objects) {
          if (!uploadedBefore || object.uploaded < uploadedBefore) keys.push(object.key)
        }
        if (!listed.truncated) return keys
        if (!listed.cursor || listed.cursor === cursor) return keys
        cursor = listed.cursor
      }
      return keys
    },
  }
}

function deps(env: Env): Deps {
  const bucketName = env.R2_BUCKET_NAME || 'autoclip-diagnostics'
  if (bucketName === 'autoclip-media') throw new Error('refusing_media_bucket')
  if (!env.DIAGNOSTICS_DB) throw new Error('DIAGNOSTICS_DB missing')
  if (!env.DIAGNOSTICS_BUCKET) throw new Error('DIAGNOSTICS_BUCKET missing')
  return {
    repo: new D1Repo(env.DIAGNOSTICS_DB, () => new Date().toISOString()),
    bucket: adaptBucket(env.DIAGNOSTICS_BUCKET),
    limits: limitsFrom(env as unknown as Record<string, string | undefined>),
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

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { createHash } from 'node:crypto'
import { handle, sweep, type Bucket, type MultipartUpload, type UploadedPart } from '../src/app.ts'
import { MemoryRepo } from '../src/memory.ts'
import { PROPOSED_LIMITS, tryReserve } from '../src/quota.ts'
import { canonicalPut, presignPut } from '../src/sign.ts'

const sha = 'ab'.repeat(32)
const idem = 'cd'.repeat(32)

function manifest(extra: Record<string, unknown> = {}) {
  return {
    schema: 'autoclip.support_manifest/1',
    purpose: 'troubleshooting_and_product_improvement',
    not_for_training: true,
    consent_text_version: '2026-11-16.1',
    runtime: { app_version: '1.5.9', os: 'linux', arch: 'x86_64', runtime: 'python' },
    attempt: { attempt_id: `t-${'a'.repeat(32)}`, state: 'failed', error_code: 'timeout', failure_stage: 'analyze', sequence: 1 },
    run: { provider: 'deepseek', duration_ms: 10 },
    media_facts: {},
    log_lines: [],
    limits: { approval: 'pending' },
    ...extra,
  }
}

function etagOf(bytes: Uint8Array): string {
  return createHash('sha256').update(bytes).digest('hex')
}

class LocalBucket implements Bucket {
  objects = new Map<string, Uint8Array>()
  private uploads = new Map<string, { key: string; parts: Map<number, Uint8Array> }>()

  async put(key: string, body: Uint8Array): Promise<void> { this.objects.set(key, body) }
  async head(key: string) {
    const body = this.objects.get(key)
    return body ? { size: body.byteLength } : null
  }
  async get(key: string) {
    const body = this.objects.get(key)
    if (!body) return null
    return { size: body.byteLength, arrayBuffer: async () => body.buffer.slice(body.byteOffset, body.byteOffset + body.byteLength) }
  }
  async delete(key: string) { this.objects.delete(key) }
  async createMultipartUpload(key: string): Promise<MultipartUpload> {
    const uploadId = `up-${this.uploads.size + 1}-${key}`
    this.uploads.set(uploadId, { key, parts: new Map() })
    return this.resumeMultipartUpload(key, uploadId)
  }
  resumeMultipartUpload(key: string, uploadId: string): MultipartUpload {
    return {
      key,
      uploadId,
      uploadPart: async (partNumber, value) => {
        const upload = this.uploads.get(uploadId)
        if (!upload || upload.key !== key) throw new Error('unknown_upload')
        upload.parts.set(partNumber, value)
        return { partNumber, etag: etagOf(value) }
      },
      abort: async () => { this.uploads.delete(uploadId) },
      complete: async (uploadedParts: UploadedPart[]) => {
        const upload = this.uploads.get(uploadId)
        if (!upload || upload.key !== key) throw new Error('unknown_upload')
        const ordered = [...uploadedParts].sort((left, right) => left.partNumber - right.partNumber)
        const chunks: Uint8Array[] = []
        let expect = 1
        for (const part of ordered) {
          if (part.partNumber !== expect) throw new Error('missing_part')
          const stored = upload.parts.get(part.partNumber)
          if (!stored || etagOf(stored) !== part.etag) throw new Error('etag_mismatch')
          chunks.push(stored)
          expect += 1
        }
        if (upload.parts.size !== ordered.length) throw new Error('missing_part')
        const size = chunks.reduce((sum, chunk) => sum + chunk.byteLength, 0)
        const body = new Uint8Array(size)
        let offset = 0
        for (const chunk of chunks) {
          body.set(chunk, offset)
          offset += chunk.byteLength
        }
        this.objects.set(key, body)
        this.uploads.delete(uploadId)
        return { size, httpEtag: etagOf(body) }
      },
    }
  }
  async list() { return [...this.objects.keys()] }
}

function deps(over: Partial<Parameters<typeof handle>[1]> = {}) {
  const signed: { key: string; contentLength: number }[] = []
  const bucket = new LocalBucket()
  const repo = new MemoryRepo()
  const value = {
    repo, bucket, limits: { ...PROPOSED_LIMITS, ratePerHour: 20 }, now: () => new Date('2026-11-16T00:00:00Z'),
    signer: {
      async sign(input: { key: string; contentLength: number }) {
        signed.push(input)
        return { url: `https://account.r2.cloudflarestorage.com/autoclip-diagnostics/${input.key}?X-Amz-Expires=900`, headers: { 'content-length': String(input.contentLength) } }
      },
    },
    adminToken: 'admin-secret', bucketName: 'autoclip-diagnostics', partBytes: 8 * 1024 * 1024,
    ...over,
  }
  return { deps: value, signed, bucket, repo }
}

async function create(depsValue: Parameters<typeof handle>[1], body: unknown, key = idem) {
  return handle(new Request('https://diagnostics.example/v1/cases', {
    method: 'POST', headers: { 'content-type': 'application/json', 'idempotency-key': key },
    body: JSON.stringify(body),
  }), depsValue)
}

test('conditional reserve rejects concurrent over-cap requests', async () => {
  const repo = new MemoryRepo()
  const limits = { landedCap: 1000, inflightCap: 1000 }
  const results = await Promise.all([0, 1, 2, 3].map(() => repo.reserve(400, limits)))
  assert.equal(results.filter((row) => row.ok).length, 2)
  assert.equal(repo.snapshot().reserved, 800)
  assert.equal(tryReserve({ landed: 3_000_000_000, reserved: 0 }, 2_000_000_000, PROPOSED_LIMITS).ok, false)
})

test('manifest with a secret or path is rejected before reserve', async () => {
  const { deps: value, repo } = deps()
  const response = await create(value, { purpose: 'troubleshooting_and_product_improvement', not_for_training: true, manifest: manifest({ api_key: 'sk-secret' }), files: [] })
  assert.equal(response.status, 422)
  assert.equal(repo.snapshot().reserved, 0)
})

test('file upload reserves exact bytes and rejects a size mismatch', async () => {
  const { deps: value, signed, bucket, repo } = deps()
  const response = await create(value, {
    purpose: 'troubleshooting_and_product_improvement', not_for_training: true, consent_version: '2026-11-16.1',
    manifest: manifest(), files: [{ role: 'excerpt', bytes: 1000, sha256: sha }],
  })
  assert.equal(response.status, 201)
  const body = await response.json() as { case_id: string; capability: string; uploads: { object_id: string }[] }
  assert.equal(signed[0]?.contentLength, 1000)
  assert.equal(repo.snapshot().reserved, 1000)
  bucket.objects.set(signed[0]!.key, new Uint8Array(1001))
  const mismatch = await handle(new Request(`https://diagnostics.example/v1/cases/${body.case_id}/files/${body.uploads[0]!.object_id}/complete`, {
    method: 'POST', headers: { authorization: `Bearer ${body.capability}` }, body: '{}',
  }), value)
  assert.equal(mismatch.status, 409)
  assert.equal(repo.snapshot().reserved, 0)
  assert.equal(repo.snapshot().landed > 0, true)
})

test('matching bytes land once and a repeated idempotency key does not reserve again', async () => {
  const { deps: value, signed, bucket, repo } = deps()
  const payload = { purpose: 'troubleshooting_and_product_improvement', not_for_training: true, manifest: manifest(), files: [{ role: 'excerpt', bytes: 40, sha256: sha }] }
  const first = await create(value, payload)
  const created = await first.json() as { case_id: string; capability: string; uploads: { object_id: string }[] }
  const landedAfterManifest = repo.snapshot().landed
  bucket.objects.set(signed[0]!.key, new Uint8Array(40))
  const done = await handle(new Request(`https://diagnostics.example/v1/cases/${created.case_id}/files/${created.uploads[0]!.object_id}/complete`, {
    method: 'POST', headers: { authorization: `Bearer ${created.capability}` }, body: '{}',
  }), value)
  assert.equal(done.status, 200)
  assert.equal(repo.snapshot().reserved, 0)
  assert.equal(repo.snapshot().landed, landedAfterManifest + 40)
  const again = await create(value, payload)
  assert.equal(again.status, 200)
  assert.equal(repo.snapshot().landed, landedAfterManifest + 40)
})

test('delete requires the case capability and releases landed bytes', async () => {
  const { deps: value, repo } = deps()
  const created = await (await create(value, { purpose: 'troubleshooting_and_product_improvement', not_for_training: true, manifest: manifest(), files: [] })).json() as { case_id: string; capability: string }
  const denied = await handle(new Request(`https://diagnostics.example/v1/cases/${created.case_id}`, { method: 'DELETE', headers: { authorization: 'Bearer nope' } }), value)
  assert.equal(denied.status, 404)
  const removed = await handle(new Request(`https://diagnostics.example/v1/cases/${created.case_id}`, { method: 'DELETE', headers: { authorization: `Bearer ${created.capability}` } }), value)
  assert.equal(removed.status, 200)
  assert.equal(repo.snapshot().landed, 0)
})

test('rate limit, missing signer and admin reconcile', async () => {
  const { deps: value } = deps({ limits: { ...PROPOSED_LIMITS, ratePerHour: 1 } })
  const body = { purpose: 'troubleshooting_and_product_improvement', not_for_training: true, manifest: manifest(), files: [] }
  assert.equal((await create(value, body, '11'.repeat(32))).status, 201)
  assert.equal((await create(value, body, '22'.repeat(32))).status, 429)
  const unsigned = deps({ signer: null })
  const refused = await create(unsigned.deps, { ...body, files: [{ role: 'original', bytes: 10, sha256: sha }] }, '33'.repeat(32))
  assert.equal(refused.status, 503)
  const admin = await handle(new Request('https://diagnostics.example/admin/quota', { headers: { authorization: 'Bearer admin-secret' } }), value)
  assert.equal(admin.status, 200)
  const stranger = await handle(new Request('https://diagnostics.example/admin/reconcile', { method: 'POST', headers: { authorization: 'Bearer no' } }), value)
  assert.equal(stranger.status, 401)
})

test('sweep aborts an incomplete upload and deletes orphans under cases/', async () => {
  const { deps: value, bucket, repo } = deps({ limits: { ...PROPOSED_LIMITS, incompleteSeconds: 10, retentionSeconds: 100 } })
  value.now = () => new Date('2026-11-16T00:00:00Z')
  await create(value, { purpose: 'troubleshooting_and_product_improvement', not_for_training: true, manifest: manifest(), files: [{ role: 'excerpt', bytes: 8, sha256: sha }] })
  bucket.objects.set('cases/orphan/file', new Uint8Array(4))
  value.now = () => new Date('2026-11-16T00:01:00Z')
  const result = await sweep(value)
  assert.equal(result.aborted + result.expired > 0, true)
  assert.equal(result.orphans.includes('cases/orphan/file'), true)
  assert.equal(bucket.objects.has('cases/orphan/file'), false)
  assert.equal(repo.snapshot().reserved, 0)
})

test('presign covers content-length and refuses the media bucket', async () => {
  const left = canonicalPut({ accountId: 'acc', accessKeyId: 'key', secretAccessKey: 'secret', bucket: 'autoclip-diagnostics', key: 'cases/a/excerpt', contentLength: 10, expiresSeconds: 900, now: new Date('2026-11-16T00:00:00Z') })
  const right = canonicalPut({ accountId: 'acc', accessKeyId: 'key', secretAccessKey: 'secret', bucket: 'autoclip-diagnostics', key: 'cases/a/excerpt', contentLength: 11, expiresSeconds: 900, now: new Date('2026-11-16T00:00:00Z') })
  assert.match(left.canonical, /content-length:10/)
  assert.notEqual(left.canonical, right.canonical)
  const signed = await presignPut({ accountId: 'acc', accessKeyId: 'key', secretAccessKey: 'secret', bucket: 'autoclip-diagnostics', key: 'cases/a/excerpt', contentLength: 10, expiresSeconds: 900, now: new Date('2026-11-16T00:00:00Z') })
  assert.match(signed.url, /X-Amz-Signature=/)
  await assert.rejects(() => presignPut({ accountId: 'acc', accessKeyId: 'key', secretAccessKey: 'secret', bucket: 'autoclip-media', key: 'x', contentLength: 1, expiresSeconds: 60 }))
})

test('multipart completion assembles the readable object and a bad etag leaves nothing', async () => {
  const { deps: value, bucket, repo } = deps({ partBytes: 4 })
  const created = await (await create(value, {
    purpose: 'troubleshooting_and_product_improvement', not_for_training: true,
    manifest: manifest(), files: [{ role: 'excerpt', bytes: 6, sha256: sha }],
  })).json() as { case_id: string; capability: string; uploads: { object_id: string }[] }
  const stored = [...repo.objects.values()][0]!
  assert.ok(stored.uploadId)
  const handle = bucket.resumeMultipartUpload(stored.r2Key, stored.uploadId)
  const first = await handle.uploadPart(1, Uint8Array.from([1, 2, 3, 4]))
  const second = await handle.uploadPart(2, Uint8Array.from([5, 6]))
  const bad = await handleRequest(value, created, { parts: [{ partNumber: 1, etag: 'not-the-etag' }, second] })
  assert.equal(bad.status, 409)
  assert.equal(await bucket.get(stored.r2Key), null)

  const { deps: again, bucket: goodBucket, repo: goodRepo } = deps({ partBytes: 4 })
  const secondCase = await (await create(again, {
    purpose: 'troubleshooting_and_product_improvement', not_for_training: true,
    manifest: manifest(), files: [{ role: 'excerpt', bytes: 6, sha256: sha }],
  }, 'ee'.repeat(32))).json() as { case_id: string; capability: string; uploads: { object_id: string }[] }
  const good = [...goodRepo.objects.values()][0]!
  const upload = goodBucket.resumeMultipartUpload(good.r2Key, good.uploadId!)
  const partA = await upload.uploadPart(1, Uint8Array.from([1, 2, 3, 4]))
  const partB = await upload.uploadPart(2, Uint8Array.from([5, 6]))
  const done = await handleRequest(again, secondCase, { parts: [partA, partB] })
  assert.equal(done.status, 200)
  assert.equal((await done.json() as { bytes: number }).bytes, 6)
  const readable = await goodBucket.get(good.r2Key)
  assert.deepEqual([...(new Uint8Array(await readable!.arrayBuffer()))], [1, 2, 3, 4, 5, 6])
})

test('a lost create response is recovered with a new capability and the same plan', async () => {
  const { deps: value, repo } = deps()
  const payload = { purpose: 'troubleshooting_and_product_improvement', not_for_training: true, manifest: manifest(), files: [{ role: 'excerpt', bytes: 40, sha256: sha }] }
  const first = await (await create(value, payload)).json() as { case_id: string; capability: string; uploads: { parts: unknown[] }[] }
  const reserved = repo.snapshot().reserved
  const replay = await (await create(value, payload)).json() as { case_id: string; capability: string; uploads: { parts: { length: number }[]; object_id: string }[] }
  assert.equal(replay.case_id, first.case_id)
  assert.notEqual(replay.capability, first.capability)
  assert.equal(replay.uploads[0]?.parts.length, 1)
  assert.equal(replay.uploads[0]?.parts[0]?.length, 40)
  assert.equal(repo.snapshot().reserved, reserved)
  const stale = await handleRequest(value, { ...first, uploads: [{ object_id: replay.uploads[0]!.object_id }] }, {})
  assert.equal(stale.status, 404)
  const row = [...repo.objects.values()][0]!
  row.partPlan = []
  const broken = await create(value, payload)
  assert.equal(broken.status, 409)
})

test('canonical query sorts multipart names by unsigned byte order', async () => {
  const input = {
    accountId: 'acc', accessKeyId: 'key', secretAccessKey: 'secret', bucket: 'autoclip-diagnostics',
    key: 'cases/a/excerpt', contentLength: 10, expiresSeconds: 900, now: new Date('2026-11-16T00:00:00Z'),
    uploadId: 'id/a+b*', partNumber: 2,
  }
  const { canonical } = canonicalPut(input)
  const query = canonical.split('\n')[2]
  assert.equal(query, 'X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=key%2F20261116%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20261116T000000Z&X-Amz-Expires=900&X-Amz-SignedHeaders=content-length%3Bhost&partNumber=2&uploadId=id%2Fa%2Bb%2A')
  assert.ok(query.indexOf('X-Amz-Algorithm') < query.indexOf('partNumber'))
  assert.ok(query.indexOf('partNumber') < query.indexOf('uploadId'))
  const signed = await presignPut(input)
  assert.match(signed.url, /X-Amz-Signature=d8447a28b8d270a0390dac9d81f7069231c97b395aa3065770e20f5f51b23220$/)
})

function handleRequest(depsValue: Parameters<typeof handle>[1], created: { case_id: string; capability: string; uploads: { object_id: string }[] }, body: unknown) {
  return handle(new Request(`https://diagnostics.example/v1/cases/${created.case_id}/files/${created.uploads[0]!.object_id}/complete`, {
    method: 'POST', headers: { authorization: `Bearer ${created.capability}`, 'content-type': 'application/json' },
    body: JSON.stringify(body),
  }), depsValue)
}

test('migration states the conditional reservation and does not name the media bucket', () => {
  const sql = readFileSync(new URL('../migrations/0001_init.sql', import.meta.url), 'utf8')
  const reserve = readFileSync(new URL('../src/d1.ts', import.meta.url), 'utf8')
  const config = readFileSync(new URL('../wrangler.jsonc', import.meta.url), 'utf8')
  assert.match(reserve, /landed_bytes \+ reserved_bytes \+ \?1 <= \?3/)
  assert.match(config, /"bucket_name": "autoclip-diagnostics"/)
  assert.doesNotMatch(config, /"bucket_name": "autoclip-media"/)
  assert.doesNotMatch(sql, /autoclip-media/)
  const source = readFileSync(new URL('../src/app.ts', import.meta.url), 'utf8')
  assert.doesNotMatch(source, /fetch\(/)
})

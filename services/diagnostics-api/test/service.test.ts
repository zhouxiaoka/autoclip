import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { createHash } from 'node:crypto'
import { handle, sweep, type Bucket, type MultipartUpload, type UploadedPart } from '../src/app.ts'
import { adaptBucket } from '../src/index.ts'
import { MemoryRepo } from '../src/memory.ts'
import { PROPOSED_LIMITS, tryReserve } from '../src/quota.ts'
import { canonicalPut, presignPut } from '../src/sign.ts'

const sha = 'ab'.repeat(32)
const idem = 'cd'.repeat(32)
const partMd5 = createHash('md5').update('part').digest('base64')
const twoPartMd5 = [partMd5, partMd5]

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
  overlay = new Map<string, number>()
  private uploads = new Map<string, { key: string; parts: Map<number, Uint8Array> }>()
  completeAttempts = 0
  bodyReads = 0
  forbidBody = false
  throwNextExistingHead = false
  completeError: Error | null = null

  async put(key: string, body: Uint8Array): Promise<void> { this.objects.set(key, body) }
  async head(key: string) {
    const present = this.objects.has(key) || this.overlay.has(key)
    if (present && this.throwNextExistingHead) {
      this.throwNextExistingHead = false
      throw new Error('head_unavailable')
    }
    if (this.overlay.has(key)) return { size: this.overlay.get(key)! }
    const body = this.objects.get(key)
    return body ? { size: body.byteLength } : null
  }
  async get(key: string) {
    this.bodyReads += 1
    if (this.forbidBody) throw new Error('full_body_forbidden')
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
        if (this.completeError) throw this.completeError
        this.completeAttempts += 1
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
      async sign(input: { key: string; contentLength: number; contentMd5Base64?: string }) {
        signed.push(input)
        const headers: Record<string, string> = { 'content-length': String(input.contentLength) }
        if (input.contentMd5Base64) headers['content-md5'] = input.contentMd5Base64
        return { url: `https://account.r2.cloudflarestorage.com/autoclip-diagnostics/${input.key}?X-Amz-Expires=900`, headers }
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

test('a read url is issued only for the owned object and contains no signing secret', async () => {
  const issued: string[] = []
  const base = deps()
  base.deps.signer = {
    async sign(input) {
      base.signed.push(input)
      return { url: 'https://account.r2.cloudflarestorage.com/autoclip-diagnostics/x', headers: { 'content-length': String(input.contentLength) } }
    },
    async signGet(key) {
      issued.push(key)
      return `https://account.r2.cloudflarestorage.com/autoclip-diagnostics/${key}?X-Amz-Signature=abc`
    },
    async signHead(key) {
      issued.push(`head:${key}`)
      return `https://account.r2.cloudflarestorage.com/autoclip-diagnostics/${key}?X-Amz-Signature=head`
    },
  }
  const created = await (await create(base.deps, {
    purpose: 'troubleshooting_and_product_improvement', not_for_training: true, manifest: manifest(),
    files: [{ role: 'excerpt', bytes: 40, sha256: sha }],
  })).json() as { case_id: string; capability: string; uploads: { object_id: string }[] }
  base.bucket.objects.set(base.signed[0]!.key, new Uint8Array(40))
  await handle(new Request(`https://diagnostics.example/v1/cases/${created.case_id}/files/${created.uploads[0]!.object_id}/complete`, {
    method: 'POST', headers: { authorization: `Bearer ${created.capability}` }, body: '{}',
  }), base.deps)
  const denied = await handle(new Request(`https://diagnostics.example/v1/cases/${created.case_id}/files/${created.uploads[0]!.object_id}/read-url`, { method: 'POST' }), base.deps)
  assert.equal(denied.status, 404)
  const allowed = await handle(new Request(`https://diagnostics.example/v1/cases/${created.case_id}/files/${created.uploads[0]!.object_id}/read-url`, {
    method: 'POST', headers: { authorization: `Bearer ${created.capability}` },
  }), base.deps)
  const body = await allowed.json() as { url: string; head_url: string; expires_in: number }
  assert.equal(allowed.status, 200)
  assert.equal(body.expires_in, 120)
  assert.equal(body.url.includes('secret'), false)
  assert.notEqual(body.head_url, body.url)
  assert.equal(body.head_url.includes('secret'), false)
  assert.deepEqual(issued, [base.signed[0]!.key, `head:${base.signed[0]!.key}`])
  base.deps.signer = { async sign() { return { url: 'https://account.r2.cloudflarestorage.com/x', headers: {} } } }
  const unconfigured = await handle(new Request(`https://diagnostics.example/v1/cases/${created.case_id}/files/${created.uploads[0]!.object_id}/read-url`, {
    method: 'POST', headers: { authorization: `Bearer ${created.capability}` },
  }), base.deps)
  assert.equal(unconfigured.status, 503)
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
    manifest: manifest(), files: [{ role: 'excerpt', bytes: 6, sha256: sha, part_md5s: twoPartMd5 }],
  })).json() as { case_id: string; capability: string; uploads: { object_id: string }[] }
  const stored = [...repo.objects.values()][0]!
  assert.ok(stored.uploadId)
  const handle = bucket.resumeMultipartUpload(stored.r2Key, stored.uploadId)
  const first = await handle.uploadPart(1, Uint8Array.from([1, 2, 3, 4]))
  const second = await handle.uploadPart(2, Uint8Array.from([5, 6]))
  const bad = await handleRequest(value, created, { parts: [{ partNumber: 1, etag: 'not-the-etag' }, second] })
  assert.equal(bad.status, 409)
  const badBody = await bad.json() as { error: string; phase: string; expectedBytes: number; actualBytes: number | null }
  assert.equal(badBody.error, 'etag_mismatch')
  assert.equal(badBody.phase, 'complete')
  assert.equal(badBody.expectedBytes, 6)
  assert.equal(badBody.actualBytes, null)
  assert.equal(await bucket.get(stored.r2Key), null)

  const { deps: again, bucket: goodBucket, repo: goodRepo } = deps({ partBytes: 4 })
  const secondCase = await (await create(again, {
    purpose: 'troubleshooting_and_product_improvement', not_for_training: true,
    manifest: manifest(), files: [{ role: 'excerpt', bytes: 6, sha256: sha, part_md5s: twoPartMd5 }],
  }, 'ee'.repeat(32))).json() as { case_id: string; capability: string; uploads: { object_id: string }[] }
  const good = [...goodRepo.objects.values()][0]!
  const upload = goodBucket.resumeMultipartUpload(good.r2Key, good.uploadId!)
  const partA = await upload.uploadPart(1, Uint8Array.from([1, 2, 3, 4]))
  const partB = await upload.uploadPart(2, Uint8Array.from([5, 6]))
  const done = await handleRequest(again, secondCase, { parts: [
    { partNumber: partA.partNumber, etag: `"${partA.etag}"` },
    { partNumber: partB.partNumber, etag: `"${partB.etag}"` },
  ] })
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

test('completion uses metadata size for a large object and does not read its body', async () => {
  const { deps: value, bucket, repo } = deps()
  bucket.forbidBody = true
  const declared = 200 * 1024 * 1024
  const response = await create(value, {
    purpose: 'troubleshooting_and_product_improvement', not_for_training: true,
    manifest: manifest(), files: [{ role: 'excerpt', bytes: declared, sha256: sha, part_md5s: Array.from({ length: 25 }, () => partMd5) }],
  })
  assert.equal(response.status, 201)
  const created = await response.json() as { case_id: string; capability: string; uploads: { object_id: string }[]; checksum_note: string }
  assert.match(created.checksum_note, /does not read the body/)
  assert.match(created.checksum_note, /does not verify a content hash/)
  const object = [...repo.objects.values()][0]!
  bucket.overlay.set(object.r2Key, declared)
  const done = await handleRequest(value, created, {})
  assert.equal(done.status, 200)
  const payload = await done.json() as { bytes: number; integrity: string }
  assert.equal(payload.bytes, declared)
  assert.equal(payload.integrity, 'metadata_size')
  assert.equal(bucket.bodyReads, 0)

  const huge = deps({
    partBytes: 3 * 1024 * 1024 * 1024,
    limits: { ...PROPOSED_LIMITS, ratePerHour: 20, landedCap: 5 * 1024 * 1024 * 1024, inflightCap: 3 * 1024 * 1024 * 1024 },
  })
  huge.bucket.forbidBody = true
  const original = 2 * 1024 * 1024 * 1024
  const opened = await create(huge.deps, {
    purpose: 'troubleshooting_and_product_improvement', not_for_training: true,
    manifest: manifest(), files: [{ role: 'original', bytes: original, sha256: sha }],
  }, 'a1'.repeat(32))
  assert.equal(opened.status, 201)
  const hugeCase = await opened.json() as { case_id: string; capability: string; uploads: { object_id: string }[] }
  const hugeObject = [...huge.repo.objects.values()][0]!
  huge.bucket.overlay.set(hugeObject.r2Key, original)
  const finished = await handleRequest(huge.deps, hugeCase, {})
  assert.equal(finished.status, 200)
  assert.equal((await finished.json() as { bytes: number }).bytes, original)
  assert.equal(huge.bucket.bodyReads, 0)
})

test('assembly then a transient head or commit failure retries without deleting the object', async () => {
  const { deps: value, bucket, repo } = deps({ partBytes: 4 })
  const created = await (await create(value, {
    purpose: 'troubleshooting_and_product_improvement', not_for_training: true,
    manifest: manifest(), files: [{ role: 'excerpt', bytes: 6, sha256: sha, part_md5s: twoPartMd5 }],
  })).json() as { case_id: string; capability: string; uploads: { object_id: string }[] }
  const stored = [...repo.objects.values()][0]!
  const upload = bucket.resumeMultipartUpload(stored.r2Key, stored.uploadId!)
  const partA = await upload.uploadPart(1, Uint8Array.from([1, 2, 3, 4]))
  const partB = await upload.uploadPart(2, Uint8Array.from([5, 6]))
  const parts = { parts: [partA, partB] }
  bucket.throwNextExistingHead = true
  const paused = await handleRequest(value, created, parts)
  assert.equal(paused.status, 503)
  assert.equal((await paused.json() as { phase?: string }).phase, 'verify')
  assert.equal(bucket.completeAttempts, 1)
  assert.equal((await repo.getObject(stored.objectId))?.state, 'reserved')
  const body = await bucket.get(stored.r2Key)
  assert.deepEqual([...(new Uint8Array(await body!.arrayBuffer()))], [1, 2, 3, 4, 5, 6])
  const before = repo.snapshot()
  const resumed = await handleRequest(value, created, parts)
  assert.equal(resumed.status, 200)
  assert.equal((await resumed.json() as { bytes: number }).bytes, 6)
  assert.equal(bucket.completeAttempts, 1)
  assert.equal(repo.snapshot().landed, before.landed + 6)
  assert.equal(repo.snapshot().reserved, 0)
  const repeated = await handleRequest(value, created, parts)
  assert.equal(repeated.status, 200)
  assert.equal(repo.snapshot().landed, before.landed + 6)
  assert.deepEqual([...(new Uint8Array(await (await bucket.get(stored.r2Key))!.arrayBuffer()))], [1, 2, 3, 4, 5, 6])

  const again = deps({ partBytes: 4 })
  const second = await (await create(again.deps, {
    purpose: 'troubleshooting_and_product_improvement', not_for_training: true,
    manifest: manifest(), files: [{ role: 'excerpt', bytes: 6, sha256: sha, part_md5s: twoPartMd5 }],
  }, 'b2'.repeat(32))).json() as { case_id: string; capability: string; uploads: { object_id: string }[] }
  const row = [...again.repo.objects.values()][0]!
  const handle = again.bucket.resumeMultipartUpload(row.r2Key, row.uploadId!)
  const left = await handle.uploadPart(1, Uint8Array.from([1, 2, 3, 4]))
  const right = await handle.uploadPart(2, Uint8Array.from([5, 6]))
  const real = again.repo.commitFile.bind(again.repo)
  let bombs = 1
  again.repo.commitFile = async (...args) => {
    if (bombs > 0) { bombs -= 1; throw new Error('d1_unavailable') }
    return real(...args)
  }
  const failedCommit = await handleRequest(again.deps, second, { parts: [left, right] })
  assert.equal(failedCommit.status, 503)
  assert.equal(again.bucket.completeAttempts, 1)
  assert.notEqual(await again.bucket.get(row.r2Key), null)
  assert.equal((await again.repo.getObject(row.objectId))?.state, 'reserved')
  const recovered = await handleRequest(again.deps, second, { parts: [left, right] })
  assert.equal(recovered.status, 200)
  assert.equal(again.bucket.completeAttempts, 1)
  const landed = again.repo.snapshot().landed
  const caseRow = await again.repo.getCase(second.case_id)
  assert.ok(caseRow)
  caseRow!.state = 'deleted'
  await again.repo.saveCase(caseRow!)
  const removed = await handleRequest(again.deps, second, { parts: [left, right] })
  assert.equal(removed.status, 404)
  assert.notEqual(await again.bucket.get(row.r2Key), null)
  assert.equal(again.repo.snapshot().landed, landed)
})

test('an unrecognized complete failure stays retryable and names its phase', async () => {
  const { deps: value, bucket, repo } = deps({ partBytes: 4 })
  const created = await (await create(value, {
    purpose: 'troubleshooting_and_product_improvement', not_for_training: true,
    manifest: manifest(), files: [{ role: 'excerpt', bytes: 6, sha256: sha, part_md5s: twoPartMd5 }],
  })).json() as { case_id: string; capability: string; uploads: { object_id: string }[] }
  const stored = [...repo.objects.values()][0]!
  bucket.completeError = new Error('storage backend unavailable')
  const response = await handleRequest(value, created, { parts: [{ partNumber: 1, etag: 'a' }, { partNumber: 2, etag: 'b' }] })
  assert.equal(response.status, 503)
  const body = await response.json() as { phase?: string; detail?: string }
  assert.equal(body.phase, 'complete')
  assert.equal(body.detail, 'storage backend unavailable')
  assert.equal((await repo.getObject(stored.objectId))?.state, 'reserved')
  assert.equal(await bucket.get(stored.r2Key), null)
})

test('exact 2GiB plus the manifest stays over the frozen in-flight cap after the excerpt is released', async () => {
  const frozen = 2147483648
  const { deps: value, repo } = deps()
  value.limits = { ...value.limits, inflightCap: frozen, landedCap: 4294967296 }
  const excerpt = 200 * 1024 * 1024
  const opened = await create(value, {
    purpose: 'troubleshooting_and_product_improvement', not_for_training: true,
    manifest: manifest(), files: [{ role: 'excerpt', bytes: excerpt, sha256: sha, part_md5s: Array.from({ length: 25 }, () => partMd5) }],
  })
  assert.equal(opened.status, 201)
  const created = await opened.json() as { case_id: string; capability: string }
  assert.equal(repo.snapshot().reserved, excerpt)
  const original = 2147483648
  const blocked = await create(value, {
    purpose: 'troubleshooting_and_product_improvement', not_for_training: true,
    manifest: manifest(), files: [{ role: 'original', bytes: original, sha256: sha, part_md5s: Array.from({ length: 256 }, () => partMd5) }],
  }, 'd4'.repeat(32))
  assert.equal(blocked.status, 413)
  assert.equal((await blocked.json() as { error: string }).error, 'inflight_cap')
  const removed = await handle(new Request(`https://diagnostics.example/v1/cases/${created.case_id}`, {
    method: 'DELETE', headers: { authorization: `Bearer ${created.capability}` },
  }), value)
  assert.equal(removed.status, 200)
  assert.equal(repo.snapshot().reserved, 0)
  const still = await create(value, {
    purpose: 'troubleshooting_and_product_improvement', not_for_training: true,
    manifest: manifest(), files: [{ role: 'original', bytes: original, sha256: sha, part_md5s: Array.from({ length: 256 }, () => partMd5) }],
  }, 'd5'.repeat(32))
  assert.equal(still.status, 413)
  const manifestBytes = Buffer.byteLength(JSON.stringify(manifest()))
  const fitting = frozen - manifestBytes
  const partCount = Math.ceil(fitting / (8 * 1024 * 1024))
  const allowed = await create(value, {
    purpose: 'troubleshooting_and_product_improvement', not_for_training: true,
    manifest: manifest(), files: [{ role: 'original', bytes: fitting, sha256: sha, part_md5s: Array.from({ length: partCount }, () => partMd5) }],
  }, 'd6'.repeat(32))
  assert.equal(allowed.status, 201)
  assert.equal(PROPOSED_LIMITS.inflightCap, 2147483648)
})

test('listing follows every truncated page and does not stop after the first', async () => {
  const pages = [
    { objects: [{ key: 'cases/a' }], truncated: true, cursor: 'next' },
    { objects: [{ key: 'cases/b' }], truncated: false, cursor: undefined },
  ]
  const bucket = {
    list: async (options: { cursor?: string }) => pages[options.cursor ? 1 : 0],
  }
  const keys = await adaptBucket(bucket as never).list('cases/')
  assert.deepEqual(keys, ['cases/a', 'cases/b'])
})

test('migration states the conditional reservation and does not name the media bucket', () => {
  const sql = readFileSync(new URL('../migrations/0001_init.sql', import.meta.url), 'utf8')
  const reserve = readFileSync(new URL('../src/d1.ts', import.meta.url), 'utf8')
  const config = readFileSync(new URL('../wrangler.jsonc', import.meta.url), 'utf8')
  assert.match(reserve, /landed_bytes \+ reserved_bytes \+ \?1 <= \?3/)
  assert.match(config, /"bucket_name": "autoclip-diagnostics"/)
  assert.match(config, /"INFLIGHT_BYTES_CAP": "2147483648"/)
  assert.doesNotMatch(config, /"bucket_name": "autoclip-media"/)
  assert.doesNotMatch(sql, /autoclip-media/)
  const source = readFileSync(new URL('../src/app.ts', import.meta.url), 'utf8')
  assert.doesNotMatch(source, /fetch\(/)
  const adapter = readFileSync(new URL('../src/index.ts', import.meta.url), 'utf8')
  assert.match(adapter, /head\.size/)
  assert.doesNotMatch(adapter, /arrayBuffer/)
  assert.doesNotMatch(source, /bucket\.get\(|stored\.arrayBuffer|object\.arrayBuffer/)
})

test('a case created while the bucket listing is in flight survives the sweep', async () => {
  const { deps: value, bucket } = deps()
  const list = bucket.list.bind(bucket)
  let manifestKey = ''
  bucket.list = async () => {
    const created = await create(value, {
      purpose: 'troubleshooting_and_product_improvement', not_for_training: true,
      manifest: manifest(), files: [],
    })
    assert.equal(created.status, 201)
    manifestKey = `cases/${(await created.json()).case_id}/manifest.json`
    return list()
  }
  const { orphans } = await sweep(value)
  assert.ok(bucket.objects.has(manifestKey))
  assert.ok(!orphans.includes(manifestKey))
})

test('orphan cleanup only considers objects known to predate its grace period', async () => {
  const cutoff = new Date('2026-11-16T00:00:00Z')
  const objects = [
    { key: 'cases/old', uploaded: new Date(cutoff.getTime() - 1) },
    { key: 'cases/new', uploaded: cutoff },
    { key: 'cases/unknown' },
  ]
  const bucket = adaptBucket({ list: async () => ({ objects, truncated: false }) } as never)
  assert.deepEqual(await bucket.list('cases/', cutoff), ['cases/old'])
})

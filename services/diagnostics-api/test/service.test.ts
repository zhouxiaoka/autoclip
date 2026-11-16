import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { handle, sweep, type Bucket } from '../src/app.ts'
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

class FakeBucket implements Bucket {
  objects = new Map<string, number>()
  parts = new Map<string, number[]>()
  async put(key: string, body: Uint8Array): Promise<void> { this.objects.set(key, body.byteLength) }
  async head(key: string) { return this.objects.has(key) ? { size: this.objects.get(key)! } : null }
  async delete(key: string) { this.objects.delete(key) }
  async createMultipartUpload(key: string) {
    this.parts.set(key, [])
    return { uploadId: `up-${key}` }
  }
  async listParts(key: string) { return this.parts.get(key) ?? [] }
  async abortMultipart(key: string) { this.parts.delete(key) }
  async list() { return [...this.objects.keys()] }
}

function deps(over: Partial<Parameters<typeof handle>[1]> = {}) {
  const signed: { key: string; contentLength: number }[] = []
  const bucket = new FakeBucket()
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
  bucket.objects.set(signed[0]!.key, 1001)
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
  bucket.objects.set(signed[0]!.key, 40)
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
  bucket.objects.set('cases/orphan/file', 4)
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

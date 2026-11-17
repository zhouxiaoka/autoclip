import assert from 'node:assert/strict'
import { mkdtempSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'
import { presignGet, presignPut } from '../src/sign.ts'
import { armed, assertStagingTarget, createEvidenceStore, executeLive, exitCode, main, multipartPartHeaders, planUploads, productionHeaders, sendPart, waitForExpiry, BUDGET_BYTES, REQUIRED_LIVE_CASES } from '../live/harness.mjs'

const secret = { accountId: 'acc', accessKeyId: 'key', secretAccessKey: 'secret', bucket: 'autoclip-diagnostics-validation', key: 'cases/a/excerpt', contentLength: 64, expiresSeconds: 900, now: new Date('2026-11-17T00:00:00Z') }

test('the live harness does not run or claim validation without both approval flags', async () => {
  const result = await main({ AUTOCLIP_DIAGNOSTICS_LIVE: '1' })
  assert.equal(result.status, 'not-run')
  assert.equal(armed({}), false)
  assert.equal(result.liveValidationClaimed, undefined)
})

test('production PUT headers are only length and the single-part checksum', async () => {
  const digest = 'ab'.repeat(32)
  const single = await presignPut({ ...secret, checksumSha256Base64: Buffer.from(digest, 'hex').toString('base64') })
  assert.equal(productionHeaders(single.headers), true)
  assert.equal(single.headers['x-amz-checksum-sha256'], Buffer.from(digest, 'hex').toString('base64'))
  assert.equal('content-md5' in single.headers, false)
  const part = await presignPut({ ...secret, uploadId: 'up', partNumber: 1, contentMd5Base64: Buffer.from('ab'.repeat(16), 'hex').toString('base64') })
  assert.equal(part.headers['x-amz-checksum-sha256'], undefined)
  assert.equal(part.headers['content-md5'], Buffer.from('ab'.repeat(16), 'hex').toString('base64'))
  assert.match(part.url, /X-Amz-SignedHeaders=content-length%3Bcontent-md5%3Bhost/)
})

test('GET presign has no session token and refuses the media bucket', async () => {
  const url = await presignGet({ ...secret, expiresSeconds: 120 })
  assert.equal(url.includes('X-Amz-Security-Token'), false)
  assert.equal(url.includes('X-Amz-SignedHeaders=host'), true)
  assert.equal(new URL(url).searchParams.get('X-Amz-Signature')?.length, 64)
  await assert.rejects(() => presignGet({ ...secret, bucket: 'autoclip-media' }))
})

test('a long grant is not slept through, and a failed observation exits nonzero', async () => {
  const refused = await waitForExpiry(new Date(Date.now() + 60_000).toISOString())
  assert.equal(refused.ok, false)
  assert.equal(exitCode({ status: 'not-run' }), 0)
  assert.equal(exitCode({ status: 'observed-failures', results: [{ id: 'tampered-signature', pass: false }] }), 1)
  assert.equal(REQUIRED_LIVE_CASES.includes('wrong-etag'), true)
  assert.equal(multipartPartHeaders({ 'content-length': '1', 'content-md5': 'abc=' }), true)
})

test('a reset mid-upload keeps earlier evidence and does not pass the remaining cases', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'diag-evidence-'))
  const evidence = createEvidenceStore(dir)
  const state = { uploadedBytes: 0, evidence, results: [] }
  state.record = (id, result) => state.results.push({ id, ...result })
  let calls = 0
  await assert.rejects(() => sendPart(state, { number: 4, length: 8, url: 'https://acct.r2.cloudflarestorage.com/bucket/key?X-Amz-Signature=secret', headers: { authorization: 'Bearer secret' } }, async () => {
    calls += 1
    const error = new Error('socket hang up')
    error.code = 'ECONNRESET'
    error.bytesWritten = 3
    throw error
  }, 'exact-2gib'))
  assert.equal(calls, 3)
  assert.equal(state.uploadedBytes, 9)
  state.results.push({ id: 'valid-put', pass: true, http: 200 })
  evidence.state.results = [{ id: 'valid-put', pass: true }, { id: 'exact-2gib', run: false, pass: false, reason: 'not-run' }]
  evidence.commit()
  const saved = readFileSync(evidence.snapPath, 'utf8')
  assert.equal(saved.includes('X-Amz-Signature'), false)
  assert.equal(saved.includes('Bearer'), false)
  assert.equal(saved.includes('https://'), false)
  const parsed = JSON.parse(saved)
  assert.equal(parsed.uploadedBytes, 9)
  assert.equal(parsed.results.find((item) => item.id === 'valid-put').pass, true)
  assert.equal(parsed.results.find((item) => item.id === 'exact-2gib').pass, false)
  assert.equal(parsed.results.find((item) => item.id === 'exact-2gib').reason, 'not-run')
})

test('a reset while the live script is running returns the earlier result and skips 2GiB', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'diag-live-'))
  const evidence = createEvidenceStore(dir)
  let puts = 0
  const result = await executeLive({
    AUTOCLIP_DIAGNOSTICS_LIVE_ENDPOINT: 'https://example.workers.dev',
    AUTOCLIP_DIAGNOSTICS_LIVE_BUCKET: 'autoclip-diagnostics-validation',
  }, {
    evidence,
    hashGet: async () => ({ sha256: 'absent', bytes: 0 }),
    putPart: async () => {
      puts += 1
      if (puts >= 5) {
        const error = new Error('socket hang up')
        error.code = 'ECONNRESET'
        error.bytesWritten = 40
        throw error
      }
      return { status: 403, bytesWritten: 8, requestId: 'ray-put' }
    },
    worker: async (_endpoint, path, method) => {
      if (method === 'DELETE') return { status: 200, body: { deleted: true } }
      if (String(path).endsWith('/cancel')) return { status: 200, body: {} }
      if (String(path).endsWith('/complete')) return { status: 200, body: { ok: true, phase: 'commit' }, requestId: 'ray-complete' }
      if (String(path).endsWith('/read-url')) return { status: 200, body: { url: 'https://acct.r2.cloudflarestorage.com/bucket/key?X-Amz-Signature=secret' }, requestId: 'ray-read' }
      return {
        status: 201,
        requestId: 'ray-create',
        body: {
          case_id: 'case-1',
          capability: 'super-secret-capability',
          upload_expires_at: new Date(Date.now() + 3_600_000).toISOString(),
          uploads: [{
            object_id: 'object-1',
            url: 'https://acct.r2.cloudflarestorage.com/bucket/key?X-Amz-Signature=secret',
            headers: { 'content-length': '65536', 'x-amz-checksum-sha256': 'aa' },
            parts: [
              { number: 1, offset: 0, length: 8, headers: { 'content-length': '8', 'content-md5': 'AAAAAAAAAAAAAAAAAAAAAA==' } },
              { number: 2, offset: 8, length: 8, headers: { 'content-length': '8', 'content-md5': 'AAAAAAAAAAAAAAAAAAAAAA==' } },
            ],
          }],
        },
      }
    },
  })
  const saved = readFileSync(evidence.snapPath, 'utf8')
  assert.equal(saved.includes('super-secret-capability'), false)
  assert.equal(saved.includes('X-Amz-Signature'), false)
  assert.equal(result.results.find((item) => item.id === 'production-headers').pass, true)
  assert.equal(result.results.find((item) => item.id === 'transport-failure').errorCode, 'ECONNRESET')
  assert.equal(result.results.find((item) => item.id === 'exact-2gib').reason, 'not-run')
  assert.equal(result.results.find((item) => item.id === 'exact-2gib').pass, false)
  assert.equal(result.results.find((item) => item.id === 'lost-create-cancel').reason, 'not-run')
  assert.equal(result.liveValidationClaimed, false)
  assert.equal(result.uploadedBytes, 32 + 40)
})

test('the upload plan stays inside 3GiB and refuses the media bucket', () => {
  const planned = planUploads({})
  assert.equal(planned.withinBudget, true)
  assert.ok(planned.total <= BUDGET_BYTES)
  assert.throws(() => assertStagingTarget({
    AUTOCLIP_DIAGNOSTICS_LIVE_ENDPOINT: 'https://example.workers.dev',
    AUTOCLIP_DIAGNOSTICS_LIVE_BUCKET: 'autoclip-media',
  }), /refusing_media_bucket/)
})

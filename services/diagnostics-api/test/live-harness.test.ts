import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { createServer } from 'node:http'
import { mkdtempSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'
import { presignGet, presignPut } from '../src/sign.ts'
import { armed, assertStagingTarget, createEvidenceStore, executeLive, exitCode, hashGet, main, multipartPartHeaders, planUploads, productionHeaders, sendPart, waitForExpiry, worker, BUDGET_BYTES, REQUIRED_LIVE_CASES } from '../live/harness.mjs'

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

test('the outer failure accounting does not add a part attempt that was already counted', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'diag-count-'))
  const evidence = createEvidenceStore(dir)
  const state = { uploadedBytes: 0, evidence, results: [] }
  let caught
  try {
    await sendPart(state, { number: 1, length: 8, url: 'https://acct.r2.cloudflarestorage.com/b/k', headers: {} }, async () => {
      const error = new Error('socket hang up')
      error.code = 'ECONNRESET'
      error.bytesWritten = 3
      throw error
    }, 'control-16mib')
  } catch (error) {
    caught = error
  }
  assert.equal(caught.counted, true)
  assert.equal(state.uploadedBytes, 9)
  if (!caught.counted && Number.isInteger(caught.bytesWritten)) state.uploadedBytes += caught.bytesWritten
  assert.equal(state.uploadedBytes, 9)
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
      if (puts === 4) return { status: 400, bytesWritten: 8, requestId: 'ray-put', detail: 'BadDigest' }
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
  assert.equal(result.results.find((item) => item.id === 'original-max-plus-manifest').reason, 'not-run')
  assert.equal(result.results.find((item) => item.id === 'fitting-original-under-inflight').reason, 'not-run')
  assert.equal(result.results.find((item) => item.id === 'fitting-original-under-inflight').pass, false)
  assert.equal(result.results.find((item) => item.id === 'lost-create-cancel').reason, 'not-run')
  assert.equal(result.liveValidationClaimed, false)
  assert.equal(result.uploadedBytes, 32 + 40)
})

test('readback uses the raw url and compares a real response body', async () => {
  const payload = Buffer.from('abc')
  const digest = createHash('sha256').update(payload).digest('hex')
  let gets = 0
  const objectServer = createServer((request, response) => {
    if (request.url.startsWith('/head') && request.method === 'HEAD') {
      response.setHeader('content-length', String(payload.length))
      response.end()
      return
    }
    if (request.method === 'HEAD') {
      response.statusCode = 403
      response.end('method')
      return
    }
    if (request.method === 'GET' && request.url.startsWith('/object')) {
      gets += 1
      response.end(payload)
      return
    }
    response.statusCode = 404
    response.end()
  })
  await new Promise((resolve) => objectServer.listen(0, '127.0.0.1', resolve))
  const objectPort = objectServer.address().port
  const api = createServer((request, response) => {
    response.setHeader('content-type', 'application/json')
    response.end(JSON.stringify({
      url: `http://127.0.0.1:${objectPort}/object?X-Amz-Signature=secret`,
      head_url: `http://127.0.0.1:${objectPort}/head?X-Amz-Signature=secret`,
      capability: 'super-secret-capability',
    }))
  })
  await new Promise((resolve) => api.listen(0, '127.0.0.1', resolve))
  const apiPort = api.address().port
  try {
    const read = await worker(`http://127.0.0.1:${apiPort}`, '/read-url', 'POST', {})
    assert.equal(read.raw.url.includes('X-Amz-Signature=secret'), true)
    assert.equal(read.body.url, undefined)
    const hashed = await hashGet(read.raw.url, payload.length, read.raw.head_url)
    assert.equal(gets, 1)
    assert.equal(hashed.sha256, digest)
    assert.equal(hashed.bytes, payload.length)
    assert.equal(hashed.headStatus, 200)
    assert.equal(hashed.headMatchesBody, true)
    const saved = JSON.stringify(sanitizePublic(read))
    assert.equal(saved.includes('X-Amz-Signature'), false)
    assert.equal(saved.includes('super-secret'), false)
  } finally {
    objectServer.close()
    api.close()
  }
})

function sanitizePublic(response) {
  return JSON.parse(JSON.stringify(response.body))
}

test('the upload plan stays inside 3GiB and refuses the media bucket', () => {
  const planned = planUploads({})
  assert.equal(planned.withinBudget, true)
  assert.ok(planned.total <= BUDGET_BYTES)
  assert.throws(() => assertStagingTarget({
    AUTOCLIP_DIAGNOSTICS_LIVE_ENDPOINT: 'https://example.workers.dev',
    AUTOCLIP_DIAGNOSTICS_LIVE_BUCKET: 'autoclip-media',
  }), /refusing_media_bucket/)
})

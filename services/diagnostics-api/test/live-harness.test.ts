import assert from 'node:assert/strict'
import test from 'node:test'
import { presignGet, presignPut } from '../src/sign.ts'
import { armed, assertStagingTarget, exitCode, main, multipartPartHeaders, planUploads, productionHeaders, waitForExpiry, BUDGET_BYTES, REQUIRED_LIVE_CASES } from '../live/harness.mjs'

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

test('the upload plan stays inside 3GiB and refuses the media bucket', () => {
  const planned = planUploads({})
  assert.equal(planned.withinBudget, true)
  assert.ok(planned.total <= BUDGET_BYTES)
  assert.throws(() => assertStagingTarget({
    AUTOCLIP_DIAGNOSTICS_LIVE_ENDPOINT: 'https://example.workers.dev',
    AUTOCLIP_DIAGNOSTICS_LIVE_BUCKET: 'autoclip-media',
  }), /refusing_media_bucket/)
})

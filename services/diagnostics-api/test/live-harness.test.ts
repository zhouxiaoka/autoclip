import assert from 'node:assert/strict'
import test from 'node:test'
import { presignGet, presignPut } from '../src/sign.ts'
import { armed, assertStagingTarget, main, planUploads, productionHeaders, BUDGET_BYTES } from '../live/harness.mjs'

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
  const part = await presignPut({ ...secret, uploadId: 'up', partNumber: 1 })
  assert.equal(part.headers['x-amz-checksum-sha256'], undefined)
  assert.equal(Object.keys(part.headers).join(','), 'content-length')
})

test('GET presign has no session token and refuses the media bucket', async () => {
  const url = await presignGet({ ...secret, expiresSeconds: 120 })
  assert.equal(url.includes('X-Amz-Security-Token'), false)
  assert.equal(url.includes('X-Amz-SignedHeaders=host'), true)
  assert.equal(new URL(url).searchParams.get('X-Amz-Signature')?.length, 64)
  await assert.rejects(() => presignGet({ ...secret, bucket: 'autoclip-media' }))
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

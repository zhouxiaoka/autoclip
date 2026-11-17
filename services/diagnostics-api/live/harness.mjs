/**
 * Opt-in staging probe for the production presign and Worker path.
 * Default: print the plan and exit without a network call.
 * This file does not create buckets, deploy Workers, or read user media.
 */
import { createHash, createHmac, randomBytes } from 'node:crypto'
import https from 'node:https'
import { awsEncode, presignPut } from '../src/sign.ts'

export const FORBIDDEN_BUCKET = 'autoclip-media'
export const BUDGET_BYTES = 3 * 1024 * 1024 * 1024
export const ORIGINAL_MAX = 2147483648
export const INFLIGHT_CAP = 2147483648
export const PART_BYTES = 8 * 1024 * 1024
export const SMALL_BYTES = 64 * 1024
export const STREAM_200_MIB = 200 * 1024 * 1024
export const STAGING_INFLIGHT_CAP = INFLIGHT_CAP + 262144

/** Headers the production signer actually puts on a PUT. Anything else is unsupported. */
export const PRODUCTION_PUT_HEADERS = ['content-length', 'x-amz-checksum-sha256']
export const UNSUPPORTED_CHECKSUM_HEADERS = [
  'content-md5',
  'x-amz-checksum-crc32',
  'x-amz-checksum-crc32c',
  'x-amz-checksum-sha1',
  'x-amz-checksum-mode',
  'x-amz-sdk-checksum-algorithm',
  'x-amz-trailer',
  'x-amz-content-sha256',
]

export function armed(env = process.env) {
  return env.AUTOCLIP_DIAGNOSTICS_LIVE === '1' && env.AUTOCLIP_DIAGNOSTICS_LIVE_APPROVED === 'staging'
}

export function manifestDocument() {
  return {
    schema: 'autoclip.support_manifest/1',
    purpose: 'troubleshooting_and_product_improvement',
    not_for_training: true,
    consent_text_version: '2026-11-16.1',
    runtime: { app_version: '1.5.9', os: 'linux', arch: 'x86_64', runtime: 'node-live-harness' },
    attempt: { attempt_id: `t-${'a'.repeat(32)}`, state: 'failed', error_code: 'timeout', failure_stage: 'analyze', sequence: 1 },
    run: { duration_ms: 10 },
    media_facts: {},
    log_lines: [],
    limits: { approval: 'pending' },
  }
}

export function manifestByteLength() {
  return Buffer.byteLength(JSON.stringify(manifestDocument()))
}

/** Exact 2GiB file plus the manifest cannot share the 2GiB in-flight cap. */
export function fittingOriginalBytes(manifestBytes = manifestByteLength()) {
  return INFLIGHT_CAP - manifestBytes
}

export function planUploads(env = process.env) {
  const manifestBytes = manifestByteLength()
  const fit = fittingOriginalBytes(manifestBytes)
  const uploads = [
    { id: 'checksum-single', bytes: SMALL_BYTES, uploads: true },
    { id: 'checksum-corrupt-body', bytes: SMALL_BYTES, uploads: true },
    { id: 'checksum-altered-header', bytes: SMALL_BYTES, uploads: true },
    { id: 'signature-tamper', bytes: SMALL_BYTES, uploads: true },
    { id: 'missing-signed-header', bytes: SMALL_BYTES, uploads: true },
    { id: 'wrong-etag', bytes: PART_BYTES * 2, uploads: true },
    { id: 'stream-200-mib', bytes: STREAM_200_MIB, uploads: true },
    { id: 'exact-original-max', bytes: ORIGINAL_MAX, uploads: true },
  ]
  const total = uploads.filter((item) => item.uploads).reduce((sum, item) => sum + item.bytes, 0)
  return { manifestBytes, fit, uploads, total, withinBudget: total <= BUDGET_BYTES && fit > 0 }
}

export function productionHeaders(headers) {
  const names = Object.keys(headers).map((name) => name.toLowerCase())
  return names.every((name) => PRODUCTION_PUT_HEADERS.includes(name))
    && names.includes('content-length')
    && UNSUPPORTED_CHECKSUM_HEADERS.every((name) => !names.includes(name))
}

export function assertStagingTarget(env = process.env) {
  const endpoint = env.AUTOCLIP_DIAGNOSTICS_LIVE_ENDPOINT || ''
  const bucket = env.AUTOCLIP_DIAGNOSTICS_LIVE_BUCKET || 'autoclip-diagnostics-validation'
  if (bucket === FORBIDDEN_BUCKET || endpoint.includes(FORBIDDEN_BUCKET)) {
    throw new Error('refusing_media_bucket')
  }
  let url
  try { url = new URL(endpoint) } catch { throw new Error('endpoint_required') }
  if (url.protocol !== 'https:' || url.username || url.password) throw new Error('endpoint_rejected')
  if (!planUploads(env).withinBudget) throw new Error('budget_exceeded')
  return { endpoint: url.origin, bucket }
}

export function patternByte(offset) {
  return (offset * 131 + 17) & 0xff
}

export function hashPattern(byteLength) {
  const hash = createHash('sha256')
  const chunk = 1024 * 1024
  for (let offset = 0; offset < byteLength; offset += chunk) {
    const size = Math.min(chunk, byteLength - offset)
    const buffer = Buffer.allocUnsafe(size)
    for (let index = 0; index < size; index += 1) buffer[index] = patternByte(offset + index)
    hash.update(buffer)
  }
  return hash.digest('hex')
}

export function redactUrl(value) {
  const url = new URL(value)
  url.search = ''
  url.username = ''
  url.password = ''
  return url.toString()
}

function recoveryToken() {
  return randomBytes(32).toString('base64url')
}

export async function signedSinglePut(env, key, byteLength, digestHex) {
  return presignPut({
    accountId: env.R2_ACCOUNT_ID,
    accessKeyId: env.R2_ACCESS_KEY_ID,
    secretAccessKey: env.R2_SECRET_ACCESS_KEY,
    bucket: env.AUTOCLIP_DIAGNOSTICS_LIVE_BUCKET || 'autoclip-diagnostics-validation',
    key,
    contentLength: byteLength,
    checksumSha256Base64: Buffer.from(digestHex, 'hex').toString('base64'),
    expiresSeconds: 900,
  })
}

function hmac(key, data) {
  return createHmac('sha256', key).update(data).digest()
}

/** Verifier only. Production upload signatures come from presignPut inside the Worker. */
export function presignGet(env, key, expiresSeconds = 900) {
  const now = new Date()
  const stamp = now.toISOString().replace(/[:-]|\.\d{3}/g, '')
  const date = stamp.slice(0, 8)
  const host = `${env.R2_ACCOUNT_ID}.r2.cloudflarestorage.com`
  const bucket = env.AUTOCLIP_DIAGNOSTICS_LIVE_BUCKET || 'autoclip-diagnostics-validation'
  if (bucket === FORBIDDEN_BUCKET) throw new Error('refusing_media_bucket')
  const credential = `${env.R2_ACCESS_KEY_ID}/${date}/auto/s3/aws4_request`
  const query = [
    ['X-Amz-Algorithm', 'AWS4-HMAC-SHA256'],
    ['X-Amz-Credential', credential],
    ['X-Amz-Date', stamp],
    ['X-Amz-Expires', String(expiresSeconds)],
    ['X-Amz-SignedHeaders', 'host'],
  ].map(([name, value]) => [awsEncode(name), awsEncode(value)])
  query.sort((left, right) => left[0] < right[0] ? -1 : left[0] > right[0] ? 1 : 0)
  const canonicalQuery = query.map(([name, value]) => `${name}=${value}`).join('&')
  const canonical = ['GET', `/${awsEncode(bucket)}/${key.split('/').map(awsEncode).join('/')}`, canonicalQuery, `host:${host}\n`, 'host', 'UNSIGNED-PAYLOAD'].join('\n')
  const dateKey = hmac(`AWS4${env.R2_SECRET_ACCESS_KEY}`, date)
  const signingKey = hmac(hmac(hmac(dateKey, 'auto'), 's3'), 'aws4_request')
  const signature = createHmac('sha256', signingKey).update(`AWS4-HMAC-SHA256\n${stamp}\n${date}/auto/s3/aws4_request\n${createHash('sha256').update(canonical).digest('hex')}`).digest('hex')
  return `https://${host}/${bucket}/${key.split('/').map(encodeURIComponent).join('/')}?${canonicalQuery}&X-Amz-Signature=${signature}`
}

/** Independent streaming readback. Not a production upload, and not an ETag comparison. */
export function hashResponseBody(body, byteLength) {
  const hash = createHash('sha256')
  let seen = 0
  return new Promise((resolve, reject) => {
    body.on('data', (chunk) => {
      seen += chunk.length
      if (seen > byteLength) {
        body.destroy()
        reject(new Error('readback_longer_than_declared'))
        return
      }
      hash.update(chunk)
    })
    body.on('end', () => resolve({ bytes: seen, sha256: hash.digest('hex') }))
    body.on('error', reject)
  })
}

export function hashGet(url, byteLength) {
  const target = new URL(url)
  if (target.protocol !== 'https:' || !target.hostname.endsWith('.r2.cloudflarestorage.com')) {
    return Promise.reject(new Error('read_url_rejected'))
  }
  return new Promise((resolve, reject) => {
    const req = https.get(target, (res) => {
      if ((res.statusCode || 0) !== 200) {
        res.resume()
        resolve({ status: res.statusCode || 0, bytes: 0, sha256: '' })
        return
      }
      hashResponseBody(res, byteLength).then((hashed) => resolve({ status: 200, ...hashed })).catch(reject)
    })
    req.on('error', () => reject(new Error('readback_failed')))
  })
}

export function putStream(url, headers, byteLength, corruptFirstByte = false, start = 0) {
  const target = new URL(url)
  if (target.protocol !== 'https:' || !target.hostname.endsWith('.r2.cloudflarestorage.com')) {
    return Promise.reject(new Error('upload_url_rejected'))
  }
  return new Promise((resolve, reject) => {
    const req = https.request(target, { method: 'PUT', headers }, (res) => {
      res.resume()
      res.on('end', () => resolve({ status: res.statusCode || 0, etag: String(res.headers.etag || '') }))
    })
    req.on('error', reject)
    const chunk = 1024 * 1024
    let offset = start
    const end = start + byteLength
    const write = () => {
      while (offset < end) {
        const size = Math.min(chunk, end - offset)
        const buffer = Buffer.allocUnsafe(size)
        for (let index = 0; index < size; index += 1) buffer[index] = patternByte(offset + index)
        if (corruptFirstByte && offset === start) buffer[0] ^= 0xff
        offset += size
        if (!req.write(buffer)) {
          req.once('drain', write)
          return
        }
      }
      req.end()
    }
    write()
  })
}

async function worker(endpoint, path, method, body, headers = {}) {
  const response = await fetch(`${endpoint}${path}`, {
    method,
    headers: { 'content-type': 'application/json', ...headers },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const text = await response.text()
  let parsed = null
  try { parsed = text ? JSON.parse(text) : null } catch { parsed = { unparsed: true } }
  return { status: response.status, body: parsed }
}

function idempotency() {
  return createHash('sha256').update(randomBytes(32)).digest('hex')
}

async function openUpload(endpoint, bytes, role) {
  const digest = hashPattern(bytes)
  const token = recoveryToken()
  const key = idempotency()
  const opened = await worker(endpoint, '/v1/cases', 'POST', {
    purpose: 'troubleshooting_and_product_improvement',
    not_for_training: true,
    consent_version: '2026-11-16.1',
    recovery_token: token,
    manifest: manifestDocument(),
    files: [{ role, bytes, sha256: digest, content_type: 'application/octet-stream' }],
  }, { 'idempotency-key': key })
  return { opened, token, key, digest }
}

export async function executeLive(env = process.env) {
  const { endpoint } = assertStagingTarget(env)
  const created = []
  const results = []
  const record = (id, result) => results.push({ id, ...result })
  const remember = (opened, token, key) => {
    if (opened.body?.case_id && opened.body?.capability) {
      created.push({ id: opened.body.case_id, capability: opened.body.capability, token, key })
    }
  }
  try {
    const small = await openUpload(endpoint, SMALL_BYTES, 'excerpt')
    if (small.opened.status !== 201) return { status: 'blocked', step: 'create', http: small.opened.status }
    remember(small.opened, small.token, small.key)
    const upload = small.opened.body.uploads[0]
    const headerNames = Object.keys(upload.headers || {}).map((name) => name.toLowerCase())
    record('production-headers', {
      pass: productionHeaders(upload.headers || {}) && headerNames.includes('x-amz-checksum-sha256'),
      signedChecksum: headerNames.includes('x-amz-checksum-sha256'),
      unsupportedPresent: headerNames.filter((name) => UNSUPPORTED_CHECKSUM_HEADERS.includes(name)),
    })
    const flipped = upload.url.slice(0, -1) + (upload.url.endsWith('0') ? '1' : '0')
    const rejected = await putStream(flipped, upload.headers, SMALL_BYTES, false).catch((error) => ({ status: 0, error: error.message }))
    record('tampered-signature', { http: rejected.status, pass: rejected.status === 403 })
    const omittedHeaders = { ...upload.headers }
    delete omittedHeaders['x-amz-checksum-sha256']
    const omitted = await putStream(upload.url, omittedHeaders, SMALL_BYTES, false).catch((error) => ({ status: 0, error: error.message }))
    record('missing-signed-checksum-header', { http: omitted.status, pass: omitted.status === 403, note: 'signed-header absence is authorization, not payload proof' })
    const altered = await putStream(upload.url, { ...upload.headers, 'x-amz-checksum-sha256': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=' }, SMALL_BYTES, false).catch((error) => ({ status: 0, error: error.message }))
    record('altered-checksum-header', { http: altered.status, enforced: altered.status !== 200 })
    const corrupt = await putStream(upload.url, upload.headers, SMALL_BYTES, true).catch((error) => ({ status: 0, error: error.message }))
    record('corrupt-body-signed-checksum', { http: corrupt.status, enforced: corrupt.status !== 200 })
    const good = await putStream(upload.url, upload.headers, SMALL_BYTES, false)
    record('valid-put', { http: good.status, pass: good.status === 200 })
    record('session-token', { supported: false, detail: 'signer has no X-Amz-Security-Token input' })
    const finished = await worker(endpoint, `/v1/cases/${small.opened.body.case_id}/files/${upload.object_id}/complete`, 'POST', {}, { authorization: `Bearer ${small.opened.body.capability}` })
    const read = await worker(endpoint, `/v1/cases/${small.opened.body.case_id}/files/${upload.object_id}/read-url`, 'POST', {}, { authorization: `Bearer ${small.opened.body.capability}` })
    if (read.status !== 200 || typeof read.body?.url !== 'string') {
      record('independent-readback', { pass: false, http: read.status, blocked: read.status !== 200 })
    } else {
      const hashed = await hashGet(read.body.url, SMALL_BYTES)
      record('independent-readback', { pass: hashed.sha256 === small.digest && hashed.bytes === SMALL_BYTES, bytes: hashed.bytes, complete: finished.status })
    }
    const streamCase = async (id, bytes, role) => {
      const opened = await openUpload(endpoint, bytes, role)
      record(`${id}-create`, { http: opened.opened.status })
      if (opened.opened.status !== 201) return
      remember(opened.opened, opened.token, opened.key)
      const planned = opened.opened.body.uploads[0]
      const parts = planned.parts || []
      const sent = []
      for (const part of parts) {
        const response = await putStream(part.url, { ...part.headers, 'content-length': String(part.length) }, part.length, false, part.offset || 0)
        sent.push({ partNumber: part.number, etag: response.etag, http: response.status })
      }
      const completed = await worker(endpoint, `/v1/cases/${opened.opened.body.case_id}/files/${planned.object_id}/complete`, 'POST', {
        parts: sent.map((part) => ({ partNumber: part.partNumber, etag: part.etag })),
      }, { authorization: `Bearer ${opened.opened.body.capability}` })
      const again = await worker(endpoint, `/v1/cases/${opened.opened.body.case_id}/files/${planned.object_id}/complete`, 'POST', {
        parts: sent.map((part) => ({ partNumber: part.partNumber, etag: part.etag })),
      }, { authorization: `Bearer ${opened.opened.body.capability}` })
      record(id, {
        puts: sent.map((part) => part.http),
        complete: completed.status,
        completeRetry: again.status,
        pass: sent.every((part) => part.http === 200) && completed.status === 200 && again.status === 200,
      })
    }
    await streamCase('stream-200-mib', STREAM_200_MIB, 'excerpt')
    await streamCase('exact-2gib', ORIGINAL_MAX, 'original')
    const lostKey = idempotency()
    const lostToken = recoveryToken()
    const lost = await worker(endpoint, '/v1/cases', 'POST', {
      purpose: 'troubleshooting_and_product_improvement',
      not_for_training: true,
      consent_version: '2026-11-16.1',
      recovery_token: lostToken,
      manifest: manifestDocument(),
      files: [],
    }, { 'idempotency-key': lostKey })
    const cancelled = await worker(endpoint, '/v1/cases/cancel', 'POST', { idempotency_key: lostKey, recovery_token: lostToken })
    const replay = await worker(endpoint, '/v1/cases', 'POST', {
      purpose: 'troubleshooting_and_product_improvement',
      not_for_training: true,
      consent_version: '2026-11-16.1',
      recovery_token: lostToken,
      manifest: manifestDocument(),
      files: [],
    }, { 'idempotency-key': lostKey })
    if (lost.body?.case_id && lost.body?.capability) remember(lost, lostToken, lostKey)
    record('lost-create-cancel', { create: lost.status, cancel: cancelled.status, replay: replay.status, pass: cancelled.status === 200 && replay.status === 410 })
    return {
      status: results.some((item) => item.pass === false || item.enforced === false) ? 'observed-failures' : 'observed',
      results,
      cases: created.map((item) => item.id),
      liveValidationClaimed: false,
    }
  } finally {
    for (const item of created) {
      await worker(endpoint, `/v1/cases/${item.id}`, 'DELETE', {}, { authorization: `Bearer ${item.capability}` }).catch(() => undefined)
    }
  }
}

export async function main(env = process.env, argv = process.argv) {
  const planned = planUploads(env)
  if (!armed(env)) return { status: 'not-run', plannedBytes: planned.total, withinBudget: planned.withinBudget }
  if (!argv.includes('--execute')) {
    assertStagingTarget(env)
    return { status: 'armed-not-executed', plannedBytes: planned.total, endpoint: redactUrl(env.AUTOCLIP_DIAGNOSTICS_LIVE_ENDPOINT) }
  }
  return executeLive(env)
}

if (process.argv[1] && process.argv[1].endsWith('harness.mjs')) {
  const result = await main()
  process.stdout.write(`${JSON.stringify(result)}\n`)
}

export { recoveryToken }

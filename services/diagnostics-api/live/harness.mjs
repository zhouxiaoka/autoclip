/**
 * Opt-in staging probe for the production presign and Worker path.
 * Default: print the plan and exit without a network call.
 * This file does not create buckets, deploy Workers, or read user media.
 */
import { createHash, createHmac, randomBytes } from 'node:crypto'
import { lookup as dnsLookup } from 'node:dns'
import { closeSync, fsyncSync, mkdirSync, openSync, renameSync, writeSync } from 'node:fs'
import http from 'node:http'
import https from 'node:https'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { awsEncode, presignPut } from '../src/sign.ts'

export const FORBIDDEN_BUCKET = 'autoclip-media'
export const BUDGET_BYTES = 3 * 1024 * 1024 * 1024
export const ORIGINAL_MAX = 2147483648
export const INFLIGHT_CAP = 2147483648
export const PART_BYTES = 8 * 1024 * 1024
export const SMALL_BYTES = 64 * 1024
export const STREAM_200_MIB = 200 * 1024 * 1024
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

export const REQUIRED_LIVE_CASES = [
  'tampered-signature',
  'missing-signed-checksum-header',
  'altered-checksum-header',
  'corrupt-body-signed-checksum',
  'valid-put',
  'independent-readback',
  'control-16mib',
  'control-16mib-readback',
  'expired-url',
  'expiry-refresh-resume-successful-parts',
  'part-missing-md5',
  'part-altered-md5',
  'part-corrupt-body',
  'wrong-etag',
  'missing-part',
  'stream-200-mib',
  'independent-sha256-readback-200mib',
  'original-max-plus-manifest',
  'fitting-original-under-inflight',
  'fitting-original-readback',
  'lost-create-cancel',
]

export const EXPIRY_TTL_SECONDS = 2
export const MAX_EXPIRY_WAIT_MS = 20_000
export const PART_PUT_TIMEOUT_MS = 120_000
export const REFRESH_MARGIN_MS = 60_000
export const PART_ATTEMPTS = 3

export function planUploads() {
  const manifestBytes = manifestByteLength()
  const fit = fittingOriginalBytes(manifestBytes)
  const uploads = [
    { id: 'single-put-attempts', bytes: SMALL_BYTES * 5, uploads: true },
    { id: 'control-16mib', bytes: PART_BYTES * 2, uploads: true },
    { id: 'expiry-refresh', bytes: PART_BYTES * 3, uploads: true },
    { id: 'part-md5-negatives', bytes: PART_BYTES * 4, uploads: true },
    { id: 'wrong-etag', bytes: PART_BYTES * 2, uploads: true },
    { id: 'missing-part', bytes: PART_BYTES, uploads: true },
    { id: 'stream-200-mib', bytes: STREAM_200_MIB, uploads: true },
    { id: 'fitting-original-under-inflight', bytes: fittingOriginalBytes(manifestBytes), uploads: true },
  ]
  const total = uploads.filter((item) => item.uploads).reduce((sum, item) => sum + item.bytes, 0)
  return { manifestBytes, fit, uploads, total, withinBudget: total <= BUDGET_BYTES && fit > 0 }
}

const LIVE_DEFERRED_WHEN_SCOPED = ['stream-200-mib', 'independent-sha256-readback-200mib', 'fitting-original-under-inflight', 'fitting-original-readback']

export function requiredCases(env = {}) {
  if (env.AUTOCLIP_DIAGNOSTICS_LIVE_SCOPE === 'through-control') {
    return REQUIRED_LIVE_CASES.filter((id) => !LIVE_DEFERRED_WHEN_SCOPED.includes(id))
  }
  return REQUIRED_LIVE_CASES
}

export function exitCode(result, env = {}) {
  if (!result || result.status === 'not-run' || result.status === 'armed-not-executed') return 0
  const results = result.results || []
  const required = requiredCases(env)
  const ids = new Set(results.map((item) => item.id))
  const missing = required.some((id) => !ids.has(id))
  const failed = results.some((item) => required.includes(item.id) && (item.pass === false || item.enforced === false || item.run === false))
  return missing || failed ? 1 : 0
}

export async function waitForExpiry(uploadExpiresAt, now = Date.now()) {
  const target = Date.parse(uploadExpiresAt)
  const wait = target - now + 1000
  if (!Number.isFinite(target) || wait < 0 || wait > MAX_EXPIRY_WAIT_MS) return { ok: false, reason: 'ttl_not_test_scoped', wait }
  if (wait > 0) await new Promise((resolve) => setTimeout(resolve, wait))
  return { ok: true, wait }
}

export function productionHeaders(headers) {
  const names = Object.keys(headers).map((name) => name.toLowerCase())
  return names.every((name) => PRODUCTION_PUT_HEADERS.includes(name))
    && names.includes('content-length')
    && UNSUPPORTED_CHECKSUM_HEADERS.every((name) => !names.includes(name))
}

export function multipartPartHeaders(headers) {
  const names = Object.keys(headers).map((name) => name.toLowerCase()).sort()
  return names.join(',') === 'content-length,content-md5'
}

export function redactText(value) {
  return String(value || '').replace(/https?:\/\/\S+/gi, '[url]').slice(0, 240)
}

const HIDDEN_FIELDS = new Set(['url', 'head_url', 'authorization', 'capability', 'recovery_token', 'recoveryToken', 'secret', 'headers', 'token', 'idempotency_key', 'idempotencyKey'])

export function sanitize(value) {
  if (Array.isArray(value)) return value.map((item) => sanitize(item))
  if (value && typeof value === 'object') {
    const out = {}
    for (const [key, item] of Object.entries(value)) {
      if (HIDDEN_FIELDS.has(key)) continue
      out[key] = sanitize(item)
    }
    return out
  }
  return typeof value === 'string' ? redactText(value) : value
}

export function createEvidenceStore(directory) {
  mkdirSync(directory, { recursive: true })
  const logPath = join(directory, 'events.jsonl')
  const snapPath = join(directory, 'evidence.json')
  const state = { events: [], results: [], uploadedBytes: 0, cleanup: [], liveValidationClaimed: false }
  function commit() {
    const tmp = `${snapPath}.tmp`
    const fd = openSync(tmp, 'w')
    writeSync(fd, JSON.stringify(sanitize(state)))
    fsyncSync(fd)
    closeSync(fd)
    renameSync(tmp, snapPath)
  }
  return {
    state,
    snapPath,
    logPath,
    append(event) {
      const safe = sanitize(event)
      state.events.push(safe)
      if (Number.isInteger(event.uploadedBytes)) state.uploadedBytes = event.uploadedBytes
      const fd = openSync(logPath, 'a')
      writeSync(fd, `${JSON.stringify(safe)}\n`)
      fsyncSync(fd)
      closeSync(fd)
      commit()
    },
    commit,
  }
}

export function retryableTransport(error) {
  const code = error?.code || ''
  return ['ECONNRESET', 'ETIMEDOUT', 'ECONNABORTED', 'EPIPE'].includes(code) || /socket hang up/i.test(error?.message || '')
}

export async function sendPart(state, part, put, stage) {
  let attempt = 0
  while (attempt < PART_ATTEMPTS) {
    if (state.uploadedBytes + part.length > BUDGET_BYTES) {
      const error = new Error('budget_exceeded')
      error.code = 'BUDGET'
      throw error
    }
    try {
      const response = await put(part.url, part.headers, part.length, part.corrupt === true, part.offset || 0)
      const bytesWritten = Number.isInteger(response?.bytesWritten) ? response.bytesWritten : part.length
      state.uploadedBytes += bytesWritten
      await state.evidence.append({
        kind: 'put', stage, part: part.number, attempt, http: response?.status || 0,
        bytesWritten, uploadedBytes: state.uploadedBytes, requestId: response?.requestId || undefined,
        errorCode: response?.errorCode, detail: response?.detail, at: new Date().toISOString(),
      })
      return response
    } catch (error) {
      const bytesWritten = Number.isInteger(error.bytesWritten) ? error.bytesWritten : 0
      state.uploadedBytes += bytesWritten
      await state.evidence.append({
        kind: 'put', stage, part: part.number, attempt, http: 0, bytesWritten,
        uploadedBytes: state.uploadedBytes, errorCode: error.code || 'exception',
        detail: redactText(error.message), at: new Date().toISOString(),
      })
      attempt += 1
      if (!retryableTransport(error) || attempt >= PART_ATTEMPTS) {
        error.counted = true
        throw error
      }
    }
  }
  throw new Error('part_attempts_exhausted')
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

function fixtureLookup(hostname, options, callback) {
  if (typeof options === 'function') {
    callback = options
    options = {}
  }
  if (process.env.AUTOCLIP_DIAGNOSTICS_FIXTURE_PORT && String(hostname).endsWith('.r2.cloudflarestorage.com')) {
    if (options.all) callback(null, [{ address: '127.0.0.1', family: 4 }])
    else callback(null, '127.0.0.1', 4)
    return
  }
  dnsLookup(hostname, options, callback)
}

export function fixtureStorageUrl(url) {
  const port = process.env.AUTOCLIP_DIAGNOSTICS_FIXTURE_PORT
  const endpoint = process.env.AUTOCLIP_DIAGNOSTICS_LIVE_ENDPOINT || ''
  const target = new URL(url)
  if (!port || !/^https:\/\/(127\.0\.0\.1|localhost)(:\d+)?(\/|$)/.test(endpoint)) return target
  if (!target.hostname.endsWith('.r2.cloudflarestorage.com')) return target
  target.port = String(port)
  return target
}

function allowedReadTarget(target) {
  if (target.username || target.password) return false
  if (target.protocol === 'https:' && target.hostname.endsWith('.r2.cloudflarestorage.com')) return true
  return target.protocol === 'http:' && (target.hostname === '127.0.0.1' || target.hostname === 'localhost')
}

function requestOptions(target, method, headers = {}) {
  const signedHost = process.env.AUTOCLIP_DIAGNOSTICS_FIXTURE_PORT ? { host: target.hostname } : {}
  return {
    protocol: target.protocol,
    hostname: target.hostname,
    port: target.port,
    path: `${target.pathname}${target.search}`,
    method,
    lookup: process.env.AUTOCLIP_DIAGNOSTICS_FIXTURE_PORT ? fixtureLookup : undefined,
    headers: { ...headers, ...signedHost },
  }
}

function requestHead(transport, target) {
  return new Promise((resolve, reject) => {
    const req = transport.request(requestOptions(target, 'HEAD'), (res) => {
      res.resume()
      res.on('end', () => resolve({ status: res.statusCode || 0, contentLength: Number(res.headers['content-length']) }))
    })
    req.on('error', reject)
    req.end()
  })
}

export function hashGet(url, byteLength, headUrl) {
  const target = fixtureStorageUrl(url)
  if (!allowedReadTarget(target)) {
    return Promise.reject(new Error('read_url_rejected'))
  }
  const transport = target.protocol === 'http:' ? http : https
  const headTarget = typeof headUrl === 'string' ? fixtureStorageUrl(headUrl) : null
  if (!headTarget || !allowedReadTarget(headTarget)) {
    return Promise.resolve({ status: 0, bytes: 0, sha256: '', headStatus: 0, headMatchesBody: false, method: 'HEAD', reason: 'head_url_missing' })
  }
  return requestHead(headTarget.protocol === 'http:' ? http : https, headTarget).then((head) => new Promise((resolve, reject) => {
    if (head.status !== 200) {
      resolve({ status: head.status, bytes: 0, sha256: '', headStatus: head.status, method: 'HEAD' })
      return
    }
    const req = transport.get(requestOptions(target, 'GET'), (res) => {
      if ((res.statusCode || 0) !== 200) {
        res.resume()
        resolve({ status: res.statusCode || 0, bytes: 0, sha256: '', headStatus: head.status, headBytes: head.contentLength })
        return
      }
      hashResponseBody(res, byteLength).then((hashed) => resolve({
        status: 200, ...hashed, headStatus: head.status, headBytes: head.contentLength,
        headMatchesBody: hashed.bytes === head.contentLength,
      })).catch(reject)
    })
    req.on('error', () => reject(new Error('readback_failed')))
  }))
}

export function putStream(url, headers, byteLength, corruptFirstByte = false, start = 0) {
  const target = fixtureStorageUrl(url)
  if (target.protocol !== 'https:' || !target.hostname.endsWith('.r2.cloudflarestorage.com')) {
    return Promise.reject(new Error('upload_url_rejected'))
  }
  return new Promise((resolve, reject) => {
    let bytesWritten = 0
    let settled = false
    let stopWriting = false
    let seen = null
    const agent = new https.Agent({ keepAlive: false, maxSockets: 1 })
    const succeed = (value) => {
      if (settled) return
      settled = true
      agent.destroy()
      resolve(value)
    }
    const fail = (error) => {
      if (settled) return
      if (seen) { succeed(seen); return }
      settled = true
      error.bytesWritten = bytesWritten
      agent.destroy()
      reject(error)
    }
    const req = https.request({ ...requestOptions(target, 'PUT', headers), agent }, (res) => {
      stopWriting = true
      const chunks = []
      res.on('data', (chunk) => {
        if (chunks.reduce((sum, item) => sum + item.length, 0) < 512) chunks.push(chunk)
      })
      res.on('end', () => {
        seen = {
          status: res.statusCode || 0,
          etag: String(res.headers.etag || ''),
          requestId: String(res.headers['cf-ray'] || ''),
          bytesWritten,
          detail: (res.statusCode || 0) === 200 ? undefined : redactText(Buffer.concat(chunks).toString('utf8')),
        }
        succeed(seen)
      })
    })
    req.setTimeout(PART_PUT_TIMEOUT_MS, () => {
      const error = new Error('timeout')
      error.code = 'ETIMEDOUT'
      req.destroy(error)
    })
    req.on('error', fail)
    const end = start + byteLength
    let offset = start
    let first = true
    const write = () => {
      if (stopWriting || settled) return
      while (offset < end) {
        const size = Math.min(first ? 16 * 1024 : 1024 * 1024, end - offset)
        const buffer = Buffer.allocUnsafe(size)
        for (let index = 0; index < size; index += 1) buffer[index] = patternByte(offset + index)
        if (corruptFirstByte && offset === start) buffer[0] ^= 0xff
        offset += size
        bytesWritten += size
        const paused = !req.write(buffer)
        if (first || paused) {
          first = false
          if (paused) req.once('drain', write)
          else setImmediate(write)
          return
        }
      }
      req.end()
    }
    write()
  })
}

export async function worker(endpoint, path, method, body, headers = {}) {
  const response = await fetch(`${endpoint}${path}`, {
    method,
    headers: { 'content-type': 'application/json', ...headers },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const text = await response.text()
  let parsed = null
  try { parsed = text ? JSON.parse(text) : null } catch { parsed = { unparsed: true, redacted: redactText(text) } }
  const raw = parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : null
  return { status: response.status, raw, body: raw ? sanitize(structuredClone(raw)) : parsed, requestId: response.headers.get('cf-ray') || undefined }
}

function op(response) {
  return response?.raw || response?.body || {}
}

function idempotency() {
  return createHash('sha256').update(randomBytes(32)).digest('hex')
}

function partMd5s(bytes) {
  if (bytes <= PART_BYTES) return undefined
  const digests = []
  for (let offset = 0; offset < bytes; offset += PART_BYTES) {
    const length = Math.min(PART_BYTES, bytes - offset)
    const hash = createHash('md5')
    const chunk = 1024 * 1024
    for (let index = 0; index < length; index += chunk) {
      const size = Math.min(chunk, length - index)
      const buffer = Buffer.allocUnsafe(size)
      for (let byte = 0; byte < size; byte += 1) buffer[byte] = patternByte(offset + index + byte)
      hash.update(buffer)
    }
    digests.push(hash.digest('base64'))
  }
  return digests
}

function createBody(bytes, role, digest, token, partTtl) {
  const file = { role, bytes, sha256: digest, content_type: 'application/octet-stream' }
  const digests = partMd5s(bytes)
  if (digests) file.part_md5s = digests
  const body = {
    purpose: 'troubleshooting_and_product_improvement',
    not_for_training: true,
    consent_version: '2026-11-16.1',
    recovery_token: token,
    manifest: manifestDocument(),
    files: [file],
  }
  if (partTtl) body.part_ttl_seconds = partTtl
  return body
}

async function openUpload(endpoint, bytes, role, partTtl, call = worker) {
  const digest = hashPattern(bytes)
  const token = recoveryToken()
  const key = idempotency()
  const opened = await call(endpoint, '/v1/cases', 'POST', createBody(bytes, role, digest, token, partTtl), { 'idempotency-key': key })
  return { opened, token, key, digest, bytes, role, partTtl }
}

function observed(response) {
  const body = response?.body && typeof response.body === 'object' ? response.body : {}
  return {
    http: response?.status || 0,
    error: typeof body.error === 'string' ? body.error : undefined,
    phase: typeof body.phase === 'string' ? body.phase : undefined,
    detail: typeof body.detail === 'string' ? redactText(body.detail) : typeof body.redacted === 'string' ? body.redacted : undefined,
    requestId: response?.requestId || undefined,
  }
}

export async function executeLive(env = process.env, io = {}) {
  const { endpoint } = assertStagingTarget(env)
  const created = []
  const results = []
  const rawPut = io.putPart || putStream
  const transmit = async (...args) => {
    const length = args[2] || 0
    if (state.uploadedBytes + length > BUDGET_BYTES) {
      const error = new Error('budget_exceeded')
      error.code = 'BUDGET'
      throw error
    }
    try {
      const response = await rawPut(...args)
      const bytesWritten = Number.isInteger(response?.bytesWritten) ? response.bytesWritten : length
      state.uploadedBytes += bytesWritten
      evidence.append({ kind: 'put', http: response?.status || 0, bytesWritten, uploadedBytes: state.uploadedBytes, requestId: response?.requestId, detail: response?.detail, at: new Date().toISOString() })
      return response
    } catch (error) {
      const bytesWritten = Number.isInteger(error.bytesWritten) ? error.bytesWritten : 0
      state.uploadedBytes += bytesWritten
      error.counted = true
      evidence.append({ kind: 'put', http: 0, bytesWritten, uploadedBytes: state.uploadedBytes, errorCode: error.code || 'exception', detail: redactText(error.message), at: new Date().toISOString() })
      throw error
    }
  }
  const put = transmit
  const call = io.worker || worker
  const readHash = io.hashGet || hashGet
  const evidence = io.evidence || createEvidenceStore(env.AUTOCLIP_DIAGNOSTICS_EVIDENCE || join(tmpdir(), 'autoclip-diagnostics-evidence'))
  const state = { uploadedBytes: 0, evidence, results }
  let stopping = false
  const failedCase = (result) => result?.reason !== 'not-run' && (result?.pass === false || result?.transportUnverified === true || result?.enforced === false || result?.http === 0)
  const record = async (id, result) => {
    const row = sanitize({ id, ...result })
    results.push(row)
    evidence.state.results = results
    evidence.state.uploadedBytes = state.uploadedBytes
    await evidence.append({ kind: 'result', ...row, uploadedBytes: state.uploadedBytes })
    if (!stopping && failedCase(result)) {
      stopping = true
      throw Object.assign(new Error(`fail_fast:${id}`), { code: 'FAIL_FAST' })
    }
  }
  const remember = (opened, token, key) => {
    if (op(opened).case_id && op(opened).capability) {
      created.push({ id: op(opened).case_id, capability: op(opened).capability, token, key })
    }
  }
  const quotaSnapshot = async (label) => {
    const token = env.AUTOCLIP_DIAGNOSTICS_ADMIN_TOKEN || ''
    if (!token) {
      await record(label, { configured: false, http: 0, pass: false, reason: 'admin_token_unset' })
      return null
    }
    const response = await call(endpoint, '/admin/quota', 'GET', undefined, { authorization: `Bearer ${token}` })
    const body = op(response)
    const reserved = Number.isInteger(body.reserved) ? body.reserved : null
    const landed = Number.isInteger(body.landed) ? body.landed : null
    await record(label, {
      configured: true, http: response.status, reserved, landed,
      pass: response.status === 200 && reserved === 0,
      note: reserved === 0 ? 'no leftover reservation' : 'leftover_reservation',
    })
    return { reserved, landed }
  }
  try {
    const small = await openUpload(endpoint, SMALL_BYTES, 'excerpt', undefined, call)
    if (small.opened.status !== 201) {
      await record('valid-put', { ...observed(small.opened), pass: false, run: true })
      throw Object.assign(new Error('create_failed'), { code: 'CREATE' })
    }
    remember(small.opened, small.token, small.key)
    const upload = op(small.opened).uploads[0]
    const headerNames = Object.keys(upload.headers || {}).map((name) => name.toLowerCase())
    await record('production-headers', {
      pass: productionHeaders(upload.headers || {}) && headerNames.includes('x-amz-checksum-sha256'),
      signedChecksum: headerNames.includes('x-amz-checksum-sha256'),
      unsupportedPresent: headerNames.filter((name) => UNSUPPORTED_CHECKSUM_HEADERS.includes(name)),
    })
    const flipped = upload.url.slice(0, -1) + (upload.url.endsWith('0') ? '1' : '0')
    const rejected = await put(flipped, upload.headers, SMALL_BYTES, false).catch((error) => ({ status: 0, error: error.message }))
    await record('tampered-signature', { http: rejected.status, pass: rejected.status === 403 })
    const omittedHeaders = { ...upload.headers }
    delete omittedHeaders['x-amz-checksum-sha256']
    const omitted = await put(upload.url, omittedHeaders, SMALL_BYTES, false).catch((error) => ({ status: 0, error: error.message }))
    await record('missing-signed-checksum-header', { http: omitted.status, pass: omitted.status === 403, note: 'signed-header absence is authorization, not payload proof' })
    const altered = await put(upload.url, { ...upload.headers, 'x-amz-checksum-sha256': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=' }, SMALL_BYTES, false).catch((error) => ({ status: 0, error: error.message }))
    await record('altered-checksum-header', altered.status
      ? { http: altered.status, requestId: altered.requestId, pass: altered.status === 403, note: 'changed signed header is authorization' }
      : { http: 0, pass: false, transportUnverified: true })
    const corrupt = await put(upload.url, upload.headers, SMALL_BYTES, true).catch((error) => ({ status: 0, error: error.message }))
    await record('corrupt-body-signed-checksum', { http: corrupt.status, requestId: corrupt.requestId, detail: corrupt.detail, enforced: corrupt.status === 400, pass: corrupt.status === 400 })
    const good = await put(upload.url, upload.headers, SMALL_BYTES, false)
    await record('valid-put', { http: good.status, pass: good.status === 200 })
    await record('session-token', { supported: false, detail: 'signer has no X-Amz-Security-Token input' })
    const finished = await call(endpoint, `/v1/cases/${op(small.opened).case_id}/files/${upload.object_id}/complete`, 'POST', {}, { authorization: `Bearer ${op(small.opened).capability}` })
    const read = await call(endpoint, `/v1/cases/${op(small.opened).case_id}/files/${upload.object_id}/read-url`, 'POST', {}, { authorization: `Bearer ${op(small.opened).capability}` })
    if (read.status !== 200 || typeof op(read)?.url !== 'string') {
      await record('independent-readback', { pass: false, http: read.status, blocked: read.status !== 200 })
    } else {
      const hashed = await readHash(op(read).url, SMALL_BYTES, op(read).head_url)
      await record('independent-readback', { pass: hashed.sha256 === small.digest && hashed.bytes === SMALL_BYTES && hashed.headMatchesBody === true, bytes: hashed.bytes, headBytes: hashed.headBytes, headStatus: hashed.headStatus, complete: finished.status })
    }
    const release = async (opened) => {
      if (!op(opened).case_id) return 0
      const response = await call(endpoint, `/v1/cases/${op(opened).case_id}`, 'DELETE', {}, { authorization: `Bearer ${op(opened).capability}` })
      return response.status
    }
    async function streamCase(id, bytes, role) {
      const opened = await openUpload(endpoint, bytes, role, undefined, call)
      await record(`${id}-create`, observed(opened.opened))
      const readId = id === 'stream-200-mib' ? 'independent-sha256-readback-200mib' : id === 'fitting-original-under-inflight' ? 'fitting-original-readback' : `${id}-readback`
      if (opened.opened.status !== 201) {
        await record(id, { pass: false, run: true })
        await record(readId, { run: false, pass: false, reason: 'not-run' })
        return false
      }
      remember(opened.opened, opened.token, opened.key)
      let planned = op(opened.opened).uploads[0]
      const sent = []
      for (const part of planned.parts || []) {
        const expires = Date.parse(op(opened.opened).upload_expires_at)
        if (Number.isFinite(expires) && expires - Date.now() < REFRESH_MARGIN_MS) {
          const refreshed = await call(endpoint, '/v1/cases', 'POST', createBody(bytes, role, opened.digest, opened.token), { 'idempotency-key': opened.key })
          await record(`${id}-refresh`, { ...observed(refreshed), part: part.number })
          if (op(refreshed)?.uploads?.[0]) {
            op(opened.opened).uploads = op(refreshed).uploads
            op(opened.opened).upload_expires_at = op(refreshed).upload_expires_at
            planned = op(refreshed).uploads[0]
          }
        }
        const current = (planned.parts || []).find((item) => item.number === part.number) || part
        const response = await sendPart(state, current, rawPut, id)
        sent.push({ partNumber: current.number, etag: response.etag, http: response.status, requestId: response.requestId, detail: response.detail })
        if (response.status !== 200) break
      }
      const completed = await call(endpoint, `/v1/cases/${op(opened.opened).case_id}/files/${planned.object_id}/complete`, 'POST', {
        parts: sent.map((part) => ({ partNumber: part.partNumber, etag: part.etag })),
      }, { authorization: `Bearer ${op(opened.opened).capability}` })
      const again = await call(endpoint, `/v1/cases/${op(opened.opened).case_id}/files/${planned.object_id}/complete`, 'POST', {
        parts: sent.map((part) => ({ partNumber: part.partNumber, etag: part.etag })),
      }, { authorization: `Bearer ${op(opened.opened).capability}` })
      const uploaded = sent.length === (planned.parts || []).length && sent.every((part) => part.http === 200) && completed.status === 200 && again.status === 200
      await record(id, {
        puts: sent.map((part) => part.http),
        ...observed(completed),
        retry: observed(again),
        uploadedBytes: state.uploadedBytes,
        pass: uploaded,
      })
      let hashedOk = false
      if (!uploaded) await record(readId, { run: false, pass: false, reason: 'not-run' })
      else {
        const read = await call(endpoint, `/v1/cases/${op(opened.opened).case_id}/files/${planned.object_id}/read-url`, 'POST', {}, { authorization: `Bearer ${op(opened.opened).capability}` })
        if (read.status !== 200 || typeof op(read)?.url !== 'string' || typeof op(read)?.head_url !== 'string') await record(readId, { ...observed(read), pass: false })
        else {
          const hashed = await readHash(op(read).url, bytes, op(read).head_url)
          hashedOk = hashed.sha256 === opened.digest && hashed.bytes === bytes && hashed.headMatchesBody === true && hashed.headStatus === 200
          await record(readId, { pass: hashedOk, bytes: hashed.bytes, headStatus: hashed.headStatus, headBytes: hashed.headBytes })
        }
      }
      const released = await release(opened.opened)
      await record(`${id}-released`, { http: released, pass: released === 200 || released === 404 })
      return uploaded && hashedOk
    }
    const controlOk = await streamCase('control-16mib', PART_BYTES * 2, 'excerpt')
    if (!controlOk) {
      for (const id of REQUIRED_LIVE_CASES) {
        if (!results.some((item) => item.id === id)) await record(id, { run: false, pass: false, reason: 'not-run' })
      }
    } else {
    const expiry = await openUpload(endpoint, PART_BYTES * 2, 'excerpt', EXPIRY_TTL_SECONDS, call)
    remember(expiry.opened, expiry.token, expiry.key)
    if (expiry.opened.status !== 201) {
      await record('expired-url', { ...observed(expiry.opened), pass: false })
      await record('expiry-refresh-resume-successful-parts', { run: false, pass: false })
    } else {
      const planned = op(expiry.opened).uploads[0]
      const first = planned.parts[0]
      const second = planned.parts[1]
      const kept = await put(first.url, first.headers, first.length, false, first.offset || 0)
      const waited = await waitForExpiry(op(expiry.opened).upload_expires_at)
      const stale = waited.ok ? await put(second.url, second.headers, second.length, false, second.offset || 0).catch((error) => ({ status: 0, detail: error.message })) : { status: 0 }
      await record('expired-url', { http: stale.status, requestId: stale.requestId, waited: waited.ok, pass: waited.ok && stale.status === 403 })
      const refreshed = await call(endpoint, '/v1/cases', 'POST', createBody(expiry.bytes, expiry.role, expiry.digest, expiry.token), { 'idempotency-key': expiry.key })
      const fresh = op(refreshed)?.uploads?.[0]?.parts?.[1]
      const resumed = fresh ? await put(fresh.url, fresh.headers, fresh.length, false, fresh.offset || 0) : { status: 0 }
      const completed = await call(endpoint, `/v1/cases/${op(expiry.opened).case_id}/files/${planned.object_id}/complete`, 'POST', {
        parts: [{ partNumber: 1, etag: kept.etag }, { partNumber: 2, etag: resumed.etag }],
      }, { authorization: `Bearer ${op(expiry.opened).capability}` })
      await record('expiry-refresh-resume-successful-parts', {
        keptPart: kept.status, resumedPart: resumed.status, ...observed(completed),
        pass: kept.status === 200 && resumed.status === 200 && completed.status === 200,
      })
    }
    await release(expiry.opened)
    const negative = await openUpload(endpoint, PART_BYTES * 2, 'excerpt', undefined, call)
    remember(negative.opened, negative.token, negative.key)
    if (negative.opened.status !== 201) {
      await record('part-missing-md5', { ...observed(negative.opened), pass: false })
      await record('part-altered-md5', { pass: false })
      await record('part-corrupt-body', { pass: false, enforced: false })
    } else {
      const planned = op(negative.opened).uploads[0]
      await record('multipart-part-headers', { pass: planned.parts.every((part) => multipartPartHeaders(part.headers)) })
      const first = planned.parts[0]
      const second = planned.parts[1]
      await put(first.url, first.headers, first.length, false, first.offset || 0)
      const withoutMd5 = { ...second.headers }
      delete withoutMd5['content-md5']
      const missing = await put(second.url, withoutMd5, second.length, false, second.offset || 0).catch((error) => ({ status: 0, detail: error.message }))
      await record('part-missing-md5', { http: missing.status, requestId: missing.requestId, pass: missing.status === 403, note: 'missing signed content-md5 is authorization' })
      const alteredMd5 = await put(second.url, { ...second.headers, 'content-md5': 'AAAAAAAAAAAAAAAAAAAAAA==' }, second.length, false, second.offset || 0).catch((error) => ({ status: 0, detail: error.message }))
      await record('part-altered-md5', alteredMd5.status
        ? { http: alteredMd5.status, requestId: alteredMd5.requestId, pass: alteredMd5.status === 403, note: 'changed signed content-md5 is authorization' }
        : { http: 0, pass: false, transportUnverified: true })
      const corruptPart = await put(second.url, second.headers, second.length, true, second.offset || 0).catch((error) => ({ status: 0, detail: error.message }))
      await record('part-corrupt-body', corruptPart.status
        ? { http: corruptPart.status, requestId: corruptPart.requestId, detail: corruptPart.detail, enforced: corruptPart.status === 400, pass: corruptPart.status === 400 }
        : { http: 0, pass: false, transportUnverified: true, enforced: undefined })
    }
    await release(negative.opened)
    const wrong = await openUpload(endpoint, PART_BYTES * 2, 'excerpt', undefined, call)
    remember(wrong.opened, wrong.token, wrong.key)
    if (wrong.opened.status !== 201) await record('wrong-etag', { ...observed(wrong.opened), pass: false })
    else {
      const planned = op(wrong.opened).uploads[0]
      const sent = []
      for (const part of planned.parts) {
        const response = await put(part.url, part.headers, part.length, false, part.offset || 0)
        sent.push({ partNumber: part.number, etag: response.etag, http: response.status })
      }
      const bad = sent.map((part, index) => ({ partNumber: part.partNumber, etag: index === 1 ? '"00000000000000000000000000000000"' : part.etag }))
      const completed = await call(endpoint, `/v1/cases/${op(wrong.opened).case_id}/files/${planned.object_id}/complete`, 'POST', { parts: bad }, { authorization: `Bearer ${op(wrong.opened).capability}` })
      const absent = await call(endpoint, `/v1/cases/${op(wrong.opened).case_id}/files/${planned.object_id}/read-url`, 'POST', {}, { authorization: `Bearer ${op(wrong.opened).capability}` })
      await record('wrong-etag', { puts: sent.map((part) => part.http), ...observed(completed), objectAbsent: absent.status === 404, pass: sent.every((part) => part.http === 200) && observed(completed).error === 'etag_mismatch' && absent.status === 404 })
    }
    await release(wrong.opened)
    const missingPart = await openUpload(endpoint, PART_BYTES * 2, 'excerpt', undefined, call)
    remember(missingPart.opened, missingPart.token, missingPart.key)
    if (missingPart.opened.status !== 201) await record('missing-part', { ...observed(missingPart.opened), pass: false })
    else {
      const planned = op(missingPart.opened).uploads[0]
      const first = planned.parts[0]
      const response = await put(first.url, first.headers, first.length, false, first.offset || 0)
      const completed = await call(endpoint, `/v1/cases/${op(missingPart.opened).case_id}/files/${planned.object_id}/complete`, 'POST', {
        parts: [{ partNumber: 1, etag: response.etag }],
      }, { authorization: `Bearer ${op(missingPart.opened).capability}` })
      const absent = await call(endpoint, `/v1/cases/${op(missingPart.opened).case_id}/files/${planned.object_id}/read-url`, 'POST', {}, { authorization: `Bearer ${op(missingPart.opened).capability}` })
      await record('missing-part', { put: response.status, ...observed(completed), objectAbsent: absent.status === 404, pass: response.status === 200 && observed(completed).error === 'missing_part' && absent.status === 404 })
    }
    await release(missingPart.opened)
    const lostKey = idempotency()
    const lostToken = recoveryToken()
    const lost = await call(endpoint, '/v1/cases', 'POST', {
      purpose: 'troubleshooting_and_product_improvement',
      not_for_training: true,
      consent_version: '2026-11-16.1',
      recovery_token: lostToken,
      manifest: manifestDocument(),
      files: [],
    }, { 'idempotency-key': lostKey })
    const cancelled = await call(endpoint, '/v1/cases/cancel', 'POST', { idempotency_key: lostKey, recovery_token: lostToken })
    const replay = await call(endpoint, '/v1/cases', 'POST', {
      purpose: 'troubleshooting_and_product_improvement',
      not_for_training: true,
      consent_version: '2026-11-16.1',
      recovery_token: lostToken,
      manifest: manifestDocument(),
      files: [],
    }, { 'idempotency-key': lostKey })
    if (op(lost).case_id && op(lost).capability) remember(lost, lostToken, lostKey)
    await record('lost-create-cancel', {
      create: lost.status, cancel: cancelled.status, replay: replay.status,
      pass: lost.status === 201 && cancelled.status === 200 && replay.status === 404,
      note: 'replay after delete is 404 and returns no upload plan; 410 is only the tombstone when create never landed',
    })
    const stopBeforeLarge = env.AUTOCLIP_DIAGNOSTICS_LIVE_SCOPE === 'through-control'
    const excerptReady = stopBeforeLarge ? false : await streamCase('stream-200-mib', STREAM_200_MIB, 'excerpt')
    if (stopBeforeLarge) {
      await record('stream-200-mib', { run: false, pass: false, reason: 'not-run' })
      await record('independent-sha256-readback-200mib', { run: false, pass: false, reason: 'not-run' })
    }
    if (stopBeforeLarge || excerptReady) {
      const beforeCap = await quotaSnapshot('pre-original-max-quota')
      const rejected = await openUpload(endpoint, ORIGINAL_MAX, 'original', undefined, call)
      remember(rejected.opened, rejected.token, rejected.key)
      const rejectedPuts = Array.isArray(op(rejected.opened).uploads) ? op(rejected.opened).uploads.length : 0
      const capDecision = beforeCap?.reserved === 0 ? 'inflight_cap' : 'leftover_reservation'
      await record('original-max-plus-manifest', {
        ...observed(rejected.opened), puts: rejectedPuts, reservedBefore: beforeCap?.reserved, capDecision,
        pass: rejected.opened.status === 413 && observed(rejected.opened).error === 'inflight_cap' && rejectedPuts === 0 && beforeCap?.reserved === 0,
        note: 'ORIGINAL_MAX plus its manifest does not fit the frozen in-flight cap. A nonzero reservedBefore means an earlier case still holds quota.',
      })
      if (rejected.opened.status === 201) await release(rejected.opened)
    } else {
      await record('original-max-plus-manifest', { run: false, pass: false, reason: 'not-run' })
    }
    if (!stopBeforeLarge && excerptReady) {
      await quotaSnapshot('pre-fitting-quota')
      await streamCase('fitting-original-under-inflight', fittingOriginalBytes(), 'original')
    }
    else {
      await record('fitting-original-under-inflight', { run: false, pass: false, reason: 'not-run' })
      await record('fitting-original-readback', { run: false, pass: false, reason: 'not-run' })
    }
    }
  } catch (error) {
    stopping = true
    if (!error.counted && Number.isInteger(error.bytesWritten)) state.uploadedBytes += error.bytesWritten
    if (error.code !== 'FAIL_FAST') {
      await record('transport-failure', {
        pass: false, run: true, errorCode: error.cause?.code || error.code || 'exception', detail: redactText(error.cause?.message || error.message),
        bytesWritten: Number.isInteger(error.bytesWritten) ? error.bytesWritten : undefined,
        uploadedBytes: state.uploadedBytes,
      })
    }
    for (const id of REQUIRED_LIVE_CASES) {
      if (!results.some((item) => item.id === id)) await record(id, { run: false, pass: false, reason: 'not-run' })
    }
  } finally {
    const cleanup = []
    for (const item of created) {
      try {
        const response = await call(endpoint, `/v1/cases/${item.id}`, 'DELETE', {}, { authorization: `Bearer ${item.capability}` })
        cleanup.push({ http: response.status })
      } catch (error) {
        cleanup.push({ errorCode: error.code || 'cleanup_failed', detail: redactText(error.message) })
      }
    }
    evidence.state.cleanup = cleanup
    evidence.state.uploadedBytes = state.uploadedBytes
    evidence.commit()
  }
  for (const id of REQUIRED_LIVE_CASES) {
    if (!results.some((item) => item.id === id)) await record(id, { run: false, pass: false, reason: 'not-run' })
  }
  const outcome = {
    results, uploadedBytes: state.uploadedBytes, cleanup: evidence.state.cleanup,
    cases: created.map((item) => item.id), liveValidationClaimed: false, evidence: evidence.snapPath,
  }
    outcome.status = exitCode(outcome, env) === 0 ? 'observed' : 'observed-failures'
  evidence.state.results = results
  evidence.commit()
  return outcome
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
  try {
    const result = await main()
    const text = `${JSON.stringify(result)}\n`
    process.stdout.write(text)
    process.exitCode = exitCode(result, process.env)
    if (process.exitCode !== 0) process.stderr.write(text)
  } catch (error) {
    const partial = { status: 'crashed', errorCode: error.code || 'exception', detail: redactText(error.message), liveValidationClaimed: false }
    const text = `${JSON.stringify(partial)}\n`
    process.stdout.write(text)
    process.stderr.write(text)
    process.exitCode = 1
  }
}

export { recoveryToken }

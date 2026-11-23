import { type CaseRow, type ObjectRow, type Repo } from './memory.ts'
import { orphanKeys, type Limits } from './quota.ts'
import { fileProblems, manifestProblems } from './validate.ts'

export interface UploadedPart {
  partNumber: number
  etag: string
}

/** The methods documented for a multipart upload handle. Completion assembles the parts. */
export interface MultipartUpload {
  key: string
  uploadId: string
  uploadPart(partNumber: number, value: Uint8Array): Promise<UploadedPart>
  abort(): Promise<void>
  complete(uploadedParts: UploadedPart[]): Promise<{ size: number; httpEtag: string }>
}

export interface Bucket {
  put(key: string, body: Uint8Array): Promise<void>
  head(key: string): Promise<{ size: number } | null>
  delete(key: string): Promise<void>
  createMultipartUpload(key: string): Promise<MultipartUpload>
  resumeMultipartUpload(key: string, uploadId: string): MultipartUpload
  list(prefix: string, uploadedBefore?: Date): Promise<string[]>
}

export interface Signer {
  sign(input: { key: string; contentLength: number; sha256Hex?: string; contentMd5Base64?: string; uploadId?: string; partNumber?: number; expiresSeconds?: number }): Promise<{ url: string; headers: Record<string, string> }>
  signGet?(key: string): Promise<string>
  signHead?(key: string): Promise<string>
}

export interface Deps {
  repo: Repo
  bucket: Bucket
  limits: Limits
  now: () => Date
  signer: Signer | null
  adminToken: string
  bucketName: string
  partBytes: number
}

const encoder = new TextEncoder()

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json; charset=utf-8' } })
}

async function sha256Hex(bytes: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', bytes)
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('')
}

function token(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(32))
  return btoa(String.fromCharCode(...bytes)).replaceAll('+', '-').replaceAll('/', '_').replaceAll('=', '')
}

function timingSafeEqual(left: string, right: string): boolean {
  const a = encoder.encode(left)
  const b = encoder.encode(right)
  if (a.length !== b.length) return false
  let diff = 0
  for (let i = 0; i < a.length; i += 1) diff |= a[i]! ^ b[i]!
  return diff === 0
}

function bearer(request: Request): string {
  const header = request.headers.get('authorization') || ''
  return header.toLowerCase().startsWith('bearer ') ? header.slice(7).trim() : ''
}

async function authorized(repo: Repo, caseId: string, request: Request): Promise<CaseRow | null> {
  const row = await repo.getCase(caseId)
  if (!row || row.state === 'deleted') return null
  const presented = bearer(request)
  if (!presented) return null
  const hash = await sha256Hex(encoder.encode(presented))
  if (!timingSafeEqual(hash, row.capabilitySha256)) return null
  return row
}

function partPlan(size: number, partBytes: number): { number: number; offset: number; length: number }[] {
  if (size <= partBytes) return [{ number: 1, offset: 0, length: size }]
  const parts = []
  let offset = 0
  let number = 1
  while (offset < size) {
    const length = Math.min(partBytes, size - offset)
    parts.push({ number, offset, length })
    number += 1
    offset += length
  }
  return parts
}

export async function handle(request: Request, deps: Deps): Promise<Response> {
  const url = new URL(request.url)
  if (request.method === 'POST' && url.pathname === '/v1/cases') return createCase(request, deps)
  if (request.method === 'POST' && url.pathname === '/v1/cases/cancel') return cancelCreation(request, deps)
  const abort = url.pathname.match(/^\/v1\/cases\/([^/]+)\/abort$/)
  if (request.method === 'POST' && abort) return abortCase(abort[1]!, request, deps)
  const complete = url.pathname.match(/^\/v1\/cases\/([^/]+)\/files\/([^/]+)\/complete$/)
  if (request.method === 'POST' && complete) return completeFile(complete[1]!, complete[2]!, request, deps)
  const readUrl = url.pathname.match(/^\/v1\/cases\/([^/]+)\/files\/([^/]+)\/read-url$/)
  if (request.method === 'POST' && readUrl) return readObjectUrl(readUrl[1]!, readUrl[2]!, request, deps)
  const remove = url.pathname.match(/^\/v1\/cases\/([^/]+)$/)
  if (request.method === 'DELETE' && remove) return deleteCase(remove[1]!, request, deps)
  if (request.method === 'GET' && url.pathname === '/admin/quota') {
    return admin(request, deps, async () => json(200, { ...(await Promise.resolve(deps.repo.snapshot())), approval: 'pending' }))
  }
  if (request.method === 'POST' && url.pathname === '/admin/reconcile') {
    return admin(request, deps, async () => json(200, { quota: await deps.repo.reconcile(), approval: 'pending' }))
  }
  return json(404, { error: 'not_found' })
}

function admin(request: Request, deps: Deps, next: () => Response | Promise<Response>): Response | Promise<Response> {
  if (!deps.adminToken || !timingSafeEqual(bearer(request), deps.adminToken)) return json(401, { error: 'unauthorized' })
  return next()
}

type UploadFile = { role: string; bytes: number; sha256: string; content_type?: string; part_md5s?: string[] }

type ObjectMeta = { kind: 'size'; size: number } | { kind: 'missing' } | { kind: 'transient'; detail?: string }

/** Object length comes from metadata. The body is not read, and a size is not a hash. */
async function metadataSize(bucket: Bucket, key: string): Promise<ObjectMeta> {
  try {
    const head = await bucket.head(key)
    if (!head) return { kind: 'missing' }
    if (typeof head.size !== 'number' || !Number.isSafeInteger(head.size) || head.size < 0) return { kind: 'transient' }
    return { kind: 'size', size: head.size }
  } catch (error) {
    return { kind: 'transient', detail: safeDetail(error) }
  }
}

function safeDetail(error: unknown): string | undefined {
  const message = error instanceof Error ? error.message : ''
  if (!message || /https?:|authorization|bearer|x-amz-|secret|signature/i.test(message)) return undefined
  const clean = message.replace(/[^\x20-\x7e]/g, '').slice(0, 160)
  return clean || undefined
}

function unavailable(phase: 'head' | 'complete' | 'verify' | 'commit', error?: unknown): Response {
  const detail = typeof error === 'string' ? error : safeDetail(error)
  return json(503, detail ? { error: 'unavailable', phase, detail } : { error: 'unavailable', phase })
}

/** S3 UploadPart returns an HTTP ETag in quotes. R2UploadedPart.etag is the unquoted value uploadPart() returns. */
export function bindingEtag(value: string): string {
  const trimmed = value.trim()
  if (trimmed.length >= 2 && trimmed.startsWith('"') && trimmed.endsWith('"')) return trimmed.slice(1, -1)
  return trimmed
}

function assemblyReason(error: unknown): 'etag_mismatch' | 'missing_part' | null {
  const message = error instanceof Error ? error.message : ''
  if (message === 'missing_part' || /InvalidPartOrder|missing_part/i.test(message)) return 'missing_part'
  if (message === 'etag_mismatch' || /InvalidPart|specified parts could not be found|entity tag/i.test(message)) return 'etag_mismatch'
  return null
}

async function signParts(deps: Deps, object: ObjectRow, digest?: string, expiresSeconds?: number): Promise<{ number: number; offset: number; length: number; url: string; headers: Record<string, string> }[]> {
  if (!object.partPlan.length) throw new Error('incomplete_plan')
  const multipart = object.partPlan.length > 1
  if (multipart && !object.uploadId) throw new Error('incomplete_plan')
  const signed = []
  for (const part of object.partPlan) {
    if (multipart && !part.contentMd5) throw new Error('incomplete_plan')
    const signature = await deps.signer!.sign({
      key: object.r2Key,
      contentLength: part.length,
      sha256Hex: multipart ? undefined : digest,
      contentMd5Base64: part.contentMd5,
      uploadId: multipart ? object.uploadId ?? undefined : undefined,
      partNumber: multipart ? part.number : undefined,
      expiresSeconds,
    })
    if (signature.headers['content-length'] !== String(part.length)) throw new Error('signer_length_mismatch')
    if (multipart && signature.headers['content-md5'] !== part.contentMd5) throw new Error('signer_length_mismatch')
    signed.push({ number: part.number, offset: part.offset, length: part.length, url: signature.url, headers: signature.headers })
  }
  return signed
}

async function rotateCapability(deps: Deps, row: CaseRow): Promise<string> {
  const capability = token()
  if (!await deps.repo.rotateCapability(row.caseId, await sha256Hex(encoder.encode(capability)), deps.now().toISOString())) {
    throw new Error('case_deleted')
  }
  return capability
}

function requestedTtl(body: Record<string, unknown>, deps: Deps): number | undefined {
  if (body.part_ttl_seconds === undefined) return undefined
  const asked = body.part_ttl_seconds
  if (typeof asked !== 'number' || !Number.isSafeInteger(asked) || asked < 1 || asked > deps.limits.partTtl) return Number.NaN
  return asked
}

async function replayCase(deps: Deps, existing: CaseRow, files: UploadFile[], recoveryToken?: string, expiresSeconds?: number): Promise<Response> {
  if (['deleted', 'deleting'].includes(existing.state)) return json(404, { error: 'not_found' })
  if (existing.state === 'creation_cleanup') return json(503, { error: 'creation_pending' })
  if (existing.state === 'failed') return json(409, { error: 'incomplete_plan' })
  if (files.length && !deps.signer) return json(503, { error: 'upload_signing_unconfigured' })
  const objects = await deps.repo.objectsFor(existing.caseId)
  if (existing.state === 'creating') {
    const manifest = await metadataSize(deps.bucket, `cases/${existing.caseId}/manifest.json`)
    const bytes = objects.reduce((total, object) => total + object.declaredBytes, existing.manifestBytes)
    if (manifest.kind !== 'size' || manifest.size !== existing.manifestBytes || bytes !== existing.reservedBytes ||
        objects.length !== files.length || objects.some((object) => !object.partPlan.length || (object.partPlan.length > 1 && !object.uploadId))) {
      return json(503, { error: 'creation_pending' })
    }
    await deps.repo.finishCreation(existing.caseId, deps.now().toISOString())
    const resumed = await deps.repo.getCase(existing.caseId)
    if (!resumed || !['open', 'complete'].includes(resumed.state)) return json(404, { error: 'not_found' })
    existing = resumed
  }
  const byRole = new Map(objects.map((object) => [object.role, object]))
  const uploads = []
  for (const file of files) {
    const object = byRole.get(file.role)
    if (!object || object.declaredBytes !== file.bytes || object.sha256 !== file.sha256 || !object.partPlan.length) {
      return json(409, { error: 'incomplete_plan' })
    }
    if (object.state === 'complete') {
      const size = await metadataSize(deps.bucket, object.r2Key)
      if (size.kind === 'transient') return json(503, { error: 'unavailable' })
      if (size.kind !== 'size' || size.size !== object.declaredBytes) return json(409, { error: 'incomplete_plan' })
      uploads.push({ object_id: object.objectId, role: object.role, parts: [], already_complete: true, bytes: size.size })
      continue
    }
    if (object.state !== 'reserved') return json(409, { error: 'incomplete_plan' })
    if (object.partPlan.length > 1 && file.part_md5s?.some((digest, index) => digest !== object.partPlan[index]?.contentMd5)) {
      return json(409, { error: 'incomplete_plan' })
    }
    const signed = await signParts(deps, object, file.sha256, expiresSeconds)
    uploads.push({
      object_id: object.objectId, role: object.role, parts: signed,
      url: signed.length === 1 ? signed[0]!.url : undefined,
      headers: signed.length === 1 ? signed[0]!.headers : undefined,
    })
  }
  const current = await deps.repo.getCase(existing.caseId)
  if (!current || !['open', 'complete'].includes(current.state)) return json(404, { error: 'not_found' })
  // New clients persist this credential before create. Replays must not invalidate
  // it when their response is lost. Legacy clients retain the original rotation.
  const capability = existing.recoverySha256 && recoveryToken ? recoveryToken : await rotateCapability(deps, existing)
  return json(200, {
    case_id: existing.caseId,
    capability,
    existing: true,
    expires_at: existing.expiresAt,
    upload_expires_at: new Date(deps.now().getTime() + (expiresSeconds || deps.limits.partTtl) * 1000).toISOString(),
    uploads,
    approval: 'pending',
  })
}

async function createCase(request: Request, deps: Deps): Promise<Response> {
  let body: Record<string, unknown>
  try {
    const raw = new Uint8Array(await request.arrayBuffer())
    if (raw.byteLength > deps.limits.manifestMax + 8192) return json(413, { error: 'too_large' })
    body = JSON.parse(new TextDecoder().decode(raw))
  } catch {
    return json(400, { error: 'bad_json' })
  }
  if (body.purpose !== 'troubleshooting_and_product_improvement' || body.not_for_training !== true) {
    return json(422, { error: 'purpose' })
  }
  const manifest = body.manifest
  const problems = [...manifestProblems(manifest, deps.limits.manifestMax), ...fileProblems(body.files, { ...deps.limits, partBytes: deps.partBytes })]
  if (problems.length) return json(422, { error: 'rejected', reasons: [...new Set(problems)] })
  const files = (body.files as UploadFile[]) || []
  const idempotency = request.headers.get('idempotency-key') || ''
  if (!/^[a-f0-9]{64}$/.test(idempotency)) return json(422, { error: 'idempotency_key' })
  const recoveryToken = typeof body.recovery_token === 'string' ? body.recovery_token : ''
  if (recoveryToken && !/^[A-Za-z0-9_-]{43,128}$/.test(recoveryToken)) return json(422, { error: 'recovery_token' })
  const recoveryHash = recoveryToken ? await sha256Hex(encoder.encode(recoveryToken)) : ''
  const ttl = requestedTtl(body, deps)
  if (Number.isNaN(ttl)) return json(422, { error: 'part_ttl' })
  const manifestBytes = encoder.encode(JSON.stringify(manifest)).byteLength
  const manifestHash = await sha256Hex(encoder.encode(JSON.stringify(manifest)))
  let existing = await deps.repo.findByIdempotency(idempotency)
  if (existing) {
    if (existing.manifestSha256 !== manifestHash) return json(409, { error: 'idempotency_conflict' })
    if (existing.recoverySha256 && existing.recoverySha256 !== recoveryHash) return json(403, { error: 'unauthorized' })
    if (existing.state === 'failed' && existing.reservedBytes === 0 && existing.landedBytes === 0) {
      await deps.repo.forgetFailedCreation(existing.caseId)
      existing = await deps.repo.findByIdempotency(idempotency)
    }
    if (existing) return replayCase(deps, existing, files, recoveryToken, ttl)
  }
  const ip = request.headers.get('cf-connecting-ip') || 'local'
  const hour = deps.now().toISOString().slice(0, 13)
  const rateBucket = await sha256Hex(encoder.encode(`${ip}:${hour}`))
  if (!await deps.repo.hit(rateBucket, deps.limits.ratePerHour)) return json(429, { error: 'rate_limited' })
  if (files.length && !deps.signer) return json(503, { error: 'upload_signing_unconfigured' })
  if (deps.bucketName === 'autoclip-media') return json(500, { error: 'refusing_media_bucket' })
  const total = manifestBytes + files.reduce((sum, file) => sum + file.bytes, 0)
  const caseId = crypto.randomUUID()
  const capability = recoveryToken || token()
  const capabilitySha256 = await sha256Hex(encoder.encode(capability))
  const createdAt = deps.now().toISOString()
  const expires = new Date(deps.now().getTime() + deps.limits.retentionSeconds * 1000).toISOString()
  const row: CaseRow = {
    caseId, idempotencyKey: idempotency, manifestSha256: manifestHash, state: 'creating',
    capabilitySha256, recoverySha256: recoveryHash, consentVersion: String(body.consent_version || ''), manifestBytes,
    reservedBytes: total, landedBytes: 0, createdAt, expiresAt: expires, updatedAt: createdAt,
  }
  // Claim identity and reservation together before writing any object. A cancel
  // that arrives first records a tombstone; a cancel that arrives later finds this row.
  const reserved = await deps.repo.openCase(row, deps.limits)
  if (!reserved.ok) {
    if (reserved.reason === 'cancelled') return json(410, { error: 'cancelled' })
    if (reserved.reason === 'existing' || reserved.reason === 'retry') return json(503, { error: 'creation_pending' })
    return json(413, { error: reserved.reason })
  }
  const manifestKey = `cases/${caseId}/manifest.json`
  try {
    const bytes = encoder.encode(JSON.stringify(manifest))
    if (bytes.byteLength !== manifestBytes) throw new Error('manifest_size')
    await deps.bucket.put(manifestKey, bytes)
    const stored = await metadataSize(deps.bucket, manifestKey)
    if (stored.kind !== 'size' || stored.size !== manifestBytes) throw new Error('manifest_size')
  } catch {
    await purgeCase(deps, row, true)
    return json(500, { error: 'manifest_store_failed' })
  }
  const uploads = []
  const opened: MultipartUpload[] = []
  try {
    for (const file of files) {
      if ((await deps.repo.getCase(caseId))?.state !== 'creating') throw new Error('cancelled')
      const objectId = crypto.randomUUID()
      const key = `cases/${caseId}/${file.role}`
      const planned = partPlan(file.bytes, deps.partBytes)
      const parts = planned.map((part, index) => (
        planned.length > 1 ? { ...part, contentMd5: file.part_md5s?.[index] } : part
      ))
      const multipart = parts.length > 1
      const upload = multipart ? await deps.bucket.createMultipartUpload(key) : null
      if (upload) opened.push(upload)
      const row: ObjectRow = {
        objectId, caseId, role: file.role, r2Key: key, declaredBytes: file.bytes, actualBytes: null,
        sha256: file.sha256, uploadId: upload?.uploadId ?? null, partPlan: parts, state: 'reserved', createdAt, updatedAt: createdAt,
      }
      await deps.repo.saveObject(row)
      const signed = await signParts(deps, row, file.sha256, ttl)
      uploads.push({
        object_id: objectId, role: file.role, parts: signed,
        url: signed.length === 1 ? signed[0]!.url : undefined,
        headers: signed.length === 1 ? signed[0]!.headers : undefined,
      })
    }
  } catch {
    for (const upload of opened) {
      try { await upload.abort() } catch { /* the upload may not exist */ }
    }
    await purgeCase(deps, row, true)
    return json(500, { error: 'signing_failed' })
  }
  if (!await deps.repo.finishCreation(caseId, deps.now().toISOString()) &&
      !['open', 'complete'].includes((await deps.repo.getCase(caseId))?.state || '')) {
    await purgeCase(deps, row)
    return json(410, { error: 'cancelled' })
  }
  return json(201, {
    case_id: caseId,
    capability,
    expires_at: expires,
    upload_expires_at: new Date(deps.now().getTime() + (ttl || deps.limits.partTtl) * 1000).toISOString(),
    uploads,
    checksum_note: 'Completion checks object metadata size only. It does not read the body and does not verify a content hash.',
    approval: 'pending',
  })
}

async function partsFrom(request: Request): Promise<UploadedPart[] | null> {
  try {
    const body = await request.json() as { parts?: { partNumber?: unknown; etag?: unknown }[] }
    if (!Array.isArray(body.parts)) return []
    const parts: UploadedPart[] = []
    for (const part of body.parts) {
      if (typeof part?.partNumber !== 'number' || typeof part.etag !== 'string' || !part.etag) return null
      parts.push({ partNumber: part.partNumber, etag: bindingEtag(part.etag) })
    }
    return parts
  } catch {
    return []
  }
}

async function settleFile(deps: Deps, row: CaseRow, object: ObjectRow, actual: number): Promise<Response> {
  if (row.state === 'deleted') return json(404, { error: 'not_found' })
  try {
    const result = await deps.repo.commitFile(row.caseId, object.objectId, actual, deps.now().toISOString())
    if ('reason' in result) {
      await deps.bucket.delete(object.r2Key)
      return json(404, { error: 'not_found' })
    }
  } catch (error) {
    return unavailable('commit', error)
  }
  return json(200, { ok: true, bytes: actual, integrity: 'metadata_size' })
}

async function rejectInvalid(deps: Deps, row: CaseRow, object: ObjectRow, failure: { phase: string; reason: string; actualBytes: number | null }): Promise<Response> {
  const body = { error: failure.reason, phase: failure.phase, expectedBytes: object.declaredBytes, actualBytes: failure.actualBytes }
  if (object.uploadId) {
    try { await deps.bucket.resumeMultipartUpload(object.r2Key, object.uploadId).abort() }
    catch (error) {
      if (!(error instanceof Error) || !/10024|NoSuchUpload|unknown_upload|does not exist/i.test(error.message)) throw error
    }
  }
  await deps.bucket.delete(object.r2Key)
  await failObject(deps, row, object)
  return json(409, body)
}

async function readObjectUrl(caseId: string, objectId: string, request: Request, deps: Deps): Promise<Response> {
  const row = await authorized(deps.repo, caseId, request)
  if (!row || row.state === 'deleted') return json(404, { error: 'not_found' })
  const object = await deps.repo.getObject(objectId)
  if (!object || object.caseId !== caseId || object.state === 'aborted') return json(404, { error: 'object' })
  const meta = await metadataSize(deps.bucket, object.r2Key)
  if (meta.kind === 'transient') return json(503, { error: 'unavailable' })
  if (meta.kind !== 'size' || meta.size !== object.declaredBytes) return json(404, { error: 'object' })
  if (!deps.signer?.signGet || !deps.signer?.signHead) return json(503, { error: 'upload_signing_unconfigured' })
  const url = await deps.signer.signGet(object.r2Key)
  const headUrl = await deps.signer.signHead(object.r2Key)
  return json(200, { url, head_url: headUrl, expires_in: 120, bytes: meta.size })
}

async function completeFile(caseId: string, objectId: string, request: Request, deps: Deps): Promise<Response> {
  const row = await authorized(deps.repo, caseId, request)
  if (!row || !['open', 'complete', 'failed'].includes(row.state)) return json(404, { error: 'not_found' })
  const object = await deps.repo.getObject(objectId)
  if (!object || object.caseId !== caseId || object.state === 'aborted') return json(404, { error: 'object' })
  const existing = await metadataSize(deps.bucket, object.r2Key)
  if (existing.kind === 'transient') return unavailable('head', existing.detail)
  if (existing.kind === 'size' && existing.size === object.declaredBytes) return settleFile(deps, row, object, existing.size)
  if (existing.kind === 'size') {
    if (object.state === 'complete') return json(409, { error: 'size_mismatch', phase: 'head', expectedBytes: object.declaredBytes, actualBytes: existing.size })
    return rejectInvalid(deps, row, object, { phase: 'head', reason: 'size_mismatch', actualBytes: existing.size })
  }
  if (object.state === 'complete') return json(409, { error: 'size_mismatch', phase: 'head', expectedBytes: object.declaredBytes, actualBytes: null })
  if (!object.uploadId) return rejectInvalid(deps, row, object, { phase: 'complete', reason: 'missing_part', actualBytes: null })
  const parts = await partsFrom(request)
  if (!parts?.length) return json(409, { error: 'incomplete_plan' })
  const expectedNumbers = object.partPlan.map((part) => part.number).sort((left, right) => left - right)
  const gotNumbers = parts.map((part) => part.partNumber).sort((left, right) => left - right)
  if (expectedNumbers.length !== gotNumbers.length || expectedNumbers.some((number, index) => number !== gotNumbers[index])) {
    return rejectInvalid(deps, row, object, { phase: 'complete', reason: 'missing_part', actualBytes: null })
  }
  try {
    await deps.bucket.resumeMultipartUpload(object.r2Key, object.uploadId).complete(parts)
  } catch (error) {
    const after = await metadataSize(deps.bucket, object.r2Key)
    if (after.kind === 'transient') return unavailable('complete', after.detail || error)
    if (after.kind === 'size' && after.size === object.declaredBytes) return settleFile(deps, row, object, after.size)
    if (after.kind === 'size') return rejectInvalid(deps, row, object, { phase: 'complete', reason: 'size_mismatch', actualBytes: after.size })
    const reason = assemblyReason(error)
    if (reason) return rejectInvalid(deps, row, object, { phase: 'complete', reason, actualBytes: null })
    return unavailable('complete', error)
  }
  const verified = await metadataSize(deps.bucket, object.r2Key)
  if (verified.kind === 'transient') return unavailable('verify', verified.detail)
  if (verified.kind === 'size' && verified.size === object.declaredBytes) return settleFile(deps, row, object, verified.size)
  if (verified.kind === 'size') return rejectInvalid(deps, row, object, { phase: 'verify', reason: 'size_mismatch', actualBytes: verified.size })
  return unavailable('verify')
}

async function failObject(deps: Deps, row: CaseRow, object: ObjectRow): Promise<void> {
  await deps.repo.failFile(row.caseId, object.objectId, deps.now().toISOString())
}

async function abortCase(caseId: string, request: Request, deps: Deps): Promise<Response> {
  return deleteCase(caseId, request, deps)
}

async function deleteCase(caseId: string, request: Request, deps: Deps): Promise<Response> {
  const row = await authorized(deps.repo, caseId, request)
  if (!row) return json(404, { error: 'not_found' })
  await purgeCase(deps, row)
  return json(200, { deleted: true })
}

/** Cancel does not replay create and never uploads a manifest or media. */
async function cancelCreation(request: Request, deps: Deps): Promise<Response> {
  let body: { idempotency_key?: unknown; recovery_token?: unknown }
  try {
    const raw = await request.text()
    if (raw.length > 512) return json(413, { error: 'too_large' })
    body = JSON.parse(raw)
  } catch { return json(400, { error: 'bad_json' }) }
  if (!body || typeof body.idempotency_key !== 'string' || !/^[a-f0-9]{64}$/.test(body.idempotency_key) ||
      typeof body.recovery_token !== 'string' || !/^[A-Za-z0-9_-]{43,128}$/.test(body.recovery_token)) return json(422, { error: 'recovery_token' })
  const hash = await sha256Hex(encoder.encode(body.recovery_token))
  const existing = await deps.repo.findByIdempotency(body.idempotency_key)
  if (existing && !timingSafeEqual(existing.recoverySha256 || '', hash)) return json(403, { error: 'unauthorized' })
  if (!existing) {
    const ip = request.headers.get('cf-connecting-ip') || 'local'
    const rateBucket = await sha256Hex(encoder.encode(`cancel:${ip}:${deps.now().toISOString().slice(0, 13)}`))
    if (!await deps.repo.hit(rateBucket, deps.limits.ratePerHour)) return json(429, { error: 'rate_limited' })
  }
  await deps.repo.cancelCreation(body.idempotency_key, hash, deps.now().toISOString())
  const row = await deps.repo.findByIdempotency(body.idempotency_key)
  if (row) {
    if (!timingSafeEqual(row.recoverySha256 || '', hash)) return json(403, { error: 'unauthorized' })
    await purgeCase(deps, row)
  }
  return json(200, { deleted: true })
}

async function purgeCase(deps: Deps, row: CaseRow, creationFailure = false): Promise<void> {
  // Persist the deletion fence before any network operation. Failures leave it
  // retryable, and completion/refresh can no longer revive the case.
  if (creationFailure) {
    if (!await deps.repo.beginCreationCleanup(row.caseId, deps.now().toISOString())) {
      // Cancellation can finish while an earlier storage write is still in flight.
      // Remove its late result too, without resetting the cancellation tombstone.
      const current = await deps.repo.getCase(row.caseId)
      if (current && ['deleting', 'deleted'].includes(current.state)) await purgeCase(deps, current)
      return
    }
  } else {
    await deps.repo.cancelCreation(row.idempotencyKey, row.recoverySha256 || '', deps.now().toISOString())
    await deps.repo.beginDelete(row.caseId, deps.now().toISOString())
  }
  for (const object of await deps.repo.objectsFor(row.caseId)) {
    if (object.uploadId) {
      try { await deps.bucket.resumeMultipartUpload(object.r2Key, object.uploadId).abort() }
      catch (error) {
        if (!(error instanceof Error) || !/10024|NoSuchUpload|unknown_upload|does not exist/i.test(error.message)) throw error
      }
    }
    await deps.bucket.delete(object.r2Key)
  }
  await deps.bucket.delete(`cases/${row.caseId}/manifest.json`)
  await deps.repo.finishDelete(row.caseId, deps.now().toISOString(), creationFailure)
  if (creationFailure) await deps.repo.forgetFailedCreation(row.caseId)
}

export async function sweep(deps: Deps): Promise<{ aborted: number; expired: number; orphans: string[] }> {
  const now = deps.now().getTime()
  let aborted = 0
  let expired = 0
  for (const row of await deps.repo.activeCases()) {
    if (row.state === 'deleted') continue
    if (row.state === 'creation_cleanup') { await purgeCase(deps, row, true); continue }
    const ageSeconds = (now - Date.parse(row.createdAt)) / 1000
    const expiredCase = Date.parse(row.expiresAt) <= now
    const incomplete = ['open', 'creating'].includes(row.state) && ageSeconds >= deps.limits.incompleteSeconds
    if (expiredCase || incomplete || row.state === 'deleting') {
      await purgeCase(deps, row)
      if (incomplete && !expiredCase) aborted += 1
      else expired += 1
    }
  }
  // Writers register ownership before storing bytes. Check ownership *after*
  // listing, so a concurrent case cannot appear only on the storage side.
  const listed = await deps.bucket.list('cases/', new Date(now - 60 * 60 * 1000))
  const orphans = listed.length ? orphanKeys(listed, await deps.repo.liveKeys()) : []
  for (const key of orphans) await deps.bucket.delete(key)
  await deps.repo.reconcile()
  return { aborted, expired, orphans }
}

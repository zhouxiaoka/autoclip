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

export interface StoredObject {
  size: number
  arrayBuffer(): Promise<ArrayBuffer>
}

export interface Bucket {
  put(key: string, body: Uint8Array): Promise<void>
  get(key: string): Promise<StoredObject | null>
  head(key: string): Promise<{ size: number } | null>
  delete(key: string): Promise<void>
  createMultipartUpload(key: string): Promise<MultipartUpload>
  resumeMultipartUpload(key: string, uploadId: string): MultipartUpload
  list(prefix: string): Promise<string[]>
}

export interface Signer {
  sign(input: { key: string; contentLength: number; sha256Hex?: string; uploadId?: string; partNumber?: number }): Promise<{ url: string; headers: Record<string, string> }>
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
  const abort = url.pathname.match(/^\/v1\/cases\/([^/]+)\/abort$/)
  if (request.method === 'POST' && abort) return abortCase(abort[1]!, request, deps)
  const complete = url.pathname.match(/^\/v1\/cases\/([^/]+)\/files\/([^/]+)\/complete$/)
  if (request.method === 'POST' && complete) return completeFile(complete[1]!, complete[2]!, request, deps)
  const remove = url.pathname.match(/^\/v1\/cases\/([^/]+)$/)
  if (request.method === 'DELETE' && remove) return deleteCase(remove[1]!, request, deps)
  if (request.method === 'GET' && url.pathname === '/admin/quota') {
    return admin(request, deps, async () => json(200, { ...(await Promise.resolve(deps.repo.snapshot())), approval: 'pending' }))
  }
  if (request.method === 'POST' && url.pathname === '/admin/reconcile') {
    return admin(request, deps, async () => json(200, { quota: deps.repo.reconcile(), approval: 'pending' }))
  }
  return json(404, { error: 'not_found' })
}

function admin(request: Request, deps: Deps, next: () => Response | Promise<Response>): Response | Promise<Response> {
  if (!deps.adminToken || !timingSafeEqual(bearer(request), deps.adminToken)) return json(401, { error: 'unauthorized' })
  return next()
}

type UploadFile = { role: string; bytes: number; sha256: string; content_type?: string }

async function readableSize(bucket: Bucket, key: string): Promise<number> {
  const stored = await bucket.get(key)
  if (!stored) return -1
  const bytes = new Uint8Array(await stored.arrayBuffer())
  if (bytes.byteLength !== stored.size) return -1
  return bytes.byteLength
}

async function signParts(deps: Deps, object: ObjectRow, digest?: string): Promise<{ number: number; offset: number; length: number; url: string; headers: Record<string, string> }[]> {
  if (!object.partPlan.length) throw new Error('incomplete_plan')
  const multipart = object.partPlan.length > 1
  if (multipart && !object.uploadId) throw new Error('incomplete_plan')
  const signed = []
  for (const part of object.partPlan) {
    const signature = await deps.signer!.sign({
      key: object.r2Key,
      contentLength: part.length,
      sha256Hex: multipart ? undefined : digest,
      uploadId: multipart ? object.uploadId ?? undefined : undefined,
      partNumber: multipart ? part.number : undefined,
    })
    if (signature.headers['content-length'] !== String(part.length)) throw new Error('signer_length_mismatch')
    signed.push({ number: part.number, offset: part.offset, length: part.length, url: signature.url, headers: signature.headers })
  }
  return signed
}

async function rotateCapability(deps: Deps, row: CaseRow): Promise<string> {
  const capability = token()
  row.capabilitySha256 = await sha256Hex(encoder.encode(capability))
  row.updatedAt = deps.now().toISOString()
  await deps.repo.saveCase(row)
  return capability
}

async function replayCase(deps: Deps, existing: CaseRow, files: UploadFile[]): Promise<Response> {
  if (existing.state === 'deleted') return json(404, { error: 'not_found' })
  if (existing.state === 'failed') return json(409, { error: 'incomplete_plan' })
  if (files.length && !deps.signer) return json(503, { error: 'upload_signing_unconfigured' })
  const objects = await deps.repo.objectsFor(existing.caseId)
  const byRole = new Map(objects.map((object) => [object.role, object]))
  const uploads = []
  for (const file of files) {
    const object = byRole.get(file.role)
    if (!object || object.declaredBytes !== file.bytes || object.sha256 !== file.sha256 || !object.partPlan.length) {
      return json(409, { error: 'incomplete_plan' })
    }
    if (object.state === 'complete') {
      const size = await readableSize(deps.bucket, object.r2Key)
      if (size !== object.declaredBytes) return json(409, { error: 'incomplete_plan' })
      uploads.push({ object_id: object.objectId, role: object.role, parts: [], already_complete: true, bytes: size })
      continue
    }
    if (object.state !== 'reserved') return json(409, { error: 'incomplete_plan' })
    const signed = await signParts(deps, object, file.sha256)
    uploads.push({
      object_id: object.objectId, role: object.role, parts: signed,
      url: signed.length === 1 ? signed[0]!.url : undefined,
      headers: signed.length === 1 ? signed[0]!.headers : undefined,
    })
  }
  const capability = await rotateCapability(deps, existing)
  return json(200, {
    case_id: existing.caseId,
    capability,
    existing: true,
    expires_at: existing.expiresAt,
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
  const problems = [...manifestProblems(manifest, deps.limits.manifestMax), ...fileProblems(body.files, deps.limits)]
  if (problems.length) return json(422, { error: 'rejected', reasons: [...new Set(problems)] })
  const files = (body.files as UploadFile[]) || []
  const idempotency = request.headers.get('idempotency-key') || ''
  if (!/^[a-f0-9]{64}$/.test(idempotency)) return json(422, { error: 'idempotency_key' })
  const manifestBytes = encoder.encode(JSON.stringify(manifest)).byteLength
  const manifestHash = await sha256Hex(encoder.encode(JSON.stringify(manifest)))
  const existing = await deps.repo.findByIdempotency(idempotency)
  if (existing) {
    if (existing.manifestSha256 !== manifestHash) return json(409, { error: 'idempotency_conflict' })
    return replayCase(deps, existing, files)
  }
  const ip = request.headers.get('cf-connecting-ip') || 'local'
  const hour = deps.now().toISOString().slice(0, 13)
  const rateBucket = await sha256Hex(encoder.encode(`${ip}:${hour}`))
  if (!await deps.repo.hit(rateBucket, deps.limits.ratePerHour)) return json(429, { error: 'rate_limited' })
  if (files.length && !deps.signer) return json(503, { error: 'upload_signing_unconfigured' })
  if (deps.bucketName === 'autoclip-media') return json(500, { error: 'refusing_media_bucket' })
  const total = manifestBytes + files.reduce((sum, file) => sum + file.bytes, 0)
  const reserved = await deps.repo.reserve(total, deps.limits)
  if (!reserved.ok) return json(413, { error: reserved.reason })
  const caseId = crypto.randomUUID()
  const capability = token()
  const capabilitySha256 = await sha256Hex(encoder.encode(capability))
  const createdAt = deps.now().toISOString()
  const expires = new Date(deps.now().getTime() + deps.limits.retentionSeconds * 1000).toISOString()
  const manifestKey = `cases/${caseId}/manifest.json`
  try {
    const bytes = encoder.encode(JSON.stringify(manifest))
    if (bytes.byteLength !== manifestBytes) throw new Error('manifest_size')
    await deps.bucket.put(manifestKey, bytes)
    const stored = await readableSize(deps.bucket, manifestKey)
    if (stored !== manifestBytes) throw new Error('manifest_size')
  } catch {
    await deps.bucket.delete(manifestKey)
    await deps.repo.release(total)
    return json(500, { error: 'manifest_store_failed' })
  }
  await deps.repo.land(manifestBytes)
  const fileBytes = total - manifestBytes
  const uploads = []
  const opened: MultipartUpload[] = []
  try {
    for (const file of files) {
      const objectId = crypto.randomUUID()
      const key = `cases/${caseId}/${file.role}`
      const parts = partPlan(file.bytes, deps.partBytes)
      const multipart = parts.length > 1
      const upload = multipart ? await deps.bucket.createMultipartUpload(key) : null
      if (upload) opened.push(upload)
      const row: ObjectRow = {
        objectId, caseId, role: file.role, r2Key: key, declaredBytes: file.bytes, actualBytes: null,
        sha256: file.sha256, uploadId: upload?.uploadId ?? null, partPlan: parts, state: 'reserved', createdAt, updatedAt: createdAt,
      }
      const signed = await signParts(deps, row, file.sha256)
      await deps.repo.saveObject(row)
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
    await deps.bucket.delete(manifestKey)
    await deps.repo.unland(manifestBytes)
    await deps.repo.release(fileBytes)
    return json(500, { error: 'signing_failed' })
  }
  const row: CaseRow = {
    caseId, idempotencyKey: idempotency, manifestSha256: manifestHash, state: files.length ? 'open' : 'complete',
    capabilitySha256, consentVersion: String(body.consent_version || ''), manifestBytes,
    reservedBytes: fileBytes, landedBytes: manifestBytes, createdAt, expiresAt: expires, updatedAt: createdAt,
  }
  await deps.repo.saveCase(row)
  return json(201, {
    case_id: caseId,
    capability,
    expires_at: expires,
    uploads,
    checksum_note: 'Completion reads the assembled object and checks its byte length. A whole-object cryptographic rehash is not done inside the Worker.',
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
      parts.push({ partNumber: part.partNumber, etag: part.etag })
    }
    return parts
  } catch {
    return []
  }
}

async function completeFile(caseId: string, objectId: string, request: Request, deps: Deps): Promise<Response> {
  const row = await authorized(deps.repo, caseId, request)
  if (!row || row.state === 'deleted') return json(404, { error: 'not_found' })
  const object = await deps.repo.getObject(objectId)
  if (!object || object.caseId !== caseId) return json(404, { error: 'object' })
  if (object.state === 'complete') {
    const size = await readableSize(deps.bucket, object.r2Key)
    if (size !== object.declaredBytes) return json(409, { error: 'byte_mismatch' })
    return json(200, { ok: true, bytes: size })
  }
  if (object.state !== 'reserved') return json(404, { error: 'object' })
  let actual = 0
  if (object.uploadId) {
    const parts = await partsFrom(request)
    if (!parts?.length) return json(409, { error: 'incomplete_plan' })
    try {
      await deps.bucket.resumeMultipartUpload(object.r2Key, object.uploadId).complete(parts)
    } catch {
      try { await deps.bucket.resumeMultipartUpload(object.r2Key, object.uploadId).abort() } catch { /* already gone */ }
      await deps.bucket.delete(object.r2Key)
      await failObject(deps, row, object)
      return json(409, { error: 'byte_mismatch' })
    }
    actual = await readableSize(deps.bucket, object.r2Key)
    if (actual !== object.declaredBytes) {
      await deps.bucket.delete(object.r2Key)
      await failObject(deps, row, object)
      return json(409, { error: 'byte_mismatch' })
    }
  } else {
    actual = await readableSize(deps.bucket, object.r2Key)
    if (actual !== object.declaredBytes) {
      await deps.bucket.delete(object.r2Key)
      await failObject(deps, row, object)
      return json(409, { error: 'byte_mismatch' })
    }
  }
  object.actualBytes = actual
  object.state = 'complete'
  object.updatedAt = deps.now().toISOString()
  await deps.repo.saveObject(object)
  await deps.repo.land(object.declaredBytes)
  row.reservedBytes = Math.max(0, row.reservedBytes - object.declaredBytes)
  row.landedBytes += object.declaredBytes
  const pending = (await deps.repo.objectsFor(caseId)).filter((item) => item.state === 'reserved')
  if (!pending.length) row.state = 'complete'
  row.updatedAt = object.updatedAt
  await deps.repo.saveCase(row)
  return json(200, { ok: true, bytes: actual })
}

async function failObject(deps: Deps, row: CaseRow, object: ObjectRow): Promise<void> {
  await deps.repo.release(object.declaredBytes)
  object.state = 'aborted'
  object.updatedAt = deps.now().toISOString()
  await deps.repo.saveObject(object)
  row.reservedBytes = Math.max(0, row.reservedBytes - object.declaredBytes)
  row.state = 'failed'
  row.updatedAt = object.updatedAt
  await deps.repo.saveCase(row)
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

async function purgeCase(deps: Deps, row: CaseRow): Promise<void> {
  for (const object of await deps.repo.objectsFor(row.caseId)) {
    if (object.uploadId && object.state === 'reserved') {
      try { await deps.bucket.resumeMultipartUpload(object.r2Key, object.uploadId).abort() } catch { /* already finished */ }
    }
    await deps.bucket.delete(object.r2Key)
    if (object.state === 'reserved') await deps.repo.release(object.declaredBytes)
    object.state = 'aborted'
    await deps.repo.saveObject(object)
  }
  await deps.bucket.delete(`cases/${row.caseId}/manifest.json`)
  if (row.landedBytes) await deps.repo.unland(row.landedBytes)
  row.landedBytes = 0
  row.reservedBytes = 0
  row.state = 'deleted'
  row.updatedAt = deps.now().toISOString()
  await deps.repo.saveCase(row)
}

export async function sweep(deps: Deps): Promise<{ aborted: number; expired: number; orphans: string[] }> {
  const now = deps.now().getTime()
  let aborted = 0
  let expired = 0
  for (const row of await deps.repo.allCases()) {
    if (row.state === 'deleted') continue
    const ageSeconds = (now - Date.parse(row.createdAt)) / 1000
    const expiredCase = Date.parse(row.expiresAt) <= now
    const incomplete = row.state === 'open' && ageSeconds >= deps.limits.incompleteSeconds
    if (expiredCase || incomplete) {
      await purgeCase(deps, row)
      if (incomplete && !expiredCase) aborted += 1
      else expired += 1
    }
  }
  const live = new Set<string>()
  for (const row of await deps.repo.allCases()) {
    if (row.state === 'deleted') continue
    live.add(`cases/${row.caseId}/manifest.json`)
    for (const object of await deps.repo.objectsFor(row.caseId)) {
      if (object.state !== 'aborted') live.add(object.r2Key)
    }
  }
  const orphans = orphanKeys(await deps.bucket.list('cases/'), live)
  for (const key of orphans) await deps.bucket.delete(key)
  await deps.repo.reconcile()
  return { aborted, expired, orphans }
}

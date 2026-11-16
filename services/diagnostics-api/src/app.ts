import { MemoryRepo, type CaseRow, type ObjectRow } from './memory.ts'
import { orphanKeys, type Limits } from './quota.ts'
import { fileProblems, manifestProblems } from './validate.ts'

export interface Bucket {
  put(key: string, body: Uint8Array): Promise<void>
  head(key: string): Promise<{ size: number } | null>
  delete(key: string): Promise<void>
  createMultipartUpload(key: string): Promise<{ uploadId: string }>
  listParts(key: string, uploadId: string): Promise<number[]>
  abortMultipart(key: string, uploadId: string): Promise<void>
  list(prefix: string): Promise<string[]>
}

export interface Signer {
  sign(input: { key: string; contentLength: number; sha256Hex?: string; uploadId?: string; partNumber?: number }): Promise<{ url: string; headers: Record<string, string> }>
}

export interface Deps {
  repo: MemoryRepo
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

async function authorized(repo: MemoryRepo, caseId: string, request: Request): Promise<CaseRow | null> {
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

async function createCase(request: Request, deps: Deps): Promise<Response> {
  const ip = request.headers.get('cf-connecting-ip') || 'local'
  const hour = deps.now().toISOString().slice(0, 13)
  const bucket = await sha256Hex(encoder.encode(`${ip}:${hour}`))
  if (!await deps.repo.hit(bucket, deps.limits.ratePerHour)) return json(429, { error: 'rate_limited' })
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
  const files = (body.files as { role: string; bytes: number; sha256: string; content_type?: string }[]) || []
  const idempotency = request.headers.get('idempotency-key') || ''
  if (!/^[a-f0-9]{64}$/.test(idempotency)) return json(422, { error: 'idempotency_key' })
  const manifestBytes = encoder.encode(JSON.stringify(manifest)).byteLength
  const manifestHash = await sha256Hex(encoder.encode(JSON.stringify(manifest)))
  const existing = await deps.repo.findByIdempotency(idempotency)
  if (existing) {
    if (existing.manifestSha256 !== manifestHash) return json(409, { error: 'idempotency_conflict' })
    return json(200, { case_id: existing.caseId, existing: true })
  }
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
    const head = await deps.bucket.head(manifestKey)
    if (!head || head.size !== manifestBytes) throw new Error('manifest_size')
  } catch {
    await deps.bucket.delete(manifestKey)
    await deps.repo.release(total)
    return json(500, { error: 'manifest_store_failed' })
  }
  await deps.repo.land(manifestBytes)
  const fileBytes = total - manifestBytes
  const uploads = []
  try {
  for (const file of files) {
    const objectId = crypto.randomUUID()
    const key = `cases/${caseId}/${file.role}`
    const parts = partPlan(file.bytes, deps.partBytes)
    const multipart = parts.length > 1
    const uploadId = multipart ? (await deps.bucket.createMultipartUpload(key)).uploadId : null
    const signed = []
    for (const part of parts) {
      const signature = await deps.signer!.sign({
        key, contentLength: part.length, sha256Hex: parts.length === 1 ? file.sha256 : undefined,
        uploadId: uploadId ?? undefined, partNumber: multipart ? part.number : undefined,
      })
      if (signature.headers['content-length'] !== String(part.length)) throw new Error('signer_length_mismatch')
      signed.push({ number: part.number, offset: part.offset, length: part.length, url: signature.url, headers: signature.headers })
    }
    const row: ObjectRow = {
      objectId, caseId, role: file.role, r2Key: key, declaredBytes: file.bytes, actualBytes: null,
      sha256: file.sha256, uploadId, state: 'reserved', createdAt, updatedAt: createdAt,
    }
    await deps.repo.saveObject(row)
    uploads.push({ object_id: objectId, role: file.role, parts: signed, url: signed.length === 1 ? signed[0]!.url : undefined, headers: signed.length === 1 ? signed[0]!.headers : undefined })
  }
  } catch {
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
    checksum_note: 'Per-object size is enforced at complete via HEAD or ListParts. A whole-object rehash is not done inside the Worker.',
    approval: 'pending',
  })
}

async function completeFile(caseId: string, objectId: string, request: Request, deps: Deps): Promise<Response> {
  const row = await authorized(deps.repo, caseId, request)
  if (!row || row.state === 'deleted') return json(404, { error: 'not_found' })
  const object = await deps.repo.getObject(objectId)
  if (!object || object.caseId !== caseId || object.state !== 'reserved') return json(404, { error: 'object' })
  let actual = 0
  if (object.uploadId) {
    const sizes = await deps.bucket.listParts(object.r2Key, object.uploadId)
    actual = sizes.reduce((sum, size) => sum + size, 0)
    if (actual !== object.declaredBytes) {
      await deps.bucket.abortMultipart(object.r2Key, object.uploadId)
      await deps.bucket.delete(object.r2Key)
      await failObject(deps, row, object)
      return json(409, { error: 'byte_mismatch' })
    }
  } else {
    const head = await deps.bucket.head(object.r2Key)
    actual = head?.size ?? -1
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
    if (object.uploadId && object.state === 'reserved') await deps.bucket.abortMultipart(object.r2Key, object.uploadId)
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

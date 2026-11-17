/**
 * Spawns the unmodified harness CLI against a local HTTPS fixture.
 * The fixture checks signed headers and body digests. It is not a production R2 proof.
 */
import assert from 'node:assert/strict'
import { spawn, execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import https from 'node:https'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'
import { handle, type Bucket, type MultipartUpload, type UploadedPart } from '../src/app.ts'
import { MemoryRepo } from '../src/memory.ts'
import { PROPOSED_LIMITS } from '../src/quota.ts'
import { presignGet, presignPut, sha256Base64 } from '../src/sign.ts'

const ACCOUNT = 'fixture'
const BUCKET = 'autoclip-diagnostics'
const SECRET = 'fixture-secret-not-a-live-token'
const KEY_ID = 'fixture-access-key'

function etagOf(bytes: Uint8Array): string {
  return createHash('sha256').update(bytes).digest('hex')
}

class FixtureBucket implements Bucket {
  objects = new Map<string, Uint8Array>()
  private uploads = new Map<string, { key: string; parts: Map<number, Uint8Array> }>()
  async put(key: string, body: Uint8Array): Promise<void> { this.objects.set(key, body) }
  async head(key: string) {
    const body = this.objects.get(key)
    return body ? { size: body.byteLength } : null
  }
  async delete(key: string) { this.objects.delete(key) }
  async createMultipartUpload(key: string): Promise<MultipartUpload> {
    const uploadId = `up-${this.uploads.size + 1}`
    this.uploads.set(uploadId, { key, parts: new Map() })
    return this.resumeMultipartUpload(key, uploadId)
  }
  resumeMultipartUpload(key: string, uploadId: string): MultipartUpload {
    return {
      key, uploadId,
      uploadPart: async (partNumber, value) => {
        const upload = this.uploads.get(uploadId)
        if (!upload || upload.key !== key) throw new Error('unknown_upload')
        upload.parts.set(partNumber, value)
        return { partNumber, etag: etagOf(value) }
      },
      abort: async () => { this.uploads.delete(uploadId) },
      complete: async (uploadedParts: UploadedPart[]) => {
        const upload = this.uploads.get(uploadId)
        if (!upload || upload.key !== key) throw new Error('unknown_upload')
        const ordered = [...uploadedParts].sort((left, right) => left.partNumber - right.partNumber)
        const chunks: Uint8Array[] = []
        let expect = 1
        for (const part of ordered) {
          if (part.partNumber !== expect) throw new Error('missing_part')
          const stored = upload.parts.get(part.partNumber)
          if (!stored || etagOf(stored) !== part.etag) throw new Error('etag_mismatch')
          chunks.push(stored)
          expect += 1
        }
        if (upload.parts.size !== ordered.length) throw new Error('missing_part')
        const size = chunks.reduce((sum, chunk) => sum + chunk.byteLength, 0)
        const body = new Uint8Array(size)
        let offset = 0
        for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.byteLength }
        this.objects.set(key, body)
        this.uploads.delete(uploadId)
        return { size, httpEtag: etagOf(body) }
      },
    }
  }
  async list() { return [...this.objects.keys()] }
}

export function storageDecision(input: {
  issued: boolean
  expired: boolean
  expectedHeaders: Record<string, string>
  gotHeaders: Record<string, string>
  bodyMd5: string
  bodyChecksum: string
  bodyLength: number
}): { status: number; body: string } {
  if (!input.issued || input.expired) return { status: 403, body: 'AccessDenied' }
  for (const [name, expected] of Object.entries(input.expectedHeaders)) {
    if (input.gotHeaders[name] !== expected) return { status: 403, body: 'SignatureDoesNotMatch' }
  }
  if (input.expectedHeaders['content-md5'] && input.bodyMd5 !== input.expectedHeaders['content-md5']) return { status: 400, body: 'BadDigest' }
  if (input.expectedHeaders['x-amz-checksum-sha256'] && input.bodyChecksum !== input.expectedHeaders['x-amz-checksum-sha256']) return { status: 400, body: 'BadDigest' }
  if (input.bodyLength !== Number(input.expectedHeaders['content-length'])) return { status: 400, body: 'IncompleteBody' }
  return { status: 200, body: '' }
}

function expired(url: URL): boolean {
  const stamp = url.searchParams.get('X-Amz-Date') || ''
  const seconds = Number(url.searchParams.get('X-Amz-Expires'))
  if (!/^\d{8}T\d{6}Z$/.test(stamp) || !Number.isFinite(seconds)) return true
  const iso = `${stamp.slice(0, 4)}-${stamp.slice(4, 6)}-${stamp.slice(6, 8)}T${stamp.slice(9, 11)}:${stamp.slice(11, 13)}:${stamp.slice(13, 15)}Z`
  return Date.now() > Date.parse(iso) + seconds * 1000
}

function readBody(req: import('node:http').IncomingMessage): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = []
    req.on('data', (chunk) => chunks.push(chunk))
    req.on('end', () => resolve(Buffer.concat(chunks)))
    req.on('error', reject)
  })
}

test('storage decisions reject a bad signature, a changed header, and a corrupt body separately', () => {
  const headers = { 'content-length': '4', 'content-md5': 'abcd' }
  assert.equal(storageDecision({ issued: false, expired: false, expectedHeaders: headers, gotHeaders: headers, bodyMd5: 'abcd', bodyChecksum: '', bodyLength: 4 }).status, 403)
  assert.equal(storageDecision({ issued: true, expired: false, expectedHeaders: headers, gotHeaders: { ...headers, 'content-md5': 'zzzz' }, bodyMd5: 'abcd', bodyChecksum: '', bodyLength: 4 }).status, 403)
  assert.equal(storageDecision({ issued: true, expired: false, expectedHeaders: headers, gotHeaders: headers, bodyMd5: 'nope', bodyChecksum: '', bodyLength: 4 }).status, 400)
  assert.equal(storageDecision({ issued: true, expired: false, expectedHeaders: headers, gotHeaders: headers, bodyMd5: 'abcd', bodyChecksum: '', bodyLength: 4 }).status, 200)
})

test('unmodified harness CLI completes the local HTTPS control matrix', async () => {
  const root = mkdtempSync(join(tmpdir(), 'autoclip-cli-'))
  const cert = join(root, 'cert.pem')
  const key = join(root, 'key.pem')
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-keyout', key, '-out', cert, '-days', '1', '-nodes',
    '-subj', '/CN=fixture.r2.cloudflarestorage.com',
    '-addext', 'subjectAltName=DNS:fixture.r2.cloudflarestorage.com,IP:127.0.0.1'])
  const issued = new Map<string, { headers: Record<string, string>; key: string; uploadId?: string; partNumber?: number }>()
  const bucket = new FixtureBucket()
  const signer = {
    async sign(input: { key: string; contentLength: number; sha256Hex?: string; contentMd5Base64?: string; uploadId?: string; partNumber?: number; expiresSeconds?: number }) {
      const signed = await presignPut({
        accountId: ACCOUNT, accessKeyId: KEY_ID, secretAccessKey: SECRET, bucket: BUCKET,
        key: input.key, contentLength: input.contentLength,
        checksumSha256Base64: input.sha256Hex ? sha256Base64(input.sha256Hex) : undefined,
        contentMd5Base64: input.contentMd5Base64,
        expiresSeconds: input.expiresSeconds || 900,
        uploadId: input.uploadId, partNumber: input.partNumber,
      })
      const signature = new URL(signed.url).searchParams.get('X-Amz-Signature') || ''
      issued.set(signature, { headers: signed.headers, key: input.key, uploadId: input.uploadId, partNumber: input.partNumber })
      return signed
    },
    async signGet(objectKey: string) {
      const url = await presignGet({ accountId: ACCOUNT, accessKeyId: KEY_ID, secretAccessKey: SECRET, bucket: BUCKET, key: objectKey, expiresSeconds: 120 })
      issued.set(new URL(url).searchParams.get('X-Amz-Signature') || '', { headers: {}, key: objectKey })
      return url
    },
  }
  const deps = {
    repo: new MemoryRepo(), bucket, signer, now: () => new Date(),
    limits: { ...PROPOSED_LIMITS }, adminToken: 'fixture-admin', bucketName: BUCKET, partBytes: 8 * 1024 * 1024,
  }
  const serverLog: string[] = []
  const server = https.createServer({ key: readFileSync(key), cert: readFileSync(cert) }, async (req, res) => {
    serverLog.push(`${req.method} ${req.headers['content-length'] || 0} ${String(req.url).slice(0, 40)}`)
    try {
      const host = String(req.headers.host || '')
      if (req.url === '/reset') { req.socket.destroy(); return }
      if (host.startsWith('127.0.0.1') || host.startsWith('localhost')) {
        const body = await readBody(req)
        const headers = new Headers()
        for (const [name, value] of Object.entries(req.headers)) {
          if (typeof value === 'string' && !['host', 'connection', 'content-length', 'transfer-encoding'].includes(name)) headers.set(name, value)
        }
        const request = new Request(`https://127.0.0.1${req.url}`, { method: req.method, headers, body: body.length ? body : undefined })
        const response = await handle(request, deps)
        const payload = Buffer.from(await response.arrayBuffer())
        serverLog.push(`api ${response.status} ${body.length} ${payload.toString('utf8').slice(0, 120)}`)
        res.writeHead(response.status, { 'content-type': 'application/json', 'cf-ray': 'fixture-local' })
        res.end(payload)
        return
      }
      const url = new URL(req.url || '/', `https://${host}`)
      const signature = url.searchParams.get('X-Amz-Signature') || ''
      const grant = issued.get(signature)
      const objectKey = decodeURIComponent(url.pathname.replace(new RegExp(`^/${BUCKET}/`), ''))
      if (req.method === 'HEAD' || req.method === 'GET') {
        if (!grant || expired(url) || grant.key !== objectKey) { res.writeHead(403); res.end('AccessDenied'); return }
        const stored = bucket.objects.get(objectKey)
        if (!stored) { res.writeHead(404); res.end(); return }
        res.writeHead(200, { 'content-length': String(stored.byteLength), etag: `"${etagOf(stored)}"` })
        res.end(req.method === 'HEAD' ? undefined : Buffer.from(stored))
        return
      }
      if (req.method !== 'PUT') { res.writeHead(405); res.end(); return }
      const body = await readBody(req)
      const got: Record<string, string> = {}
      for (const name of ['content-length', 'content-md5', 'x-amz-checksum-sha256']) {
        const value = req.headers[name]
        if (typeof value === 'string') got[name] = value
      }
      const decision = storageDecision({
        issued: Boolean(grant), expired: expired(url), expectedHeaders: grant?.headers || {},
        gotHeaders: got, bodyLength: body.length,
        bodyMd5: createHash('md5').update(body).digest('base64'),
        bodyChecksum: createHash('sha256').update(body).digest('base64'),
      })
      if (decision.status !== 200 || !grant) { res.writeHead(decision.status); res.end(decision.body); return }
      const bytes = new Uint8Array(body)
      let etag = etagOf(bytes)
      if (grant.uploadId && grant.partNumber) {
        const uploaded = await bucket.resumeMultipartUpload(grant.key, grant.uploadId).uploadPart(grant.partNumber, bytes)
        etag = uploaded.etag
      } else {
        await bucket.put(grant.key, bytes)
      }
      res.writeHead(200, { etag: `"${etag}"`, 'cf-ray': 'fixture-put' })
      res.end()
    } catch (error) {
      serverLog.push(error instanceof Error ? error.stack || error.message : 'fixture')
      res.writeHead(500)
      res.end(error instanceof Error ? error.message : 'fixture')
    }
  })
  server.on('clientError', (error) => serverLog.push(`client ${error.message}`))
  server.keepAliveTimeout = 120_000
  server.requestTimeout = 0
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve))
  const address = server.address()
  if (!address || typeof address === 'string') throw new Error('fixture_port')
  const port = address.port
  const evidence = join(root, 'evidence')
  const reset = await new Promise<string>((resolve, reject) => {
    const req = https.request({ host: '127.0.0.1', port, path: '/reset', method: 'PUT', ca: readFileSync(cert), rejectUnauthorized: true }, () => resolve('unexpected-response'))
    req.on('error', (error: NodeJS.ErrnoException) => resolve(error.code || error.message))
    req.end('x')
  })
  assert.equal(reset, 'ECONNRESET')
  const child = spawn(process.execPath, [process.env.AUTOCLIP_DIAGNOSTICS_HARNESS_ENTRY || 'live/harness.mjs', '--execute'], {
    cwd: join(import.meta.dirname, '..'),
    env: {
      ...process.env,
      AUTOCLIP_DIAGNOSTICS_LIVE: '1',
      AUTOCLIP_DIAGNOSTICS_LIVE_APPROVED: 'staging',
      AUTOCLIP_DIAGNOSTICS_LIVE_ENDPOINT: `https://127.0.0.1:${port}`,
      AUTOCLIP_DIAGNOSTICS_LIVE_BUCKET: BUCKET,
      AUTOCLIP_DIAGNOSTICS_FIXTURE_PORT: String(port),
      AUTOCLIP_DIAGNOSTICS_LIVE_SCOPE: 'through-control',
      AUTOCLIP_DIAGNOSTICS_EVIDENCE: evidence,
      NODE_EXTRA_CA_CERTS: cert,
    },
  })
  let stdout = ''
  let stderr = ''
  child.stdout.on('data', (chunk) => { stdout += chunk })
  child.stderr.on('data', (chunk) => { stderr += chunk })
  const code = await new Promise<number>((resolve) => child.on('exit', (status) => resolve(status ?? 1)))
  server.close()
  assert.equal(stderr.includes('ReferenceError'), false, stderr.slice(0, 500))
  const result = JSON.parse(stdout.trim().split('\n').at(-1) || '{}') as { results: { id: string; pass?: boolean; http?: number; error?: string; reason?: string }[] }
  const row = (id: string) => result.results.find((item) => item.id === id)
  assert.equal(row('independent-readback')?.pass, true, JSON.stringify(result.results?.slice(0, 12)))
  assert.equal(row('control-16mib')?.pass, true)
  assert.equal(row('control-16mib-readback')?.pass, true)
  assert.equal(row('altered-checksum-header')?.http, 403)
  assert.equal(row('corrupt-body-signed-checksum')?.http, 400)
  assert.equal(row('part-altered-md5')?.http, 403)
  assert.equal(row('part-corrupt-body')?.http, 400)
  assert.equal(row('wrong-etag')?.error, 'etag_mismatch')
  assert.equal(row('wrong-etag')?.pass, true)
  assert.equal(row('missing-part')?.error, 'missing_part')
  assert.equal(row('missing-part')?.pass, true)
  assert.equal(row('expired-url')?.pass, true)
  assert.equal(row('expiry-refresh-resume-successful-parts')?.pass, true)
  assert.equal(row('original-max-plus-manifest')?.pass, true, JSON.stringify({ max: row('original-max-plus-manifest'), transport: row('transport-failure'), log: serverLog.filter((line) => line.startsWith('POST') || line.startsWith('api 413') || line.startsWith('api 422') || line.startsWith('api 429') || line.startsWith('api 500')) }))
  assert.equal(row('lost-create-cancel')?.pass, true)
  assert.equal(row('stream-200-mib')?.reason, 'not-run')
  assert.equal(code, 0, stdout.slice(0, 2000))
  rmSync(root, { recursive: true, force: true })
})

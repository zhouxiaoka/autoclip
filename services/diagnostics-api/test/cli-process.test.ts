/**
 * Spawns the unmodified harness CLI against a local HTTPS fixture.
 * The fixture checks signed headers and body digests. It is not a production R2 proof.
 */
import assert from 'node:assert/strict'
import { spawn, execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import https from 'node:https'
import { createReadStream, mkdirSync, mkdtempSync, readFileSync, rmSync, unlinkSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'
import { handle, type Bucket, type MultipartUpload, type UploadedPart } from '../src/app.ts'
import { MemoryRepo } from '../src/memory.ts'
import { PROPOSED_LIMITS } from '../src/quota.ts'
import { presignGet, presignHead, presignPut, sha256Base64 } from '../src/sign.ts'
import { verifySigV4 } from './sigv4-check.mjs'

const ACCOUNT = 'fixture'
const BUCKET = 'autoclip-diagnostics'
const SECRET = 'fixture-secret-not-a-live-token'
const KEY_ID = 'fixture-access-key'

function etagOf(bytes: Uint8Array): string {
  return createHash('sha256').update(bytes).digest('hex')
}

class FixtureBucket implements Bucket {
  objects = new Map<string, { path: string; size: number }>()
  private uploads = new Map<string, { key: string; parts: Map<number, { path: string; size: number; etag: string }> }>()
  private directory: string
  constructor(directory: string) {
    this.directory = directory
    mkdirSync(join(directory, 'objects'), { recursive: true })
    mkdirSync(join(directory, 'parts'), { recursive: true })
  }
  private objectPath(key: string) { return join(this.directory, 'objects', encodeURIComponent(key)) }
  async put(key: string, body: Uint8Array): Promise<void> {
    const path = this.objectPath(key)
    writeFileSync(path, body)
    this.objects.set(key, { path, size: body.byteLength })
  }
  async head(key: string) {
    const stored = this.objects.get(key)
    return stored ? { size: stored.size } : null
  }
  async delete(key: string) {
    const stored = this.objects.get(key)
    if (stored) { try { unlinkSync(stored.path) } catch { /* already gone */ } }
    this.objects.delete(key)
  }
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
        const path = join(this.directory, 'parts', `${uploadId}-${partNumber}`)
        writeFileSync(path, value)
        const etag = etagOf(value)
        upload.parts.set(partNumber, { path, size: value.byteLength, etag })
        return { partNumber, etag }
      },
      abort: async () => {
        const upload = this.uploads.get(uploadId)
        for (const part of upload?.parts.values() || []) { try { unlinkSync(part.path) } catch { /* already gone */ } }
        this.uploads.delete(uploadId)
      },
      complete: async (uploadedParts: UploadedPart[]) => {
        const upload = this.uploads.get(uploadId)
        if (!upload || upload.key !== key) throw new Error('unknown_upload')
        const ordered = [...uploadedParts].sort((left, right) => left.partNumber - right.partNumber)
        let expect = 1
        const files = []
        for (const part of ordered) {
          if (part.partNumber !== expect) throw new Error('missing_part')
          const stored = upload.parts.get(part.partNumber)
          if (!stored || stored.etag !== part.etag) throw new Error('etag_mismatch')
          files.push(stored)
          expect += 1
        }
        if (upload.parts.size !== ordered.length) throw new Error('missing_part')
        const path = this.objectPath(key)
        const hash = createHash('sha256')
        let size = 0
        for (const file of files) {
          const bytes = readFileSync(file.path)
          hash.update(bytes)
          writeFileSync(path, bytes, { flag: size === 0 ? 'w' : 'a' })
          size += bytes.length
        }
        for (const file of files) { try { unlinkSync(file.path) } catch { /* already gone */ } }
        this.objects.set(key, { path, size })
        this.uploads.delete(uploadId)
        return { size, httpEtag: hash.digest('hex') }
      },
    }
  }
  async list() { return [...this.objects.keys()] }
}

function readBody(req: import('node:http').IncomingMessage): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = []
    req.on('data', (chunk) => chunks.push(chunk))
    req.on('end', () => resolve(Buffer.concat(chunks)))
    req.on('error', reject)
  })
}

async function runLive(rstMode: '' | 'signature' | 'digest') {
  const root = mkdtempSync(join(tmpdir(), 'autoclip-cli-'))
  const cert = join(root, 'cert.pem')
  const key = join(root, 'key.pem')
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-keyout', key, '-out', cert, '-days', '1', '-nodes',
    '-subj', '/CN=fixture.r2.cloudflarestorage.com',
    '-addext', 'subjectAltName=DNS:fixture.r2.cloudflarestorage.com,IP:127.0.0.1'])
  const bucket = new FixtureBucket(root)
  const signer = {
    async sign(input: { key: string; contentLength: number; sha256Hex?: string; contentMd5Base64?: string; uploadId?: string; partNumber?: number; expiresSeconds?: number }) {
      return presignPut({
        accountId: ACCOUNT, accessKeyId: KEY_ID, secretAccessKey: SECRET, bucket: BUCKET,
        key: input.key, contentLength: input.contentLength,
        checksumSha256Base64: input.sha256Hex ? sha256Base64(input.sha256Hex) : undefined,
        contentMd5Base64: input.contentMd5Base64,
        expiresSeconds: input.expiresSeconds || 900,
        uploadId: input.uploadId, partNumber: input.partNumber,
      })
    },
    signGet(objectKey: string) {
      return presignGet({ accountId: ACCOUNT, accessKeyId: KEY_ID, secretAccessKey: SECRET, bucket: BUCKET, key: objectKey, expiresSeconds: 120 })
    },
    signHead(objectKey: string) {
      return presignHead({ accountId: ACCOUNT, accessKeyId: KEY_ID, secretAccessKey: SECRET, bucket: BUCKET, key: objectKey, expiresSeconds: 120 })
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
      const hostname = host.replace(/:\d+$/, '')
      const url = new URL(req.url || '/', `https://${hostname}`)
      const presented: Record<string, string> = { host: host }
      for (const name of ['content-length', 'content-md5', 'x-amz-checksum-sha256']) {
        const value = req.headers[name]
        if (typeof value === 'string') presented[name] = value
      }
      const verdict = verifySigV4({
        method: req.method, url: url.toString(), headers: presented,
        secretAccessKey: SECRET, accessKeyId: KEY_ID,
      })
      const objectKey = decodeURIComponent(url.pathname.replace(new RegExp(`^/${BUCKET}/`), ''))
      if (!verdict.ok) {
        if (rstMode === 'signature') { req.socket.destroy(); return }
        res.writeHead(403); res.end(verdict.reason); return
      }
      if (req.method === 'HEAD' || req.method === 'GET') {
        const stored = bucket.objects.get(objectKey)
        if (!stored) { res.writeHead(404); res.end(); return }
        res.writeHead(200, { 'content-length': String(stored.size) })
        if (req.method === 'HEAD') { res.end(); return }
        createReadStream(stored.path).pipe(res)
        return
      }
      if (req.method !== 'PUT') { res.writeHead(405); res.end(); return }
      const body = await readBody(req)
      const md5 = createHash('md5').update(body).digest('base64')
      const checksum = createHash('sha256').update(body).digest('base64')
      if ((presented['content-md5'] && md5 !== presented['content-md5']) || (presented['x-amz-checksum-sha256'] && checksum !== presented['x-amz-checksum-sha256'])) {
        if (rstMode === 'digest') { req.socket.destroy(); return }
        res.writeHead(400); res.end('BadDigest'); return
      }
      if (body.length !== Number(presented['content-length'])) { res.writeHead(400); res.end('IncompleteBody'); return }
      const bytes = new Uint8Array(body)
      const uploadId = url.searchParams.get('uploadId')
      const partNumber = Number(url.searchParams.get('partNumber'))
      let etag = etagOf(bytes)
      if (uploadId && Number.isInteger(partNumber)) {
        const uploaded = await bucket.resumeMultipartUpload(objectKey, uploadId).uploadPart(partNumber, bytes)
        etag = uploaded.etag
      } else {
        await bucket.put(objectKey, bytes)
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
      AUTOCLIP_DIAGNOSTICS_ADMIN_TOKEN: 'fixture-admin',
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
  if (rstMode) {
    const stopped = row(rstMode === 'signature' ? 'tampered-signature' : 'corrupt-body-signed-checksum')
    assert.equal(stopped?.http, 0)
    assert.equal(stopped?.pass, false)
    assert.equal(row('stream-200-mib')?.reason, 'not-run')
    assert.equal(row('fitting-original-under-inflight')?.reason, 'not-run')
    assert.equal(row('control-16mib')?.reason, 'not-run')
    assert.equal(code, 1)
    const evidenceText = readFileSync(join(evidence, 'evidence.json'), 'utf8')
    assert.equal(evidenceText.includes('X-Amz-Signature'), false)
    assert.equal(Array.isArray(JSON.parse(evidenceText).cleanup), true)
    rmSync(root, { recursive: true, force: true })
    return
  }
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
  assert.equal(row('pre-original-max-quota')?.reserved, 0)
  assert.equal(row('pre-fitting-quota')?.reserved, 0)
  assert.equal(row('original-max-plus-manifest')?.capDecision, 'inflight_cap')
  assert.equal(row('original-max-plus-manifest')?.pass, true, JSON.stringify({ max: row('original-max-plus-manifest'), transport: row('transport-failure') }))
  assert.equal(row('lost-create-cancel')?.pass, true)
  assert.equal(row('stream-200-mib')?.pass, true, JSON.stringify(row('stream-200-mib')))
  assert.equal(row('independent-sha256-readback-200mib')?.pass, true)
  assert.equal(row('fitting-original-under-inflight')?.pass, true, JSON.stringify(row('fitting-original-under-inflight')))
  assert.equal(row('fitting-original-readback')?.pass, true, JSON.stringify(row('fitting-original-readback')))
  assert.equal(row('independent-readback')?.headStatus, 200)
  const evidenceText = readFileSync(join(evidence, 'evidence.json'), 'utf8')
  assert.equal(evidenceText.includes('X-Amz-Signature'), false)
  assert.equal(evidenceText.includes('head_url'), false)
  assert.equal(code, 0, stdout.slice(0, 2000))
  rmSync(root, { recursive: true, force: true })
}

test('unmodified harness CLI completes the local HTTPS matrix through the fitting upload', { timeout: 600_000 }, () => runLive(''))
test('a signature reset stops the unmodified CLI before later cases', { timeout: 120_000 }, () => runLive('signature'))
test('a digest reset stops the unmodified CLI before later cases', { timeout: 120_000 }, () => runLive('digest'))

/** SigV4 query signing for one R2 PUT. Content-Length is a signed header, so the URL is not reusable for a different size. */

export interface SignInput {
  accountId: string
  accessKeyId: string
  secretAccessKey: string
  bucket: string
  key: string
  contentLength: number
  checksumSha256Base64?: string
  contentMd5Base64?: string
  expiresSeconds: number
  now?: Date
  uploadId?: string
  partNumber?: number
}

function hex(buf: ArrayBuffer): string {
  return [...new Uint8Array(buf)].map((byte) => byte.toString(16).padStart(2, '0')).join('')
}

/** Encode one SigV4 component. Only unreserved ASCII bytes stay literal. */
export function awsEncode(value: string): string {
  let out = ''
  for (const byte of new TextEncoder().encode(value)) {
    const char = String.fromCharCode(byte)
    out += /[A-Za-z0-9\-._~]/.test(char) ? char : `%${byte.toString(16).toUpperCase().padStart(2, '0')}`
  }
  return out
}

function encodePath(value: string): string {
  return value.split('/').map((part) => awsEncode(part)).join('/')
}

function byteCompare(left: string, right: string): number {
  const a = new TextEncoder().encode(left)
  const b = new TextEncoder().encode(right)
  const length = Math.min(a.length, b.length)
  for (let index = 0; index < length; index += 1) {
    if (a[index] !== b[index]) return a[index]! - b[index]!
  }
  return a.length - b.length
}

async function hmac(key: ArrayBuffer | Uint8Array, data: string): Promise<ArrayBuffer> {
  const raw = key instanceof Uint8Array ? key : new Uint8Array(key)
  const cryptoKey = await crypto.subtle.importKey('raw', raw, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'])
  return crypto.subtle.sign('HMAC', cryptoKey, new TextEncoder().encode(data))
}

function amzDate(now: Date): { date: string; stamp: string } {
  const stamp = now.toISOString().replace(/[:-]|\.\d{3}/g, '')
  return { stamp, date: stamp.slice(0, 8) }
}

export function canonicalPut(input: SignInput, now = input.now ?? new Date()): { url: string; canonical: string; signedHeaders: string } {
  const host = `${input.accountId}.r2.cloudflarestorage.com`
  const { stamp, date } = amzDate(now)
  const credential = `${input.accessKeyId}/${date}/auto/s3/aws4_request`
  const names = ['content-length', 'host']
  if (input.contentMd5Base64) names.push('content-md5')
  if (input.checksumSha256Base64) names.push('x-amz-checksum-sha256')
  names.sort()
  const signed = names.join(';')
  const query: [string, string][] = [
    ['X-Amz-Algorithm', 'AWS4-HMAC-SHA256'],
    ['X-Amz-Credential', credential],
    ['X-Amz-Date', stamp],
    ['X-Amz-Expires', String(input.expiresSeconds)],
    ['X-Amz-SignedHeaders', signed],
  ]
  if (input.partNumber) query.push(['partNumber', String(input.partNumber)])
  if (input.uploadId) query.push(['uploadId', input.uploadId])
  const encoded = query.map(([key, value]) => [awsEncode(key), awsEncode(value)] as [string, string])
  encoded.sort((left, right) => byteCompare(left[0], right[0]) || byteCompare(left[1], right[1]))
  const canonicalQuery = encoded.map(([key, value]) => `${key}=${value}`).join('&')
  const headerLines = [`content-length:${input.contentLength}`, `host:${host}`]
  if (input.contentMd5Base64) headerLines.push(`content-md5:${input.contentMd5Base64}`)
  if (input.checksumSha256Base64) headerLines.push(`x-amz-checksum-sha256:${input.checksumSha256Base64}`)
  headerLines.sort()
  const canonical = [
    'PUT',
    `/${encodePath(input.bucket)}/${encodePath(input.key)}`,
    canonicalQuery,
    `${headerLines.join('\n')}\n`,
    signed,
    'UNSIGNED-PAYLOAD',
  ].join('\n')
  const url = `https://${host}/${encodePath(input.bucket)}/${encodePath(input.key)}?${canonicalQuery}`
  return { url, canonical, signedHeaders: signed }
}

export async function presignPut(input: SignInput): Promise<{ url: string; headers: Record<string, string> }> {
  if (input.bucket === 'autoclip-media') throw new Error('refusing_media_bucket')
  const now = input.now ?? new Date()
  const { url, canonical, signedHeaders } = canonicalPut(input, now)
  const { date } = amzDate(now)
  const secret = new TextEncoder().encode(`AWS4${input.secretAccessKey}`)
  const dateKey = await hmac(secret, date)
  const regionKey = await hmac(dateKey, 'auto')
  const serviceKey = await hmac(regionKey, 's3')
  const signingKey = await hmac(serviceKey, 'aws4_request')
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonical))
  const stringToSign = `AWS4-HMAC-SHA256\n${amzDate(now).stamp}\n${date}/auto/s3/aws4_request\n${hex(hash)}`
  const signature = hex(await hmac(signingKey, stringToSign))
  const headers: Record<string, string> = { 'content-length': String(input.contentLength) }
  if (input.contentMd5Base64) headers['content-md5'] = input.contentMd5Base64
  if (input.checksumSha256Base64) headers['x-amz-checksum-sha256'] = input.checksumSha256Base64
  return { url: `${url}&X-Amz-Signature=${signature}`, headers }
}

export interface ReadSignInput {
  accountId: string
  accessKeyId: string
  secretAccessKey: string
  bucket: string
  key: string
  expiresSeconds: number
  now?: Date
}

/** One signed read. GET and HEAD are different canonical methods and cannot share a URL. */
async function presignRead(method: 'GET' | 'HEAD', input: ReadSignInput): Promise<string> {
  if (input.bucket === 'autoclip-media') throw new Error('refusing_media_bucket')
  const now = input.now ?? new Date()
  const host = `${input.accountId}.r2.cloudflarestorage.com`
  const { stamp, date } = amzDate(now)
  const credential = `${input.accessKeyId}/${date}/auto/s3/aws4_request`
  const signed = 'host'
  const query: [string, string][] = [
    ['X-Amz-Algorithm', 'AWS4-HMAC-SHA256'],
    ['X-Amz-Credential', credential],
    ['X-Amz-Date', stamp],
    ['X-Amz-Expires', String(input.expiresSeconds)],
    ['X-Amz-SignedHeaders', signed],
  ]
  const encoded = query.map(([key, value]) => [awsEncode(key), awsEncode(value)] as [string, string])
  encoded.sort((left, right) => byteCompare(left[0], right[0]) || byteCompare(left[1], right[1]))
  const canonicalQuery = encoded.map(([key, value]) => `${key}=${value}`).join('&')
  const canonical = [
    method,
    `/${encodePath(input.bucket)}/${encodePath(input.key)}`,
    canonicalQuery,
    `host:${host}\n`,
    signed,
    'UNSIGNED-PAYLOAD',
  ].join('\n')
  const secret = new TextEncoder().encode(`AWS4${input.secretAccessKey}`)
  const dateKey = await hmac(secret, date)
  const regionKey = await hmac(dateKey, 'auto')
  const serviceKey = await hmac(regionKey, 's3')
  const signingKey = await hmac(serviceKey, 'aws4_request')
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonical))
  const signature = hex(await hmac(signingKey, `AWS4-HMAC-SHA256\n${stamp}\n${date}/auto/s3/aws4_request\n${hex(hash)}`))
  return `https://${host}/${encodePath(input.bucket)}/${encodePath(input.key)}?${canonicalQuery}&X-Amz-Signature=${signature}`
}

/** Short-lived GET for one object. No session token parameter exists on this signer. */
export function presignGet(input: ReadSignInput): Promise<string> {
  return presignRead('GET', input)
}

/** Short-lived HEAD for the same object. The signature is not valid for GET. */
export function presignHead(input: ReadSignInput): Promise<string> {
  return presignRead('HEAD', input)
}

export function sha256Base64(hexDigest: string): string {
  const bytes = new Uint8Array(hexDigest.match(/.{2}/g)!.map((pair) => Number.parseInt(pair, 16)))
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary)
}

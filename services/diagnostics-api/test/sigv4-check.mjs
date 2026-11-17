/**
 * Independent SigV4 check for the local fixture.
 * It does not call the production signer. A matching signature is necessary
 * and is not sufficient: the HTTP method, path, query, expiry and signed
 * headers are part of the canonical request.
 */
import { createHash, createHmac, timingSafeEqual } from 'node:crypto'

function awsEncode(value) {
  let out = ''
  for (const byte of Buffer.from(String(value), 'utf8')) {
    const char = String.fromCharCode(byte)
    out += /[A-Za-z0-9\-._~]/.test(char) ? char : `%${byte.toString(16).toUpperCase().padStart(2, '0')}`
  }
  return out
}

function byteCompare(left, right) {
  const a = Buffer.from(left)
  const b = Buffer.from(right)
  const length = Math.min(a.length, b.length)
  for (let index = 0; index < length; index += 1) {
    if (a[index] !== b[index]) return a[index] - b[index]
  }
  return a.length - b.length
}

function signingKey(secret, date) {
  const dateKey = createHmac('sha256', `AWS4${secret}`).update(date).digest()
  const regionKey = createHmac('sha256', dateKey).update('auto').digest()
  const serviceKey = createHmac('sha256', regionKey).update('s3').digest()
  return createHmac('sha256', serviceKey).update('aws4_request').digest()
}

export function verifySigV4({ method, url, headers, secretAccessKey, accessKeyId, now = new Date() }) {
  let parsed
  try { parsed = new URL(url) } catch { return { ok: false, reason: 'url' } }
  const signature = parsed.searchParams.get('X-Amz-Signature') || ''
  if (parsed.searchParams.get('X-Amz-Algorithm') !== 'AWS4-HMAC-SHA256') return { ok: false, reason: 'algorithm' }
  const credential = parsed.searchParams.get('X-Amz-Credential') || ''
  const stamp = parsed.searchParams.get('X-Amz-Date') || ''
  const expires = Number(parsed.searchParams.get('X-Amz-Expires'))
  const signedNames = (parsed.searchParams.get('X-Amz-SignedHeaders') || '').split(';').filter(Boolean)
  if (!/^\d{8}T\d{6}Z$/.test(stamp) || !Number.isFinite(expires)) return { ok: false, reason: 'date' }
  const date = stamp.slice(0, 8)
  if (credential !== `${accessKeyId}/${date}/auto/s3/aws4_request`) return { ok: false, reason: 'credential' }
  const issued = Date.parse(`${stamp.slice(0, 4)}-${stamp.slice(4, 6)}-${stamp.slice(6, 8)}T${stamp.slice(9, 11)}:${stamp.slice(11, 13)}:${stamp.slice(13, 15)}Z`)
  if (!Number.isFinite(issued) || now.getTime() > issued + expires * 1000) return { ok: false, reason: 'expired' }
  const pairs = []
  for (const [key, value] of parsed.searchParams) {
    if (key === 'X-Amz-Signature') continue
    pairs.push([awsEncode(key), awsEncode(value)])
  }
  pairs.sort((left, right) => byteCompare(left[0], right[0]) || byteCompare(left[1], right[1]))
  const canonicalQuery = pairs.map(([key, value]) => `${key}=${value}`).join('&')
  const presented = {}
  for (const [name, value] of Object.entries(headers || {})) {
    if (typeof value === 'string') presented[name.toLowerCase()] = value.trim()
  }
  const lines = []
  for (const name of signedNames) {
    if (presented[name] === undefined) return { ok: false, reason: 'missing-signed-header' }
    lines.push(`${name}:${presented[name]}\n`)
  }
  const canonical = [
    String(method || '').toUpperCase(),
    parsed.pathname,
    canonicalQuery,
    lines.join(''),
    signedNames.join(';'),
    'UNSIGNED-PAYLOAD',
  ].join('\n')
  const hash = createHash('sha256').update(canonical).digest('hex')
  const stringToSign = `AWS4-HMAC-SHA256\n${stamp}\n${date}/auto/s3/aws4_request\n${hash}`
  const expected = createHmac('sha256', signingKey(secretAccessKey, date)).update(stringToSign).digest('hex')
  const left = Buffer.from(expected)
  const right = Buffer.from(signature)
  if (left.length !== right.length || !timingSafeEqual(left, right)) return { ok: false, reason: 'signature' }
  return { ok: true }
}

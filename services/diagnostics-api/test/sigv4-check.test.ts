import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import test from 'node:test'
import { presignGet, presignHead, presignPut } from '../src/sign.ts'
import { verifySigV4 } from './sigv4-check.mjs'

const secret = {
  accountId: 'fixture',
  accessKeyId: 'fixture-access-key',
  secretAccessKey: 'fixture-secret-not-a-live-token',
  bucket: 'autoclip-diagnostics',
  key: 'cases/a/excerpt',
  expiresSeconds: 120,
}
const host = 'fixture.r2.cloudflarestorage.com'

test('a GET signature is not a HEAD signature, and a changed signed header fails', async () => {
  const getUrl = await presignGet(secret)
  const headUrl = await presignHead(secret)
  assert.notEqual(getUrl, headUrl)
  const creds = { secretAccessKey: secret.secretAccessKey, accessKeyId: secret.accessKeyId }
  assert.equal(verifySigV4({ method: 'GET', url: getUrl, headers: { host }, ...creds }).ok, true)
  assert.equal(verifySigV4({ method: 'HEAD', url: getUrl, headers: { host }, ...creds }).ok, false)
  assert.equal(verifySigV4({ method: 'HEAD', url: headUrl, headers: { host }, ...creds }).ok, true)
  assert.equal(verifySigV4({ method: 'GET', url: headUrl, headers: { host }, ...creds }).ok, false)
  const body = Buffer.from('abcd')
  const contentMd5 = createHash('md5').update(body).digest('base64')
  const put = await presignPut({ ...secret, contentLength: body.length, contentMd5Base64: contentMd5 })
  const headers = { host, 'content-length': String(body.length), 'content-md5': contentMd5 }
  assert.equal(verifySigV4({ method: 'PUT', url: put.url, headers, ...creds }).ok, true)
  assert.equal(verifySigV4({ method: 'PUT', url: put.url, headers: { ...headers, 'content-md5': 'AAAAAAAAAAAAAAAAAAAAAA==' }, ...creds }).ok, false)
  assert.equal(verifySigV4({ method: 'PUT', url: put.url, headers: { host, 'content-length': String(body.length) }, ...creds }).ok, false)
  assert.notEqual(createHash('md5').update(Buffer.from('abce')).digest('base64'), contentMd5)
})

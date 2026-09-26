const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')
function load(desktop = true) {
  const calls = []
  const events = []
  const window = { location: { href: desktop ? 'http://tauri.localhost/' : 'https://autoclip.example/' }, dispatchEvent: e => events.push(e.type), ...(desktop ? { __TAURI_INTERNALS__: {} } : {}) }
  const config = { getBaseUrl: () => desktop ? 'http://127.0.0.1:56101/api/v1' : '/api/v1', getAuthToken: () => desktop ? 'installation-secret' : '', waitForReady: async () => true }
  const module = { exports: {} }
  const source = fs.readFileSync(path.join(__dirname, '../src/utils/auth.ts'), 'utf8')
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText, {
    module, exports: module.exports, URL, Headers, Event, window,
    require: () => ({ apiConfigManager: config }),
    fetch: async (url, options) => { calls.push({ url, options }); return { ok: true, status: 200, json: async () => ({ token: 'path-ticket', expires_in: 60 }) } },
  })
  return { ...module.exports, calls, events }
}
test('desktop API fetch uses memory capability only for exact backend origin', async () => {
  const auth = load()
  await auth.authenticatedFetch('/api/v1/settings/')
  assert.equal(auth.calls[0].url, 'http://127.0.0.1:56101/api/v1/settings/')
  assert.equal(auth.calls[0].options.headers.get('Authorization'), 'Bearer installation-secret')
  assert.equal(auth.calls[0].options.redirect, 'error')
  for (const url of ['https://evil.example/api/v1/settings', 'http://127.0.0.1:56102/api/v1/settings', 'http://127.0.0.1.evil.example:56101/api/v1/settings']) {
    assert.equal(Object.keys(auth.authHeaders(url)).length, 0)
  }
})
test('media URL gets a scoped ticket, never the installation capability', async () => {
  const auth = load()
  const url = await auth.authorizeMediaUrl('http://127.0.0.1:56101/api/v1/projects/p1/download?clip_id=a%20b')
  assert.equal(JSON.parse(auth.calls[0].options.body).path, '/api/v1/projects/p1/download?clip_id=a%20b')
  assert.equal(new URL(url).searchParams.get('_media'), 'path-ticket')
  assert.equal(new URL(url).searchParams.get('clip_id'), 'a b')
  assert.ok(!url.includes('installation-secret'))
  await assert.rejects(() => auth.authorizeMediaUrl('https://evil.example/api/v1/projects/p1/video'))
})
test('web requests use same-origin cookie and do not retain a bearer', async () => {
  const auth = load(false)
  await auth.authenticatedFetch('/api/auth/login', { method: 'POST', body: '{"token":"example"}' })
  assert.equal(auth.calls[0].options.headers.get('Authorization'), null)
  assert.equal(auth.calls[0].options.credentials, 'same-origin')
  assert.equal(await auth.authorizeMediaUrl('/api/v1/projects/p1/video'), '/api/v1/projects/p1/video')
})

const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path')
const { runInSandbox } = require('./vm-sandbox.cjs')
const ts = require('typescript'), axios = require('axios')

function loadApi(timers) {
  const exports = {}, delays = [], errors = []
  const mocks = {
    axios: { default: axios },
    '../analytics/workflow': {}, '../i18n': { t: x => x },
    '../utils/errorHandler': { errorHandler: { handleError: e => errors.push(e) } },
    '../utils/apiConfig': { apiConfigManager: { getBaseUrl: () => 'http://localhost/api/v1', addListener: () => {} } },
    '../analytics/operations': {}, '../analytics/observer': {}, '../analytics/posthog': {}, '../analytics/events': {},
  }
  const source = fs.readFileSync(path.join(__dirname, '../src/services/api.ts'), 'utf8')
  runInSandbox(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, {
    exports, require: id => { assert.ok(id in mocks, id); return mocks[id] }, console,
    setTimeout: (fn, delay) => { delays.push(delay); if (timers) return timers.add(fn, delay); queueMicrotask(fn) },
    clearTimeout: id => { if (timers) timers.clear(id) },
  })
  return { api: exports.default, delays, errors }
}

function failure(config, status) {
  const response = status ? { status, data: {}, headers: {}, config } : undefined
  return new axios.AxiosError('synthetic failure', status ? 'ERR_BAD_RESPONSE' : 'ECONNABORTED', config, undefined, response)
}

for (const status of [500, 503, undefined]) test(`GET retries are bounded for ${status || 'timeout'}`, async () => {
  const { api, delays, errors } = loadApi()
  const attempts = []
  api.defaults.adapter = async config => {
    attempts.push(config.metadata?.retryCount || 0)
    if (attempts.length > 6) throw new axios.AxiosError('retry guard', 'ERR_BAD_REQUEST', config, undefined, { status: 400, data: {}, config })
    throw failure(config, status)
  }
  await assert.rejects(api.get('/settings/ai-models'))
  assert.deepEqual(attempts, [0, 1, 2])
  assert.deepEqual(delays, [300, 600])
  assert.equal(errors.length, 1)
  assert.ok(errors[0].userMessage)
})

test('a transient GET failure recovers and each new request has a fresh retry budget', async () => {
  const { api } = loadApi()
  const attempts = []
  api.defaults.adapter = async config => {
    const retry = config.metadata?.retryCount || 0
    attempts.push(retry)
    if (!retry) throw failure(config, 500)
    return { status: 200, data: { ready: true }, headers: {}, config }
  }
  assert.deepEqual(await api.get('/settings/ai-models'), { ready: true })
  assert.deepEqual(await api.get('/settings/ai-models'), { ready: true })
  assert.deepEqual(attempts, [0, 1, 0, 1])
})

test('POST failures never retry a mutation', async () => {
  const { api, delays } = loadApi()
  let attempts = 0
  api.defaults.adapter = async config => { attempts++; throw failure(config, 500) }
  await assert.rejects(api.post('/studio/project/produce', {}))
  assert.equal(attempts, 1)
  assert.deepEqual(delays, [])
})

// 418 : retry:false (a generic config flag, not a URL special case) and abort during the retry wait
const netError = config => new axios.AxiosError('Network Error', 'ERR_NETWORK', config)

test('R27c a retry:false GET that hits a network error is sent exactly once', async () => {
  const { api, delays } = loadApi()
  let attempts = 0
  api.defaults.adapter = async config => { attempts++; if (attempts > 6) throw failure(config, 400); throw netError(config) }
  await assert.rejects(api.get('/any/endpoint', { retry: false }))
  assert.equal(attempts, 1, 'no retry for retry:false')
  assert.deepEqual(delays, [])
  attempts = 0
  await assert.rejects(api.get('/any/endpoint', { retry: false, timeout: 5000 }).catch(e => { throw e }))
  assert.equal(attempts, 1)
  attempts = 0
  api.defaults.adapter = async config => { attempts++; if (attempts > 6) throw failure(config, 400); throw failure(config, 500) }
  await assert.rejects(api.get('/other/endpoint', { retry: false }), e => e.response?.status === 500)
  assert.equal(attempts, 1, 'a 500 reaches the caller after one attempt (no retry swallows it)')
  attempts = 0
  await assert.rejects(api.get('/other/endpoint'))
  assert.equal(attempts, 3, 'requests without the flag keep their retries')
})

test('R27c an abort while waiting between retries ends the request at once and sends nothing more', async () => {
  const held = new Map(); let next = 1
  const timers = { add: (fn, ms) => { const id = next++; held.set(id, { fn, ms }); return id }, clear: id => { held.delete(id) } }
  const { api } = loadApi(timers)
  let attempts = 0
  api.defaults.adapter = async config => { attempts++; throw netError(config) }
  const ctrl = new AbortController()
  let settled = null
  const req = api.get('/studio/anything', { signal: ctrl.signal }).then(() => { settled = 'resolved' }, e => { settled = e })
  for (let i = 0; i < 20 && held.size === 0; i++) await Promise.resolve()
  assert.equal(attempts, 1); assert.equal(held.size, 1, 'waiting before the first retry')
  ctrl.abort()
  for (let i = 0; i < 20 && settled === null; i++) await Promise.resolve()
  assert.ok(settled && settled !== 'resolved', 'the abort ends the request immediately, without waiting out the delay')
  assert.ok(axios.isCancel(settled), 'it ends as a cancel')
  assert.equal(held.size, 0, 'the retry timer is cleared')
  for (const { fn } of [...held.values()]) fn()
  await req
  for (let i = 0; i < 20; i++) await Promise.resolve()
  assert.equal(attempts, 1, 'nothing more is sent after the abort')
})

test('R27c a request cancelled by its signal is never retried', async () => {
  const { api, delays } = loadApi()
  let attempts = 0
  const ctrl = new AbortController()
  api.defaults.adapter = async config => { attempts++; ctrl.abort(); throw new axios.CanceledError(undefined, config) }
  await assert.rejects(api.get('/studio/anything', { signal: ctrl.signal }), e => axios.isCancel(e))
  assert.equal(attempts, 1); assert.deepEqual(delays, [])
  attempts = 0  // a cancel that does not come from the signal (e.g. a CancelToken) is not retried either
  api.defaults.adapter = async config => { attempts++; throw new axios.CanceledError(undefined, config) }
  await assert.rejects(api.get('/studio/anything'), e => axios.isCancel(e))
  assert.equal(attempts, 1); assert.deepEqual(delays, [])
})

test('R27c I481 the readiness probe the recovery controller uses is one request: 5s timeout, signal, a 500 is seen', async () => {
  const { api } = loadApi()
  const { loadTs } = require('./load-ts.cjs')
  const dir = path.join(__dirname, '../src/features/studio')
  const { studioApi } = loadTs(path.join(dir, 'api.ts'), {
    '../../analytics/posthog': { captureBusinessEvent() {} }, '../../analytics/workflow': { safeStudioProperties: x => x },
    '../../analytics/studio': {}, '../../analytics/observer': { workflow: {} }, '../../services/api': { default: api },
    './noticeRuntime': { noteWorkspaceCompletion() {} }, './subtitleState': { effectiveSubtitles: () => false }, './types': {},
  }, dir)
  const sent = []
  api.defaults.adapter = async config => { sent.push({ url: config.url, timeout: config.timeout, signal: config.signal }); if (sent.length > 6) throw failure(config, 400); throw failure(config, 500) }
  const ctrl = new AbortController()
  // before the controller read studioApi.readiness; the fallback lets this test fail on behaviour there
  const probe = studioApi.readinessProbe ? signal => studioApi.readinessProbe(signal) : () => studioApi.readiness()
  await assert.rejects(probe(ctrl.signal), e => e.response?.status === 500)
  assert.equal(sent.length, 1, `one attempt, the 500 is not swallowed by retries (sent ${sent.length})`)
  assert.equal(sent[0].url, '/studio/readiness'); assert.equal(sent[0].timeout, 5000); assert.equal(sent[0].signal, ctrl.signal)
})

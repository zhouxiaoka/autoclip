const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm')
const ts = require('typescript'), axios = require('axios')

function loadApi() {
  const exports = {}, delays = [], errors = []
  const mocks = {
    axios: { default: axios },
    '../analytics/workflow': {}, '../i18n': { t: x => x },
    '../utils/errorHandler': { errorHandler: { handleError: e => errors.push(e) } },
    '../utils/apiConfig': { apiConfigManager: { getBaseUrl: () => 'http://localhost/api/v1', addListener: () => {} } },
    '../analytics/operations': {}, '../analytics/observer': {}, '../analytics/posthog': {}, '../analytics/events': {},
  }
  const source = fs.readFileSync(path.join(__dirname, '../src/services/api.ts'), 'utf8')
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, {
    exports, require: id => { assert.ok(id in mocks, id); return mocks[id] }, console,
    setTimeout: (fn, delay) => { delays.push(delay); queueMicrotask(fn) },
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

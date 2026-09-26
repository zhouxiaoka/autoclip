const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

function loadApi({ baseUrl, tauri, invokes }) {
  const file = path.join(__dirname, '../src/services/api.ts')
  const source = fs.readFileSync(file, 'utf8').replaceAll('import.meta.env', '__env')
  const js = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true,
  } }).outputText
  const gets = []
  const blob = new Blob(['video'])
  const window = {
    URL: { createObjectURL: () => 'blob:test', revokeObjectURL() {} },
    ...(tauri ? { __TAURI_INTERNALS__: {} } : {}),
  }
  const mocks = {
    '../i18n': { t: key => key },
    '../utils/auth': { authHeaders: () => ({}), authorizeMediaUrl: async url => url },
    axios: {
      create: () => ({ defaults: {}, interceptors: { request: { use() {} }, response: { use() {} } } }),
      get: async (url) => { gets.push(url); return { data: blob, headers: { 'content-disposition': "attachment; filename*=UTF-8''clip.mp4" } } },
    },
    '../utils/errorHandler': { errorHandler: { handleError() {} } },
    '../utils/apiConfig': { apiConfigManager: {
      getBaseUrl: () => baseUrl,
      addListener() {},
      isReady: () => true,
      waitForReady: async () => true,
    } },
    '../analytics/operations': {
      observeOperation: async (_name, _props, action) => action(),
      observeDownload: async (_props, action) => action(),
      observeMediaResponse: async (_props, action) => action(),
    },
    '../analytics/observer': { workflow: { watch() {}, generation: () => 0, active: () => false } },
    '../analytics/posthog': { captureBusinessEvent() {} },
    '../analytics/events': { trackVideoImported() {}, trackClipsExported() {}, trackProcessingFailed() {} },
    '@tauri-apps/api/core': { invoke: async (_cmd, args) => { invokes.push(args); return { path: '/tmp/clip.mp4', sizeBytes: 5 } } },
    antd: { message: { success() {} } },
  }
  const module = { exports: {} }
  vm.runInNewContext(js, {
    exports: module.exports, module, Blob, console,
    require: (id) => {
      if (id in mocks) return mocks[id]
      throw new Error(`Unexpected dependency: ${id}`)
    },
    window,
    document: { createElement: () => ({ click() {} }), body: { appendChild() {}, removeChild() {} } },
  }, { filename: file })
  return { api: module.exports.projectApi, gets }
}

test('desktop clip playback and download use the local backend, not the webview origin', async () => {
  const invokes = []
  const { api, gets } = loadApi({ baseUrl: 'http://127.0.0.1:56101/api/v1', tauri: true, invokes })
  assert.equal(api.getClipVideoUrl('project', 'clip'), 'http://127.0.0.1:56101/api/v1/projects/project/clips/clip')
  assert.equal(
    api.getCollectionVideoUrl('project', 'collection'),
    'http://127.0.0.1:56101/api/v1/files/projects/project/collections/collection',
  )
  await api.downloadVideo('project', 'clip')
  assert.deepEqual(gets, [])
  assert.equal(invokes[0].url, 'http://127.0.0.1:56101/api/v1/projects/project/download?clip_id=clip')
})

test('browser playback keeps the dev-server relative API path', async () => {
  const invokes = []
  const { api, gets } = loadApi({ baseUrl: '/api/v1', tauri: false, invokes })
  assert.equal(api.getClipVideoUrl('project', 'clip'), '/api/v1/projects/project/clips/clip')
  await api.downloadVideo('project', 'clip')
  assert.deepEqual(invokes, [])
  assert.equal(gets[0], '/api/v1/projects/project/download?clip_id=clip')
})

const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

// Compile the actual source in memory. No new runner dependency or network calls.
function load(name, mocks = {}, globals = {}) {
  const file = path.join(__dirname, '../src/analytics', `${name}.ts`)
  const source = fs.readFileSync(file, 'utf8').replaceAll('import.meta.env', '__env')
  const js = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true,
  } }).outputText
  const module = { exports: {} }
  vm.runInNewContext(js, { exports: module.exports, module, Blob, Date, Math, console,
    __env: { DEV: false, VITE_PUBLIC_POSTHOG_KEY: 'test-only-not-a-real-key' },
    require: (id) => {
      if (id in mocks) return mocks[id]
      throw new Error(`Unexpected dependency: ${id}`)
    }, ...globals }, { filename: file })
  return module.exports
}
const core = load('workflow')
function memory() {
  const data = new Map()
  return { getItem: k => data.get(k) ?? null, setItem: (k, v) => data.set(k, v), removeItem: k => data.delete(k) }
}
const NOW = Date.parse('2026-09-21T01:00:00Z')
function setup(storage = memory(), clock = () => NOW) {
  const events = []
  let enabled = true
  let accepted = true
  const capture = (event, props) => { if (!accepted) return false; events.push({ event, props }); return true }
  const tracker = new core.WorkflowTracker(storage, () => enabled, capture, clock)
  return { tracker, events, storage, capture, enable: v => enabled = v, accept: v => accepted = v }
}
const task = overrides => ({ id: 'task-1', task_type: 'video_processing', status: 'completed',
  created_at: '2026-09-21T01:00:00', started_at: '2026-09-21T01:00:01Z',
  completed_at: '2026-09-21T01:00:06Z', ...overrides })

test('duplicate polling and restart preserve deduplication, actual duration and stable IDs', () => {
  const s = setup(); s.tracker.watch('project', 'p')
  const w = s.tracker.list()[0]
  s.tracker.observeTasks(w, [task()]); s.tracker.observeTasks(w, [task()])
  assert.equal(s.events.length, 3)
  assert.equal(s.events[2].props.duration_ms, 5000)
  const recovered = new core.WorkflowTracker(s.storage, () => true, s.capture, () => NOW)
  recovered.observeTasks(recovered.list()[0], [task()])
  assert.equal(s.events.length, 3)
  assert.equal(new Set(s.events.map(e => e.props.$insert_id)).size, 3)
})
test('historical/non-processing tasks excluded; retries with new task IDs counted', () => {
  const s = setup(); s.tracker.watch('project', 'p'); let w = s.tracker.list()[0]
  s.tracker.observeTasks(w, [task({ created_at: '2026-09-20T01:00:00Z' }), task({ task_type: 'cleanup' })])
  assert.equal(s.events.length, 0)
  s.tracker.observeTasks(w, [task({ status: 'failed' })])
  s.tracker.watch('project', 'p'); w = s.tracker.list()[0]
  s.tracker.observeTasks(w, [task({ id: 'retry-2' })])
  assert.equal(s.events.filter(e => e.event === 'processing_finished').length, 2)
})
test('missing worker timestamps do not invent start or duration; cancellation is distinct', () => {
  const s = setup(); s.tracker.watch('project', 'p')
  s.tracker.observeTasks(s.tracker.list()[0], [task({ status: 'cancelled', started_at: null, completed_at: null })])
  assert.equal(s.events.length, 2)
  assert.equal(s.events[1].props.outcome, 'cancelled')
  assert.equal(s.events[1].props.duration_ms, undefined)
  assert.equal(s.events[1].props.occurred_at, undefined)
})
test('opt-out clears pending watches, invalidates in-flight generation and never replays', () => {
  const s = setup(); s.tracker.watch('project', 'p'); const old = s.tracker.list()[0]
  const generation = s.tracker.generation()
  s.enable(false); assert.equal(s.tracker.list().length, 0)
  s.enable(true); assert.equal(s.tracker.active(generation), false)
  s.tracker.observeTasks(old, [task()]); assert.equal(s.events.length, 0)
  assert.equal(new core.WorkflowTracker(s.storage, () => true, s.capture, () => NOW).list().length, 0)
})
test('failed enqueue is retried; invalid storage and blocked localStorage do not throw', () => {
  const s = setup(); s.tracker.watch('project', 'p'); const w = s.tracker.list()[0]
  s.accept(false); s.tracker.observeTasks(w, [task()]); assert.equal(w.seen.length, 0)
  s.accept(true); s.tracker.observeTasks(w, [task()]); assert.equal(s.events.length, 3)
  const blocked = { getItem() { throw Error('blocked') }, setItem() { throw Error('blocked') }, removeItem() { throw Error('blocked') } }
  const b = setup(blocked); b.tracker.watch('project', 'p'); b.tracker.clear()
  const broken = memory(); broken.setItem(core.WORKFLOW_KEY, '{bad'); assert.equal(setup(broken).tracker.list().length, 0)
})
test('watch retention and capacity bounded', () => {
  const s = setup()
  s.tracker.watch('project', 'old', undefined, NOW - 8 * 86400000)
  for (let i = 0; i < 60; i++) s.tracker.watch('project', `p${i}`)
  assert.equal(s.tracker.list().length, 50)
  assert.equal(s.tracker.list().some(w => w.id === 'old'), false)
})
test('errors and routes contain no original secrets, paths or search parameters', () => {
  assert.equal(core.routeName('/project/private-id?token=secret'), '/project/:id')
  assert.equal(core.routeName('/other/secret'), '/other')
  assert.equal(core.errorCode({ message: 'sk-secret /Users/person.mp4', response: { status: 401 } }), 'http_401')
  assert.equal(core.errorCode({ message: 'secret' }), 'unknown')
})
test('SDK exceptions and unavailable storage cannot break business or override opt-out', () => {
  const captured = []; let config
  const sdk = { init(_key, cfg) { config = cfg }, capture(name, props) { captured.push({ name, props }); return {} },
    opt_out_capturing() {}, opt_in_capturing() {} }
  const blocked = { getItem() { throw Error('blocked') }, setItem() { throw Error('blocked') } }
  const ph = load('posthog', { 'posthog-js': sdk, './workflow': core }, { localStorage: blocked, window: {} })
  ph.initAnalytics(); ph.trackPageview('/project/private?key=secret')
  assert.equal(captured[0].props.route, '/project/:id')
  assert.equal(config.autocapture, false)
  assert.equal(config.disable_session_recording, true)
  ph.setAnalyticsEnabled(false); assert.equal(ph.captureBusinessEvent('test'), false)
  assert.equal(captured.length, 1)
  ph.setAnalyticsEnabled(true); sdk.capture = () => { throw Error('sdk') }
  assert.equal(ph.captureBusinessEvent('test'), false)
})
test('downloads count nonempty bytes, preserve request failure, and stop after consent changes', async () => {
  const s = setup()
  const operations = load('operations', { './posthog': { captureBusinessEvent: s.capture }, './observer': { workflow: s.tracker }, './workflow': core })
  const props = { artifact_type: 'publish_clip' }
  const blob = new Blob(['video'])
  assert.equal(await operations.observeDownload(props, async () => blob), blob)
  assert.equal(s.events.filter(e => e.event === 'media_download_received').length, 1)
  await assert.rejects(operations.observeDownload(props, async () => new Blob([])), /Empty/)
  assert.equal(s.events.filter(e => e.event === 'media_download_received').length, 1)
  const failure = { response: { status: 403 }, message: 'token=secret' }
  await assert.rejects(operations.observeDownload(props, async () => { throw failure }), e => e === failure)
  assert.equal(JSON.stringify(s.events).includes('secret'), false)
  let finish; const pending = operations.observeDownload(props, () => new Promise(r => { finish = r }))
  s.tracker.clear(); finish(blob); await pending
  assert.equal(s.events.filter(e => e.event === 'media_download_received').length, 1)
})

test('actual API entrypoints enroll imports/exports and count every media download path', async () => {
  const s = setup(memory(), () => Date.now())
  const ph = { captureBusinessEvent: s.capture }
  const operations = load('operations', { './posthog': ph, './observer': { workflow: s.tracker }, './workflow': core })
  const blob = new Blob(['video'])
  const transport = {
    defaults: {}, interceptors: { request: { use() {} }, response: { use() {} } },
    async post(url) {
      if (url === '/projects/upload') return { id: 'uploaded' }
      if (url === '/bilibili/download') return { id: 'bilibilitask' }
      if (url === '/youtube/download') return { id: 'youtubetask' }
      if (url.includes('/clips/')) return { ok: true, job_id: 'exportjob' }
      if (url === '/settings/test-api') return { success: false, error: 'secret' }
      return {}
    },
    async get() { return blob },
  }
  const api = load('../services/api', {
    '../i18n': { t: key => key },
    axios: { create: () => transport, get: async () => ({ data: blob, headers: {} }) },
    '../utils/auth': { authHeaders: () => ({}), authorizeMediaUrl: async url => url },
    '../utils/errorHandler': { errorHandler: { handleError() {} } },
    '../utils/apiConfig': { apiConfigManager: { getBaseUrl: () => '/api/v1', addListener() {} } },
    '../analytics/operations': operations, '../analytics/observer': { workflow: s.tracker },
    '../analytics/posthog': ph,
    '../analytics/events': { trackVideoImported() {}, trackClipsExported() {}, trackProcessingFailed() {} },
  }, { FormData, window: { URL: { createObjectURL: () => 'blob:test', revokeObjectURL() {} } },
    document: { createElement: () => ({ click() {} }), body: { appendChild() {}, removeChild() {} } } })
  await api.projectApi.uploadFiles({ video_file: blob, project_name: 'private-name' })
  await api.bilibiliApi.createDownloadTask({ url: 'https://private.invalid/secret' })
  await api.bilibiliApi.createYouTubeDownloadTask({ url: 'https://private.invalid/secret' })
  await api.projectApi.startClipExport('p', 'clip', { preset: 'portrait', subtitles: true })
  await api.projectApi.downloadClip('p', 'clip')
  await api.projectApi.downloadCollection('p', 'collection')
  await api.projectApi.downloadVideo('p', 'clip')
  await api.projectApi.downloadVideo('p', undefined, 'collection')
  await api.projectApi.downloadExport('p', 'exportjob')
  await api.settingsApi.testApiKey('dashscope', 'sk-secret')
  assert.equal(s.events.filter(e => e.event === 'media_download_received').length, 5)
  assert.equal(s.events.find(e => e.event === 'provider_test_finished').props.outcome, 'failed')
  assert.equal(JSON.stringify(s.events).includes('secret'), false)
  assert.equal(s.tracker.list().length, 4)
  const accepted = s.events.filter(e => e.event.endsWith('_accepted'))
  assert.equal(accepted.filter(e => e.event === 'import_accepted').length, 3)
  assert.equal(accepted.filter(e => e.event === 'publish_export_accepted').length, 1)
})

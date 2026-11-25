const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const React = require('react'), { act } = React, h = React.createElement
const { loadTs } = require('./load-ts.cjs')
const studio = path.resolve(__dirname, '../src/features/studio')
const ok = () => ({ analysis_mode: 'auto', ready: true, checks: Object.fromEntries(['analysis','transcription','visual','ffmpeg'].map(key => [key, { ok: true, code: 'configured', repair: 'none' }])) })
async function fixture(options = {}) {
  const { Window } = await import('happy-dom'), window = new Window({ url: 'http://localhost/' })
  const originals = {}, calls = [], routes = [], events = []
  let report = ok(), requested = 0
  const globals = { window, document: window.document, navigator: window.navigator, HTMLElement: window.HTMLElement, localStorage: window.localStorage, File: window.File, FormData: window.FormData, URL: window.URL, IS_REACT_ACT_ENVIRONMENT: true }
  for (const [key, value] of Object.entries(globals)) { originals[key] = Object.getOwnPropertyDescriptor(globalThis, key); Object.defineProperty(globalThis, key, { value, writable: true, configurable: true }) }
  const create = window.document.createElement.bind(window.document)
  window.URL.createObjectURL = () => 'blob:isolated'; window.URL.revokeObjectURL = () => {}
  window.document.createElement = (tag, ...args) => {
    const node = create(tag, ...args)
    if (tag === 'video') Object.defineProperty(node, 'src', { set() { Object.defineProperty(node, 'duration', { value: options.duration ?? 60 }); queueMicrotask(() => node.onloadedmetadata?.()) } })
    return node
  }
  const Btn = ({ children, onClick, disabled, loading }) => h('button', { onClick, disabled: !!(disabled || loading) }, children)
  const mocks = {
    __globals: { ...globals, setInterval, clearInterval, setTimeout, clearTimeout, Promise },
    'react-i18next': { useTranslation() {} }, '../../i18n': { t: key => key, getLocale: () => 'en' },
    'react-router-dom': { useNavigate: () => route => routes.push(route) }, antd: { Select: () => null },
    '../../ui': { Btn, Segmented: ({ options, onChange }) => h('div', null, options.map(o => h('button', { key: o.value, onClick: () => onChange(o.value) }, o.label))), Dialog: () => null, StatusDot: () => null },
    './api': { studioApi: {
      readiness: async () => { requested++; return options.readiness ? options.readiness(report, requested) : report }, readinessProbe: async () => report,
      import: async body => { calls.push(body); if (options.upload) return options.upload(body, calls.length); return { project_id: 'p-' + calls.length } },
      get: async () => ({ generation: { status: 'rendering' } }),
    }, errorText: String, errorCode: () => '' },
    '../../services/api': { speechApi: {} },
    '../../analytics/studio': { trackQuickOutputPlatforms() {}, trackAsrReadiness() {}, trackOneClickStarted() {}, trackOneClickUndone() {}, trackAutoChoiceOverridden() {}, trackImportPreviewShown() {} },
    '../../analytics/experience': { trackExperience() {} }, '../../analytics/workflow': { telemetryId: () => 't-test-aaaaaaaa' },
    '../../analytics/flags': { useFlag: () => false, flagEnabled: key => key === 'import_drop_zone', flagValue: () => 'autostart', flagAssigned: () => false, featureSnapshot: () => ({}) },
    './platformMemory': { hasSuccessHistory: () => !options.first, readRememberedPlatforms: () => null, resolvePlatforms: () => ({ platforms: options.platforms || ['douyin'], source: 'user' }), takeReuseImport: () => null, samePlatforms: () => true, writeRememberedPlatforms() {} },
    './PlatformPicker': { default: ({ value }) => h('div', null, value.join(',')) },
    './TemplatePicker': { default: () => null, templateImportFields: () => ({}) },
    './ImportPreferences': { default: () => null }, './importPreferencesStore': { readImportPreferences: () => null },
    './LiveReplayPicker': { default: () => null }, './ImportSetupCard': { default: () => null }, './StyleProbeLine': { default: () => null },
    './TranscriptionGatePrompt': { default: () => null }, '../settings/OutputCaptionsSetting': { OutputCaptionsSwitch: () => null },
    './transcriptionRecovery': { isRecoveryCode: () => false }, './useTranscriptionRecovery': { useTranscriptionRecovery: () => [{ phase: 'idle' }, { open() {}, close() {}, install() {}, retry() {}, state: { phase: 'idle' } }] },
    './studio.css': {}, './quick-output.css': {},
  }
  const batch = loadTs(path.join(studio, 'BatchVideoImport.tsx'), mocks)
  mocks['./BatchVideoImport'] = batch
  const Parent = loadTs(path.join(studio, 'CreativeImport.tsx'), mocks).default
  const host = document.createElement('div'); document.body.append(host)
  const root = require('react-dom/client').createRoot(host)
  const render = () => root.render(h(Parent, { onImported: async () => { events.push('refresh') } }))
  await act(async () => render()); await flush()
  return { host, calls, routes, events, queue: batch.batchSession,
    setReport: value => { report = value }, probes: () => requested,
    file: (name, data = name, type = 'video/mp4') => new window.File([data], name, { type }),
    pick: async files => { const input = host.querySelector('input[aria-label="视频文件"]'); assert.equal(input.multiple, true); Object.defineProperty(input, 'files', { configurable: true, value: files }); await act(async () => input.dispatchEvent(new window.Event('change', { bubbles: true }))); await flush() },
    drop: async files => { const zone = host.querySelector('.ac-dropzone'); const event = new window.Event('drop', { bubbles: true, cancelable: true }); Object.defineProperty(event, 'dataTransfer', { value: { files, getData: () => '' } }); await act(async () => zone.dispatchEvent(event)); await flush() },
    remount: async () => { await act(async () => root.render(null)); await act(async () => render()); await flush() },
    close: async () => { await act(async () => root.unmount()); host.remove(); window.happyDOM.abort(); window.close(); for (const [key, descriptor] of Object.entries(originals)) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key] } },
  }
}
async function flush() { await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)) }) }
function button(host, label) { return [...host.querySelectorAll('button')].find(node => node.textContent === label) }
async function click(node) { assert.ok(node); await act(async () => node.click()); await flush() }
async function consent(view) { const box = view.host.querySelector('input[type="checkbox"]'); assert.ok(box); await click(box) }

test('multi-file picker opens a pending queue without autostart or sharing the old SRT', async () => {
  const view = await fixture()
  try {
    await view.pick([view.file('a.mp4', 'AAA'), view.file('b.mp4', 'BBB')])
    assert.equal(view.host.querySelector('#batch-import-title').textContent, 'batchImport.title')
    assert.equal(view.host.querySelectorAll('[data-batch-id]').length, 2)
    assert.equal(view.calls.length, 0); assert.equal(view.queue.items.every(item => item.subtitle === null), true)
    await consent(view); await click(button(view.host, 'batchImport.start'))
    assert.deepEqual(view.calls.map(body => body.get('video').name), ['a.mp4','b.mp4'])
    assert.deepEqual(await Promise.all(view.calls.map(body => body.get('video').text())), ['AAA','BBB'])
    assert.ok(view.calls.every(body => body.get('auto_start') === 'true' && body.get('subtitle') === null))
    assert.ok(view.queue.items.every(item => item.status === 'submitted'))
    assert.equal(view.routes.length, 0, 'first successful import must not unmount the rest of the queue')
    assert.ok(!view.host.textContent.includes('batchImport.production.completed'))
  } finally { await view.close() }
})

test('drop keeps each invalid item visible and valid files survive', async () => {
  const view = await fixture()
  try {
    await view.drop([view.file('a.mp4'),view.file('empty.mp4',''),view.file('notes.txt','note','text/plain'),view.file('b.webm','B','video/webm')])
    assert.equal(view.queue.items.length, 4)
    assert.deepEqual(Array.from(view.queue.items, item => item.status), ['waiting','invalid','invalid','waiting'])
    await consent(view); await click(button(view.host, 'batchImport.start'))
    assert.deepEqual(view.calls.map(body => body.get('video').name), ['a.mp4','b.webm'])
  } finally { await view.close() }
})

test('rapid start is serial and cancelling waiting files does not cancel the accepted project', async () => {
  let release
  const gate = new Promise(resolve => { release = resolve })
  const view = await fixture({ upload: async (body, n) => { if (n === 1) await gate; return { project_id: 'p-' + n } } })
  try {
    await view.pick([view.file('a.mp4'),view.file('b.mp4'),view.file('c.mp4')]); await consent(view)
    const start = button(view.host,'batchImport.start'); await act(async () => { start.click(); start.click() }); await flush()
    assert.equal(view.calls.length, 1)
    await click(button(view.host.querySelectorAll('[data-batch-id]')[1], 'batchImport.cancelItem'))
    release(); await flush(); await flush()
    assert.deepEqual(view.calls.map(body => body.get('video').name), ['a.mp4','c.mp4'])
    assert.deepEqual(Array.from(view.queue.items, item => item.status), ['submitted','cancelled','submitted'])
  } finally { release(); await view.close() }
})

test('lost response stops and is never retried; remaining files require another explicit start', async () => {
  const view = await fixture({ upload: async (body, n) => { if (n === 1) throw new Error('PRIVATE RESPONSE'); return { project_id: 'p-' + n } } })
  try {
    await view.pick([view.file('a.mp4'),view.file('b.mp4')]); await consent(view); await click(button(view.host,'batchImport.start'))
    assert.deepEqual(Array.from(view.queue.items, item => item.status), ['unknown','waiting']); assert.equal(view.calls.length,1)
    assert.ok(!view.host.textContent.includes('PRIVATE RESPONSE'))
    await click(button(view.host,'batchImport.start'))
    assert.deepEqual(view.calls.map(body => body.get('video').name), ['a.mp4','b.mp4'])
    assert.equal(view.queue.items[0].status,'unknown')
  } finally { await view.close() }
})

test('per-item SRT covers only that file, and repairing readiness resumes without replaying accepted files', async () => {
  const view = await fixture()
  try {
    await view.pick([view.file('a.mp4'),view.file('b.mp4')]); const report=ok(); report.checks.transcription.ok=false; view.setReport(report)
    const input=view.host.querySelector('input[accept=".srt"]'); Object.defineProperty(input,'files',{ configurable:true,value:[view.file('a.srt','one subtitle','text/plain')] })
    await act(async () => input.dispatchEvent(new window.Event('change',{bubbles:true}))); await consent(view); await click(button(view.host,'batchImport.start'))
    assert.equal(view.calls.length,1); assert.equal(view.calls[0].get('subtitle').name,'a.srt'); assert.equal(view.queue.items[1].status,'blocked')
    view.setReport(ok()); await click(button(view.host,'batchImport.start'))
    assert.equal(view.calls.length,2); assert.equal(view.calls[1].get('video').name,'b.mp4'); assert.equal(view.calls[1].get('subtitle'),null)
    assert.ok(view.probes()>=4)
  } finally { await view.close() }
})

test('long or unknown first source requires its own explicit window choice', async () => {
  const view=await fixture({first:true,duration:4000})
  try {
    await view.pick([view.file('a.mp4'),view.file('b.mp4')]); await consent(view); await click(button(view.host,'batchImport.start'))
    assert.equal(view.calls.length,0); assert.equal(view.queue.items[0].status,'blocked')
    await act(async () => { view.queue.change(view.queue.items[0].id,{window:'first'}); view.queue.change(view.queue.items[1].id,{window:'full'}) })
    await click(button(view.host,'batchImport.start'))
    assert.equal(view.calls[0].get('source_window_end'),'1800'); assert.equal(view.calls[1].get('source_window_end'),null)
  } finally {await view.close()}
})

test('route round trip retains files, pauses in-flight completion and needs explicit resume', async () => {
  let release; const gate=new Promise(resolve=>{release=resolve})
  const view=await fixture({upload:async (body,n)=>{if(n===1) await gate;return {project_id:'p-'+n}}})
  try {
    await view.pick([view.file('a.mp4'),view.file('b.mp4')]);await consent(view)
    await act(async()=>button(view.host,'batchImport.start').click());await flush()
    await view.remount();release();await flush();await flush()
    assert.equal(view.calls.length,1);assert.equal(view.queue.items[1].status,'waiting')
    assert.equal(view.host.querySelectorAll('[data-batch-id]').length,2)
    await consent(view);await click(button(view.host,'batchImport.start'));assert.equal(view.calls.length,2)
    assert.equal(localStorage.length,0, 'no file names, media or paths are stored in browser storage')
  } finally {release();await view.close()}
})

test('HTTP rejection and lost receipts remain distinct without replaying either initial upload', async () => {
  const view = await fixture({ upload: async (body, n) => { if (n === 1) throw { response: { status: 422 } }; return {} } })
  try {
    await view.pick([view.file('a.mp4'),view.file('b.mp4')]);await consent(view);await click(button(view.host,'batchImport.start'))
    assert.equal(view.queue.items[0].status,'failed');assert.equal(view.calls.length,1)
    await click(button(view.host,'batchImport.start'));assert.equal(view.queue.items[1].status,'unknown')
    assert.deepEqual(view.calls.map(body=>body.get('video').name),['a.mp4','b.mp4'])
  } finally {await view.close()}
})

test('pausing during readiness verification does not start an upload afterwards', async () => {
  let release; const gate=new Promise(resolve=>{release=resolve})
  const view=await fixture({readiness:async (report,n)=>{if(n===2)await gate;return report}})
  try {
    await view.pick([view.file('a.mp4'),view.file('b.mp4')]);await consent(view)
    await act(async()=>button(view.host,'batchImport.start').click());await flush()
    assert.equal(view.queue.running,true);await click(button(view.host,'batchImport.pause'))
    release();await flush();await flush();assert.equal(view.calls.length,0)
    assert.equal(view.queue.items[0].status,'blocked');assert.equal(view.queue.items[1].status,'waiting')
  } finally {release();await view.close()}
})

test('YouTube landscape is confirmed explicitly and known short-only files are not uploaded', async () => {
  const view=await fixture({platforms:['youtube_long'],duration:90})
  try {
    await view.pick([view.file('a.mp4'),view.file('b.mp4')]);await consent(view);await click(button(view.host,'batchImport.start'))
    assert.equal(view.calls.length,0);assert.ok(view.host.textContent.includes('batchImport.longConfirm'))
    await click(view.host.querySelectorAll('input[type="checkbox"]')[1]);await click(button(view.host,'batchImport.start'))
    assert.equal(view.calls.length,0);assert.equal(view.queue.items[0].status,'blocked')
  } finally {await view.close()}
})

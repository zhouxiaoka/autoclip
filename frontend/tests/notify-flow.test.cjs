const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

function load(relative, extra = {}) {
  const file = path.join(__dirname, relative)
  const exports = {}
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText
  vm.runInNewContext(code, {
    exports, URL,
    require: id => {
      if (id in extra) return extra[id]
      throw new Error(`unexpected import ${id}`)
    },
  })
  return exports
}

const notice = load('../src/features/studio/completionNotice.ts')
const overrides = load('../src/features/studio/overrides.ts', {
  '../../analytics/flags': { flagAssigned: () => false },
  '../../analytics/studio': { trackAutoChoiceOverridden() {} },
})
const workflow = load('../src/analytics/workflow.ts')

function memory() {
  const data = new Map()
  return { getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, value) }
}

function running(completed = 0) {
  return { createdAt: '2026-10-09T00:00:00Z', status: 'rendering', completed }
}

test('the first look at a generation does not notify, and each later kind is once', async () => {
  const storage = memory()
  const kinds = []
  const sent = []
  const transport = { permission: () => 'default', notify: () => { throw new Error('should not show') } }
  const step = view => notice.applyCompletion({
    projectKey: 'demo', view, enabled: true, storage, transport,
    onKind: kind => kinds.push(kind),
    onSent: (kind, permission) => sent.push([kind, permission]),
  })
  assert.equal(await step(running()), null)
  assert.deepEqual(kinds, [])
  assert.equal(await step(running(1)), 'first_clip')
  assert.equal(await step(running(2)), null)
  assert.equal(await step({ ...running(2), status: 'completed' }), 'all_done')
  assert.equal(await step({ ...running(2), status: 'completed' }), null)
  assert.deepEqual(kinds, ['first_clip', 'all_done'])
  assert.deepEqual(sent, [['first_clip', 'default'], ['all_done', 'default']])
})

test('a run that finishes before a separate first clip sends one notice', async () => {
  const storage = memory()
  const kinds = []
  await notice.applyCompletion({
    projectKey: 'demo', view: running(), enabled: true, storage,
    transport: { permission: () => 'denied', notify: () => ({}) },
    onKind: kind => kinds.push(kind),
  })
  let notified = false
  const kind = await notice.applyCompletion({
    projectKey: 'demo', view: { ...running(1), status: 'completed' }, enabled: true, storage,
    transport: { permission: () => 'denied', notify: () => { notified = true; return {} } },
    onKind: item => kinds.push(item),
  })
  assert.equal(kind, 'all_done')
  assert.equal(notified, false)
  assert.deepEqual(kinds, ['all_done'])
})

test('an already finished project stays quiet, and a failure is its own kind', async () => {
  const storage = memory()
  const kinds = []
  const transport = { permission: () => 'granted', notify: () => ({ onclick() {} }), setBadge() {} }
  assert.equal(await notice.applyCompletion({
    projectKey: 'old', view: { createdAt: 'then', status: 'completed', completed: 2 },
    enabled: true, storage, transport, onKind: kind => kinds.push(kind),
  }), null)
  await notice.applyCompletion({
    projectKey: 'new', view: { createdAt: 'now', status: 'rendering', completed: 0 },
    enabled: true, storage, transport,
  })
  assert.equal(await notice.applyCompletion({
    projectKey: 'new', view: { createdAt: 'now', status: 'failed', completed: 0 },
    enabled: true, storage, transport, onKind: kind => kinds.push(kind),
  }), 'failed')
  assert.deepEqual(kinds, ['failed'])
})

test('a granted notice is shown once, records a click, and a disabled flag does nothing', async () => {
  const storage = memory()
  const opened = []
  const badges = []
  let clicks = 0
  const transport = {
    permission: () => 'granted',
    notify: copy => {
      assert.equal(copy, '第一条成片已经做好')
      assert.equal(copy.includes('demo'), false)
      return { onclick: handler => { clicks = handler } }
    },
    setBadge: count => badges.push(count),
  }
  await notice.applyCompletion({
    projectKey: 'demo', view: running(), enabled: true, storage, transport,
  })
  await notice.applyCompletion({
    projectKey: 'demo', view: running(1), enabled: true, storage, transport,
    onOpened: (kind, permission) => opened.push([kind, permission]),
    onSent: (kind, permission) => opened.push(['sent', kind, permission]),
  })
  assert.equal(badges[0], 1)
  clicks()
  assert.deepEqual(opened, [['sent', 'first_clip', 'granted'], ['first_clip', 'granted']])

  const quiet = memory()
  let called = false
  assert.equal(await notice.applyCompletion({
    projectKey: 'demo', view: running(1), enabled: false, storage: quiet,
    transport: { permission: () => { called = true; return 'granted' }, notify: () => ({}) },
  }), null)
  assert.equal(called, false)
  assert.equal(quiet.getItem('autoclip.notices.v1'), null)
})

test('notice and override events keep enums and drop titles', () => {
  const props = workflow.safeStudioProperties({
    kind: 'first_clip', permission: 'granted', field: 'layout', stage: 'editor',
    title: '私人标题', path: '/Users/secret/video.mp4', url: 'https://example.com/a',
  })
  assert.equal(props.kind, 'first_clip')
  assert.equal(props.permission, 'granted')
  assert.equal(props.field, 'layout')
  assert.equal(props.stage, 'editor')
  assert.equal(JSON.stringify(props).includes('私人'), false)
  assert.equal(JSON.stringify(props).includes('secret'), false)
  assert.equal(workflow.safeStudioProperties({ kind: 'digest', permission: 'prompt', field: 'caption' }).kind, undefined)
  assert.equal(workflow.safeStudioProperties({ field: 'not_exported', stage: 'results_chip' }).field, 'not_exported')
  assert.equal(workflow.safeStudioProperties({ field: 'clip_delete' }).field, 'clip_delete')
})

test('saving a draft reports the automatic choices that actually changed', () => {
  const before = {
    title: '原标题', layout: 'crop',
    scenes: [{ id: 'a', start: 1, end: 4 }, { id: 'b', start: 5, end: 9 }],
  }
  const fields = value => JSON.parse(JSON.stringify(overrides.savedDraftOverrides(value.before, value.after)))
  assert.deepEqual(fields({ before, after: before }), [])
  assert.deepEqual(fields({ before, after: { ...before, title: '新标题' } }), ['title'])
  assert.deepEqual(fields({ before, after: { ...before, layout: 'fit' } }), ['layout'])
  assert.deepEqual(fields({ before, after: {
    ...before, scenes: [{ id: 'a', start: 1, end: 6 }, { id: 'b', start: 5, end: 9 }],
  } }), ['duration'])
  assert.deepEqual(fields({ before, after: {
    ...before, scenes: [{ id: 'a', start: 1, end: 4 }],
  } }), ['clip_delete'])
  assert.deepEqual(fields({ before, after: {
    ...before, scenes: [{ id: 'a', start: 1, end: 4 }, { id: 'c', start: 8, end: 10 }],
  } }), ['clip_swap'])
})

test('leaving without a copy or download is recorded once, and a save cancels it', () => {
  const storage = memory()
  const done = { createdAt: 'run', status: 'completed', completed: 1 }
  assert.equal(overrides.takeUnexportedLeave('demo', { ...done, status: 'rendering' }, storage), false)
  assert.equal(overrides.takeUnexportedLeave('demo', { ...done, completed: 0 }, storage), false)
  assert.equal(overrides.takeUnexportedLeave('demo', done, storage), true)
  assert.equal(overrides.takeUnexportedLeave('demo', done, storage), false)
  const saved = memory()
  overrides.markOutputTaken('demo', saved)
  assert.equal(overrides.takeUnexportedLeave('demo', done, saved), false)
})

test('completion and override wiring stays behind the assigned flags', () => {
  const runtime = fs.readFileSync(path.join(__dirname, '../src/features/studio/noticeRuntime.ts'), 'utf8')
  const importer = fs.readFileSync(path.join(__dirname, '../src/features/studio/CreativeImport.tsx'), 'utf8')
  const editor = fs.readFileSync(path.join(__dirname, '../src/features/studio/StudioEditor.tsx'), 'utf8')
  assert.match(runtime, /flagEnabled\('notify_on_done'\)/)
  assert.match(runtime, /flagAssigned\('notify_on_done'\)/)
  assert.match(runtime, /notification_sent/)
  assert.match(runtime, /notification_opened/)
  assert.match(importer, /flagAssigned\('remember_platforms'\) \|\| flagAssigned\('track_overrides'\)/)
  assert.match(editor, /flagAssigned\('track_overrides'\)/)
  assert.match(editor, /savedDraftOverrides/)
})

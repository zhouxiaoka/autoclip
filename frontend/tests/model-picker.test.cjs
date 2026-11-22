const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const { runInSandbox } = require('./vm-sandbox.cjs')
const ts = require('typescript')
const { loadTs } = require('./load-ts.cjs')

function loadPicker() {
  const jsx = (type, props) => ({ type, props })
  const modules = {
    react: { useState: value => [value, () => {}] },
    'react/jsx-runtime': { jsx, jsxs: jsx },
    antd: { Select: 'Select' }, '../../i18n': { t: s => s }, '../../ui': { Btn: 'Btn' },
    './modelDefaults': { analysisModels: models => models.filter(m => m.analysis !== false) },
    './endpointProvider': loadTs('endpointProvider.ts'),
    './modelSettingsLogic': { connectionReady: () => true, presetKey: c => c.provider },
    './weakLocalTimeline': loadTs('weakLocalTimeline.ts'),
    './WeakLocalTimelineNote': { default: 'weak-note' },
    './LocalRecommendPull': { default: 'local-recommend' },
    './localModelGate': { belowLocalAnalysisGate: () => false, localAnalysisWarnCopy: () => '', localModelSizeLabel: () => '' },
    './modelKind': loadTs('modelKind.ts'),
  }
  const code = ts.transpileModule(fs.readFileSync('src/features/settings/ModelPicker.tsx', 'utf8'),
    { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText
  const module = { exports: {} }
  runInSandbox(code, { module, exports: module.exports, require: name => modules[name] || assert.fail(name) })
  return module.exports.default
}

function findSelect(node) {
  if (!node || typeof node !== 'object') return null
  if (node.type === 'Select' && node.props['aria-label'] === '模型') return node
  if (node.type === 'Select' && node.props['aria-label'] === '生图模型') return node
  const children = node.props?.children
  for (const child of Array.isArray(children) ? children.flat(5) : [children]) {
    const found = findSelect(child)
    if (found) return found
  }
  return null
}

test('analysis custom seedream: option disabled and onChange blocked', () => {
  let search = 'doubao-seedream-5-0-flash-260915'
  const jsx = (type, props) => ({ type, props })
  const modules = {
    react: { useState: (value) => {
      // first call = open, second = search
      if (typeof value === 'boolean') return [true, () => {}]
      return [search, (v) => { search = typeof v === 'function' ? v(search) : v }]
    } },
    'react/jsx-runtime': { jsx, jsxs: jsx },
    antd: { Select: 'Select' }, '../../i18n': { t: s => s }, '../../ui': { Btn: 'Btn' },
    './modelDefaults': { analysisModels: models => models.filter(m => m.analysis !== false) },
    './endpointProvider': loadTs('endpointProvider.ts'),
    './modelSettingsLogic': { connectionReady: () => true, presetKey: c => c.provider },
    './weakLocalTimeline': loadTs('weakLocalTimeline.ts'),
    './WeakLocalTimelineNote': { default: 'weak-note' },
    './LocalRecommendPull': { default: 'local-recommend' },
    './localModelGate': { belowLocalAnalysisGate: () => false, localAnalysisWarnCopy: () => '', localModelSizeLabel: () => '' },
    './modelKind': loadTs('modelKind.ts'),
  }
  const code = ts.transpileModule(fs.readFileSync('src/features/settings/ModelPicker.tsx', 'utf8'),
    { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText
  const module = { exports: {} }
  runInSandbox(code, { module, exports: module.exports, require: name => modules[name] || assert.fail(name) })
  let changed = null
  const tree = module.exports.default({
    role: 'analysis',
    model: '',
    connection: { id: 'c1', provider: 'seed', base_url: 'https://ark.example/api/v3', validation_status: 'ok' },
    list: { source: 'live', models: [{ id: 'doubao-seed-2-1-lite-260915', analysis: true, image: false }] },
    busy: false,
    mode: 'auto',
    onChange: (v) => { changed = v },
    onRefresh() {},
  })
  const select = findSelect(tree)
  assert.ok(select)
  const custom = select.props.options.find(o => o.value === 'doubao-seedream-5-0-flash-260915')
  assert.ok(custom, 'custom seedream option missing')
  assert.equal(custom.disabled, true)
  assert.match(custom.label, /生图模型/)
  select.props.onChange('doubao-seedream-5-0-flash-260915')
  assert.equal(changed, null)
})

test('cover role still lists seedream when image:true', () => {
  const picker = loadPicker()
  const tree = picker({
    role: 'cover',
    model: '',
    connection: { id: 'c1', provider: 'seed', validation_status: 'ok' },
    list: {
      source: 'live',
      models: [
        { id: 'doubao-seed-2-1-lite-260915', analysis: true, image: false },
        { id: 'doubao-seedream-5-0-flash-260915', analysis: false, image: true },
      ],
    },
    busy: false,
    mode: 'auto',
    onChange() {},
    onRefresh() {},
  })
  const select = findSelect(tree)
  assert.ok(select)
  const ids = select.props.options.map(o => o.value)
  assert.equal(ids.length, 1)
  assert.equal(ids[0], 'doubao-seedream-5-0-flash-260915')
})

test('backfill-style flags: analysis list drops seedream, cover keeps it', () => {
  const kind = loadTs('modelKind.ts')
  const ids = ['doubao-seed-2-1-lite-260915', 'doubao-seedream-5-0-flash-260915', 'gpt-4o']
  const models = ids.map(id => ({ id, capability: null, analysis: !kind.isImageMarker(id), image: kind.isImageMarker(id) }))
  assert.equal(models.find(m => m.id.includes('seedream')).image, true)
  assert.equal(models.find(m => m.id.includes('seedream')).analysis, false)
  const analysis = models.filter(m => m.analysis)
  const cover = models.filter(m => m.image)
  assert.equal(analysis.some(m => m.id.includes('seedream')), false)
  assert.equal(cover.some(m => m.id.includes('seedream')), true)
  assert.equal(analysis.some(m => m.id === 'gpt-4o'), true)
})

test('IMAGE_MARKERS locked to backend model_catalog', () => {
  const kind = loadTs('modelKind.ts')
  const src = fs.readFileSync('../backend/core/model_catalog.py', 'utf8')
  const match = src.match(/_IMAGE_MARKERS = \(([\s\S]*?)\)/)
  assert.ok(match)
  const backend = [...match[1].matchAll(/"([^"]+)"/g)].map(m => m[1])
  assert.deepEqual([...kind.IMAGE_MARKERS], backend)
})

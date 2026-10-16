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
    './modelDefaults': { analysisModels: models => models },
    './endpointProvider': loadTs('endpointProvider.ts'),
    './modelSettingsLogic': { connectionReady: () => true, presetKey: c => c.provider },
  }
  const code = ts.transpileModule(fs.readFileSync('src/features/settings/ModelPicker.tsx', 'utf8'),
    { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText
  const module = { exports: {} }
  runInSandbox(code, { module, exports: module.exports, require: name => modules[name] || assert.fail(name) })
  return module.exports.default
}
function findTypeSelect(node) {
  if (!node || typeof node !== 'object') return null
  if (node.type === 'Select' && node.props['aria-label'] === '自定义模型类型') return node
  const children = node.props?.children
  for (const child of Array.isArray(children) ? children.flat(5) : [children]) {
    const found = findTypeSelect(child)
    if (found) return found
  }
  return null
}
for (const provider of ['dashscope', 'compatible', 'openai']) {
  test(`${provider}: unknown model can be explicitly confirmed as multimodal`, () => {
    let chosen
    const picker = loadPicker()({ role: 'analysis', model: 'new-official-model', capability: 'auto',
      connection: { id: 'one', provider }, list: { source: 'live', models: [{ id: 'new-official-model', capability: null }] },
      busy: false, mode: 'auto', onChange() {}, onRefresh() {}, onCapability: value => { chosen = value } })
    const select = findTypeSelect(picker)
    assert.ok(select, 'no way to recover frame analysis when model metadata is missing')
    select.props.onChange('multimodal')
    assert.equal(chosen, 'multimodal')
  })
}
test('known provider capability needs no manual confirmation', () => {
  const picker = loadPicker()({ role: 'analysis', model: 'known-vision',
    connection: { id: 'one', provider: 'dashscope' }, list: { source: 'live', models: [{ id: 'known-vision', capability: 'multimodal' }] },
    busy: false, mode: 'auto', onChange() {}, onRefresh() {}, onCapability() {} })
  assert.equal(findTypeSelect(picker), null)
})


test('every purpose picker hides endpoint-only connections until URL and validation pass', () => {
  const Picker = loadPicker()
  const catalog = loadTs('providerPresets.ts').getCatalog()
  for (const preset of Object.values(catalog.providers).filter(row => !row.base_url && row.protocol !== 'local')) {
    for (const [base_url, validation_status, ready] of [['', 'ok', false], ['https://endpoint.example.test/v1', 'unchecked', false], ['https://endpoint.example.test/v1', 'failed', false], ['https://endpoint.example.test/v1', 'ok', true]]) {
      for (const role of ['analysis', 'vision', 'cover', 'transcription']) {
        const tree = Picker({ role, model: '', connection: { id: 'endpoint', provider: 'compatible', catalog_provider_id: preset.id, base_url, validation_status },
          list: { source: 'live', models: [{ id: 'test-model', analysis: true, capability: 'multimodal', image: true, asr: true, asr_supported: true }] },
          busy: false, mode: 'auto', onChange() {}, onRefresh() {} })
        const select = tree.props.children[0]
        assert.equal(select.props.disabled, !ready, `${preset.id}: ${role}`)
        assert.equal(select.props.options.length, ready ? 1 : 0, `${preset.id}: ${role}`)
      }
    }
  }
})

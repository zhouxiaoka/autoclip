const { test } = require('node:test')
const assert = require('node:assert/strict')
const React = require('react')
const { loadTs } = require('./load-ts.cjs')
const i18n = { t: key => key }
const catalog = loadTs('providerCatalogView.ts', { '../../i18n': i18n })
const optionMock = { default: props => React.createElement('request-options', props) }
const ui = { Row: 'row', Btn: 'button', StatusDot: 'status', Icon: { Back: () => null } }
const mocks = {
  react: { ...React, useState: () => [false, () => {}], useRef: initial => ({ current: initial }) },
  antd: { Input: Object.assign(() => null, { Password: 'password' }), Select: 'select' },
  '../../i18n': i18n, '../../ui': ui,
  '../../utils/externalLinks': { openExternalLink() {} },
  '../../analytics/events': { trackSponsorLinkOpened() {} },
  './CustomRequestOptions': optionMock,
}
const Fields = loadTs('ProviderFields.tsx', mocks).default
const Detail = loadTs('ProviderDetail.tsx', {
  ...mocks, './ProviderFields': { default: Fields },
  '../../components/SpeechRecognitionConfig': { default: () => null },
  './SenseVoiceConfig': { default: () => null }, './TrialRunPanel': { default: () => null },
}).default
function flatten(node) {
  if (node == null || typeof node === 'boolean') return []
  if (Array.isArray(node)) return node.flatMap(flatten)
  if (!React.isValidElement(node)) return [node]
  if (typeof node.type === 'function') return [node, ...flatten(node.type(node.props))]
  return [node, ...flatten(node.props.children)]
}
const connection = extra => ({ id: 'endpoint', name: 'Endpoint', provider: 'compatible', base_url: 'https://fixture-gateway.invalid/v1', image_api: 'auto', image_base_url: '', ...extra })
const settings = { version: 1, saved: true, connections: [], analysis: null, vision: null, cover: null, cover_enabled: false }
function renderDetail(preset, connections = []) {
  const edits = [], ensured = []
  const before = JSON.stringify(connections)
  const tree = Detail({ preset, onBack() {}, m: { settings: { ...settings, connections }, lists: {}, busy: {}, listErrors: {}, lastTrialByConnection: {}, keyHints: {}, testing: false, editConnection: (...args) => edits.push(args), ensureCatalogProvider: (...args) => ensured.push(args) } })
  assert.equal(JSON.stringify(connections), before)
  assert.deepEqual(edits, [])
  assert.deepEqual(ensured, [])
  return { tree, edits, ensured }
}
function secondary(tree) {
  const nodes = flatten(tree)
  for (const panel of nodes.filter(node => node.props?.['data-panel'] === 'connect')) {
    assert.equal(flatten(panel).some(node => node.type === 'request-options'), false)
  }
  const advanced = nodes.find(node => node.type === 'details' && node.props['data-panel'] === 'advanced')
  assert.ok(advanced)
  assert.equal(!!advanced.props.open, false)
  assert.equal(flatten(advanced).find(node => node.type === 'summary').props.children, '高级')
  return flatten(advanced).find(node => node.type === 'request-options')
}

test('credential fields never expose advanced controls or alter saved options', () => {
  for (const c of [connection({}), connection({ provider: 'openai' }), connection({ catalog_provider_id: 'azure-openai', has_http_headers: true, reasoning_effort: 'high', extra_body: { provider_options: 'saved' } })]) {
    const before = JSON.stringify(c), edits = []
    const tree = Fields({ connection: c, placement: 'settings_model', onChoose() {}, onEdit: patch => edits.push(patch) })
    assert.equal(flatten(tree).some(node => node.type === 'request-options'), false)
    assert.equal(JSON.stringify(c), before)
    assert.deepEqual(edits, [])
  }
})

test('compatible catalog pages put their editor only in a default-closed secondary section', () => {
  for (const id of ['siliconflow', 'openrouter', 'azure-openai']) {
    const { tree, ensured } = renderDetail(catalog.catalogPreset(id))
    const editor = secondary(tree)
    assert.ok(editor, id)
    editor.props.onEdit({ reasoning_effort: 'low' })
    assert.deepEqual(ensured, [[id, { reasoning_effort: 'low' }]])
  }
})

test('host-matched local and legacy gateways retain secondary editing without re-exposing the main form', () => {
  for (const provider of ['compatible', 'openai']) {
    const c = connection({ provider, base_url: 'http://localhost:9187/v1', has_http_headers: true, reasoning_effort: 'high' })
    const { tree, edits } = renderDetail(catalog.catalogPreset('ollama'), [c])
    const editor = secondary(tree)
    assert.equal(editor.props.value.base_url, c.base_url)
    assert.equal(editor.props.value.has_http_headers, true)
    assert.equal(editor.props.value.http_headers, undefined)
    editor.props.onEdit({ reasoning_effort: 'low' })
    assert.equal(edits[0][0], c)
    assert.deepEqual(edits[0][1], { reasoning_effort: 'low' })
  }
})

test('actual local compatible presets also keep the advanced area closed by default', () => {
  for (const id of ['ollama', 'lmstudio']) {
    const preset = catalog.catalogPreset(id)
    const { tree } = renderDetail(preset, [connection({ base_url: preset.base_url })])
    assert.ok(secondary(tree))
  }
})

test('saved compatible official connections keep their original edit identities with native accounts present', () => {
  const preset = catalog.catalogPreset('openai')
  for (const nativePresent of [false, true]) {
    const saved = connection({ id: 'saved-compatible', base_url: 'https://api.openai.com/v1', has_http_headers: true, extra_body: { provider_options: 'saved' } })
    const native = connection({ id: 'native-openai', provider: 'openai', base_url: 'https://api.openai.com/v1' })
    const { tree, edits, ensured } = renderDetail(preset, nativePresent ? [native, saved] : [saved])
    const editor = secondary(tree)
    assert.equal(editor.props.value.id, saved.id)
    assert.ok(flatten(tree).includes(saved.name))
    assert.equal(editor.props.value.has_http_headers, true)
    editor.props.onEdit({ reasoning_effort: 'low' })
    assert.equal(edits[0][0], saved)
    assert.deepEqual(edits[0][1], { reasoning_effort: 'low' })
    assert.deepEqual(ensured, [])
  }
})

test('an unrelated saved gateway with the draft id cannot receive new catalog edits', () => {
  const unrelated = connection({ id: 'draft:azure-openai', base_url: 'https://unrelated-gateway.invalid/v1' })
  const { tree, edits, ensured } = renderDetail(catalog.catalogPreset('azure-openai'), [unrelated])
  secondary(tree).props.onEdit({ reasoning_effort: 'low' })
  assert.deepEqual(edits, [])
  assert.deepEqual(ensured, [['azure-openai', { reasoning_effort: 'low' }]])
})

test('creating a real catalog account preserves the draft editor session key', () => {
  const refs = []; let cursor = 0
  const StatefulDetail = loadTs('ProviderDetail.tsx', {
    ...mocks, react: { ...mocks.react, useRef: initial => { const i = cursor++; return refs[i] || (refs[i] = { current: initial }) } },
    './ProviderFields': { default: Fields }, '../../components/SpeechRecognitionConfig': { default: () => null },
    './SenseVoiceConfig': { default: () => null }, './TrialRunPanel': { default: () => null },
  }).default
  const state = { ...settings, connections: [] }
  const created = connection({ id: 'real-created-id', catalog_provider_id: 'azure-openai', base_url: 'https://enterprise.invalid/v1', reasoning_effort: 'low' })
  const props = { preset: catalog.catalogPreset('azure-openai'), onBack() {}, m: { settings: state, lists: {}, busy: {}, listErrors: {}, lastTrialByConnection: {}, keyHints: {}, testing: false, ensureCatalogProvider() { state.connections = [created]; return created.id }, editConnection() {} } }
  cursor = 0
  const before = StatefulDetail(props)
  const key = flatten(before).find(node => node.props?.['data-request-connection-id']).key
  secondary(before).props.onEdit({ reasoning_effort: 'low' })
  cursor = 0
  const after = StatefulDetail(props)
  assert.equal(flatten(after).find(node => node.props?.['data-request-connection-id']).key, key)
  assert.equal(secondary(after).props.value.id, created.id)
})

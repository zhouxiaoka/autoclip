const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

const providers = {
  PROVIDERS: {
    compatible: { name: '自定义' },
    dashscope: { name: '阿里云百炼' },
  },
}
const urls = loadTs('providerUrl.ts')
const defaults = loadTs('modelDefaults.ts')
const access = loadTs('providerAccess.ts', { '../../i18n': { t: x => x }, './providers': providers })
const logic = loadTs('modelSettingsLogic.ts', { './providers': providers, './modelDefaults': defaults, './providerAccess': access, './providerUrl': urls })
const custom = loadTs('customProvider.ts', { './providerUrl': urls, './modelSettingsLogic': logic, './providerAccess': access })

const fresh = () => ({
  version: 1, saved: false,
  connections: [],
  analysis: null, vision: null, cover: null,
  transcription: { provider: 'whisper_local', model: 'base' },
  cover_enabled: false, allow_send_frame: true, analysis_mode: 'auto', allow_visual_screening: true,
  chunk_size: 5000, min_score_threshold: .7, max_clips_per_collection: 5,
})

test('custom provider is OpenAI-compatible only and needs name, url, and an enabled model', () => {
  assert.equal(custom.CUSTOM_PROTOCOL, 'openai_compatible')
  const blank = custom.emptyDraft()
  assert.equal(blank.protocol, 'openai_compatible')
  assert.equal(custom.draftIssue(blank), 'name')
  const named = { ...blank, name: 'Office' }
  assert.equal(custom.draftIssue(named), 'url')
  const withUrl = { ...named, base_url: 'https://gw.example/v1' }
  assert.equal(custom.draftIssue(withUrl), 'models')
  const ready = custom.addManualModel(withUrl, 'office-llm').draft
  assert.equal(custom.draftIssue(ready), null)
  assert.equal(custom.addManualModel(ready, 'office-llm').issue, 'duplicate')
  assert.equal(custom.addManualModel(ready, '   ').issue, 'model_id')
})

test('scenario checkboxes follow model type and vision', () => {
  const language = custom.emptyOffer('gpt-x')
  assert.equal(custom.scenarioAllowed(language.types, false, 'analysis'), true)
  assert.equal(custom.scenarioAllowed(language.types, false, 'vision'), false)
  assert.equal(custom.scenarioAllowed(language.types, true, 'vision'), true)
  assert.equal(custom.scenarioAllowed(['asr'], false, 'transcription'), true)
  assert.equal(custom.scenarioAllowed(['asr'], false, 'analysis'), false)
  assert.equal(custom.scenarioAllowed(['image'], false, 'cover'), true)
  const stripped = custom.constrainOffer({
    id: 'img', display_name: 'Pic', types: ['image'], vision: true, scenarios: ['analysis', 'cover', 'vision'], enabled: true,
  })
  assert.equal(stripped.vision, false)
  assert.equal(stripped.scenarios.join(','), 'cover')
})

test('custom_models win over a live list so discovery cannot drop user attributes', () => {
  const connection = {
    id: 'gw', name: 'Office', provider: 'compatible', base_url: 'https://gw.example/v1',
    image_api: 'auto', image_base_url: '',
    custom_models: [{
      id: 'office-llm', display_name: 'Office LLM', types: ['language'],
      vision: true, scenarios: ['analysis', 'vision'], enabled: true,
    }],
  }
  const live = {
    models: [
      { id: 'other-live', capability: 'text', analysis: true, image: false },
      { id: 'office-llm', capability: 'text', analysis: true, image: false },
    ],
    source: 'live', preview: false, updated_at: 1,
  }
  const merged = custom.mergeCustomList(connection, live)
  const office = merged.models.find(model => model.id === 'office-llm')
  assert.equal(office.capability, 'multimodal')
  assert.equal(office.analysis, true)
  assert.ok(merged.models.some(model => model.id === 'other-live'))
  const seeded = custom.mergeCustomList(connection)
  assert.equal(seeded.models[0].id, 'office-llm')
  assert.equal(seeded.models[0].capability, 'multimodal')
})

test('discover merge keeps manual models; apply writes a compatible connection without touching existing analysis', () => {
  const started = custom.addManualModel({ ...custom.emptyDraft(), name: 'Office', base_url: 'https://gw.example' }, 'keep-me').draft
  const merged = custom.mergeDiscovered(started, [
    { id: 'keep-me', analysis: true, image: false, capability: 'text' },
    { id: 'new-llm', analysis: true, image: false, capability: 'multimodal' },
  ])
  assert.equal(merged.models.find(m => m.id === 'keep-me').enabled, true)
  assert.equal(merged.models.find(m => m.id === 'new-llm').enabled, false)
  const enabled = custom.toggleModel(merged, 'new-llm', true)
  const applied = custom.applyCustomProvider(fresh(), enabled, 'custom-1')
  assert.equal(applied.connections[0].provider, 'compatible')
  assert.equal(applied.connections[0].name, 'Office')
  assert.equal(applied.connections[0].base_url, 'https://gw.example/v1')
  assert.equal(applied.connections[0].base_url_source, 'user')
  assert.equal(applied.connections[0].custom_models[0].id, 'keep-me')
  assert.equal(applied.analysis.connection_id, 'custom-1')
  assert.equal(applied.analysis.model, 'keep-me')
  assert.equal(applied.analysis.model_source, 'user')
  const already = { ...fresh(), connections: [{ id: 'old', name: 'old', provider: 'dashscope', base_url: '', api_key: 'k', image_api: 'auto', image_base_url: '' }], analysis: { connection_id: 'old', model: 'qwen-plus', capability: 'auto' } }
  const added = custom.applyCustomProvider(already, enabled, 'custom-2')
  assert.equal(added.analysis.connection_id, 'old')
  assert.equal(added.connections.at(-1).id, 'custom-2')
})

test('chat completions suffixes and invalid URLs are rejected before fetch', () => {
  assert.equal(custom.normalizedDraftUrl('https://gw.example/v1/chat/completions'), 'https://gw.example/v1')
  for (const url of ['https://infistar.ai/v1', 'https://generativelanguage.googleapis.com/v1beta', 'https://gw.example/v2/chat/completions', 'https://gw.example/v1/v1']) {
    assert.equal(custom.normalizedDraftUrl(url), urls.normalizeProviderBaseUrl(url, 'compatible'))
  }
  assert.equal(custom.draftUrlIssue(''), 'empty')
  assert.equal(custom.draftUrlIssue('not-a-url'), 'invalid')
  assert.equal(custom.draftUrlIssue('https://gw.example/v1'), null)
})

test('custom base URLs reject console hosts and embedded credentials', () => {
  assert.equal(custom.draftUrlIssue('https://user:pass@gw.example/v1'), 'invalid')
  assert.equal(custom.draftUrlIssue('https://user@gw.example/v1'), 'invalid')
  assert.equal(custom.draftUrlIssue('https://platform.openai.com/v1'), 'invalid')
  assert.equal(custom.draftUrlIssue('https://platform.openai.com/api-keys'), 'invalid')
  assert.equal(custom.draftUrlIssue('https://bailian.console.aliyun.com'), 'invalid')
  assert.equal(custom.draftUrlIssue('https://aistudio.google.com'), 'invalid')
  assert.equal(custom.draftUrlIssue('https://api.openai.com/v1'), null)
  assert.equal(custom.draftUrlIssue('https://gw.example/v1'), null)
})

test('firstBoundModel does not fall back to a non-language model', () => {
  const started = custom.addManualModel({ ...custom.emptyDraft(), name: 'Office', base_url: 'https://gw.example/v1' }, 'whisper-x').draft
  const asr = custom.editModel(started, 'whisper-x', { types: ['asr'], scenarios: ['transcription'] })
  assert.equal(custom.firstBoundModel(asr), undefined)
  const applied = custom.applyCustomProvider(fresh(), asr, 'custom-asr')
  assert.equal(applied.analysis, null)
  assert.equal(applied.connections[0].custom_models[0].id, 'whisper-x')
})

test('fetchList ids merge without overwriting a manual model', () => {
  const started = custom.addManualModel({ ...custom.emptyDraft(), name: 'Office', base_url: 'https://gw.example/v1' }, 'keep-me').draft
  const merged = custom.mergeFetched(started, ['keep-me', 'new-llm', ''])
  assert.equal(merged.models.find(model => model.id === 'keep-me').enabled, true)
  assert.equal(merged.models.find(model => model.id === 'new-llm').enabled, false)
})

test('custom dialog and first-run source have no clipboard-paste control', () => {
  const files = [
    'AddCustomProviderDialog.tsx',
    'FirstRunSetup.tsx',
    'customProvider.ts',
    'firstRunGuidance.ts',
  ]
  for (const name of files) {
    const source = fs.readFileSync(path.join(__dirname, '../src/features/settings', name), 'utf8')
    assert.equal(/从剪贴板粘贴|pasteFromClipboard|navigator\.clipboard/i.test(source), false, name)
  }
})

for (const edit of ['base_url', 'api_key']) for (const outcome of ['success', 'negative', 'reject']) test(`custom dialog discards stale ${outcome} after ${edit} changes`, async () => {
  const React = require('react')
  const source = fs.readFileSync(path.join(__dirname, '../src/features/settings/AddCustomProviderDialog.tsx'), 'utf8')
  assert.match(source, /modelSettingsApi\.fetchList/)
  assert.equal(/modelSettingsApi\.discover/.test(source), false)
  const pending = []
  let cursor = 0
  const slots = []
  const react = {
    useState(value) {
      const i = cursor++
      if (!(i in slots)) slots[i] = typeof value === 'function' ? value() : value
      return [slots[i], next => { slots[i] = typeof next === 'function' ? next(slots[i]) : next }]
    },
    useRef(value) {
      const i = cursor++
      if (!(i in slots)) slots[i] = { current: value }
      return slots[i]
    },
  }
  const Dialog = loadTs('AddCustomProviderDialog.tsx', {
    react,
    antd: {
      Input: { Password: props => React.createElement('input', props) },
      Switch: () => null,
    },
    '../../i18n': { t: text => text },
    '../../ui': {
      Btn: ({ children, onClick }) => React.createElement('button', { onClick }, children),
      Dialog: ({ children, footer }) => React.createElement('dialog', null, children, footer),
      Row: ({ children }) => React.createElement('div', null, children),
    },
    '../../analytics/experience': { beginExperience: () => () => {} },
    './modelSettingsApi': {
      modelSettingsApi: {
        fetchList: () => new Promise((resolve, reject) => pending.push({ resolve, reject })),
        discover: () => { throw new Error('must not use discover') },
      },
    },
    './customProvider': custom,
  }).default
  const flatten = node => {
    if (Array.isArray(node)) return node.flatMap(flatten)
    if (!React.isValidElement(node)) return [node]
    return [node, ...React.Children.toArray(node.props?.children).flatMap(flatten),
      ...React.Children.toArray(node.props?.footer).flatMap(flatten)]
  }
  const render = () => { cursor = 0; return Dialog({ open: true, onClose() {}, onSubmit() {} }) }
  flatten(render()).find(node => node?.props?.['aria-label'] === '接口地址')
    .props.onChange({ target: { value: 'https://gw.example/v1' } })
  const fetchBtn = flatten(render()).find(node => String(node?.props?.children).includes('获取模型列表'))
  void fetchBtn.props.onClick()
  const input = flatten(render()).find(node => node?.props?.['aria-label'] === (edit === 'base_url' ? '接口地址' : 'API Key'))
  input.props.onChange({ target: { value: edit === 'base_url' ? 'https://other.example/v1' : 'new-test-key' } })
  if (outcome === 'reject') pending[0].reject(new Error('test transport failure'))
  else pending[0].resolve({ ok: outcome === 'success', models: ['stale-id'], source: 'live' })
  await new Promise(setImmediate)
  const afterStale = JSON.stringify(flatten(render()))
  assert.equal(afterStale.includes('stale-id'), false)
  assert.equal(slots[5], false, 'stale failures must not change the current error state')
  const retry = flatten(render()).find(node => String(node?.props?.children).includes('获取模型列表'))
  assert.equal(retry.props.disabled, false)
  void retry.props.onClick()
  pending[1].resolve({ ok: true, models: ['fresh-id'], source: 'live' })
  await new Promise(setImmediate)
  const tree = JSON.stringify(flatten(render()))
  assert.equal(tree.includes('fresh-id'), true)
  assert.equal(tree.includes('stale-id'), false)
})


test('ASR support is taken from backend adapter metadata, never user types', () => {
  const connection = { custom_models: [
    { ...custom.emptyOffer('gpt-4o-transcribe'), types: ['asr'] },
    { ...custom.emptyOffer('whisper-1'), types: ['asr'] },
  ] }
  const unknown = custom.mergeCustomList(connection)
  assert.ok(unknown.models.every(model => !model.asr_supported))
  const live = { source: 'live', preview: false, updated_at: 1, models: [
    { id: 'gpt-4o-transcribe', asr: true, asr_supported: false, asr_note: 'unsupported' },
    { id: 'whisper-1', asr: true, asr_supported: true },
  ] }
  const merged = custom.mergeCustomList(connection, live)
  assert.equal(merged.models[0].asr_supported, false)
  assert.equal(merged.models[0].asr_note, 'unsupported')
  assert.equal(merged.models[1].asr_supported, true)
})

test('custom model editor has no ineffective scenario checkboxes', () => {
  const source = fs.readFileSync(path.join(__dirname, '../src/features/settings/AddCustomProviderDialog.tsx'), 'utf8')
  assert.equal(source.includes("label={t('适用场景')}"), false)
})

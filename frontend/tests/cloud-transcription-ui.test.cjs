const { test } = require('node:test')
const assert = require('node:assert/strict')
const React = require('react')
const { loadTs } = require('./load-ts.cjs')

function textOf(node) {
  if (node == null || typeof node === 'boolean') return ''
  if (Array.isArray(node)) return node.map(textOf).join('')
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (!React.isValidElement(node)) return ''
  const type = node.type
  const inner = typeof type === 'function' ? type(node.props) : node.props?.children
  return textOf(inner)
}

function renderCloud(saveResult) {
  const saves = []
  const updates = []
  let cursor = 0
  const slots = []
  const effects = []
  const settings = {
    saved: true, migration_warnings: [],
    connections: [{
      id: 'ds', name: '百炼', provider: 'dashscope',
      base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
      api_key: 'sk-test', has_key: true, validation_status: 'unchecked',
      image_api: 'auto', image_base_url: '',
    }],
    analysis: { connection_id: 'ds', model: 'qwen-plus', capability: 'text', model_source: 'user' },
    vision: null, cover: null, cover_enabled: false,
    transcription: { provider: 'whisper_local', model: 'base', model_source: 'user' },
    chunk_size: 5000, min_score_threshold: .7, max_clips_per_collection: 5,
  }
  const Page = loadTs('AIModelSettings.tsx', {
    __globals: {
      window: {
        setInterval() { return 1 },
        clearInterval() {},
        setTimeout() { return 1 },
        clearTimeout() {},
      },
      document: { getElementById() { return null } },
    },
    './AddCustomProviderDialog': { default: () => null },
    react: {
      ...React,
      useState(initial) {
        const i = cursor++
        if (!(i in slots)) slots[i] = typeof initial === 'function' ? initial() : initial
        return [slots[i], next => { slots[i] = typeof next === 'function' ? next(slots[i]) : next }]
      },
      useRef(initial) {
        const i = cursor++
        if (!(i in slots)) slots[i] = { current: initial }
        return slots[i]
      },
      useEffect(fn) { effects.push(fn) },
    },
    'react-i18next': { useTranslation: () => {} },
    antd: { Select: () => null, Switch: () => null, message: { success() {}, error() {} } },
    '../../i18n': { t: (key, values) => (values ? `${key}|${values.provider}|${values.model}` : key) },
    '../../ui': {
      Btn: ({ children }) => React.createElement('button', null, children),
      StatusDot: ({ label }) => React.createElement('span', null, label),
      Icon: { Back: () => null },
      Row: ({ children }) => React.createElement('div', null, children),
      Section: ({ children }) => React.createElement('section', null, children),
    },
    '../../utils/externalLinks': { openExternalLink: () => {} },
    '../../components/SpeechRecognitionConfig': { default: () => null },
    '../../services/api': { speechApi: { getRuntimeStatus: async () => ({}), getModels: async () => [] }, default: { get: async () => ({}) } },
    './useModelSettings': { useModelSettings: () => ({
      settings, lists: {}, busy: {}, listErrors: {}, keyHints: {}, saving: false, testing: false, error: '', dirty: false,
      update: patch => { updates.push(patch) },
      save: async patch => { saves.push(patch); return saveResult },
      discover: () => {},
      load: async () => {},
    }) },
    './ProviderFields': { default: () => null },
    './ModelPicker': { default: () => null },
    './EndpointProviderSetup': { default: () => null },
    './SenseVoiceConfig': { default: () => null },
    './ProviderCatalog': { default: () => null },
    './ProviderDetail': { default: () => null },
    './DefaultModels': { default: props => React.createElement('section', { id: 'ai-defaults-transcription' }, props.transcriptionNote) },
  }).default
  const render = () => { cursor = 0; effects.length = 0; return Page({ requestedSection: 'speech', requestedProvider: 'cloud' }) }
  return { render, effects, saves, updates }
}

async function flush(box) {
  const tree = box.render()
  const cleanups = box.effects.splice(0).map(fn => fn())
  await Promise.resolve()
  await Promise.resolve()
  for (const cleanup of cleanups) if (typeof cleanup === 'function') cleanup()
  return tree
}

test('cloud auto-select persists immediately and puts the notice on the speech slot', async () => {
  const box = renderCloud({ ok: true, validationFailed: false })
  await flush(box)
  const shown = box.render()
  assert.equal(box.saves.length, 1)
  assert.equal(box.saves[0].transcription.provider, 'cloud')
  assert.equal(box.saves[0].transcription.model, 'qwen-audio-3.1-asr-flash')
  assert.equal(box.updates[0].transcription.model, 'qwen-audio-3.1-asr-flash')
  const speech = textOf(shown)
  assert.match(speech, /已改用/)
  assert.match(speech, /阿里云百炼/)
  assert.match(speech, /qwen-audio-3.1-asr-flash/)
  assert.doesNotMatch(speech, /正在检查可用的云端转写/)
})

test('an invalid key keeps the saved error and does not claim the cloud switch', async () => {
  const box = renderCloud({ ok: true, validationFailed: true })
  await flush(box)
  const shown = box.render()
  assert.equal(box.saves.length, 1)
  assert.equal(box.saves[0].transcription.provider, 'cloud')
  assert.doesNotMatch(textOf(shown), /已改用/)
})

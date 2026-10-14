const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('path')
const React = require('react')
const { loadTs } = require('./load-ts.cjs')

function flatten(node) {
  if (node == null || typeof node === 'boolean') return []
  if (Array.isArray(node)) return node.flatMap(flatten)
  if (!React.isValidElement(node)) return [node]
  const type = node.type
  if (typeof type === 'function') return [node, ...flatten(type(node.props))]
  return [node, ...flatten(node.props?.children)]
}

function textOf(node) {
  return flatten(node).filter(item => typeof item === 'string' || typeof item === 'number').join('')
}

const ui = {
  Btn: ({ children, ...props }) => React.createElement('button', props, children),
  StatusDot: ({ label }) => React.createElement('span', { 'data-status': true }, label),
  Icon: { Back: () => null, External: () => null },
  Row: ({ label, children }) => React.createElement('div', null, label, children),
}

const settings = {
  version: 1, saved: false, connections: [],
  analysis: null, vision: null, cover: null,
  transcription: { provider: 'whisper_local', model: 'base' },
  cover_enabled: false, allow_send_frame: true, analysis_mode: 'auto', allow_visual_screening: true,
  chunk_size: 5000, min_score_threshold: .7, max_clips_per_collection: 5,
}

const i18n = { t: (key, values) => (values && values.offer ? `${key}:${values.offer}` : key) }
const Catalog = loadTs('ProviderCatalog.tsx', {
  '../../i18n': i18n,
  '../../ui': ui,
}).default

test('catalog renders recommended / popular / local and keeps more collapsed', () => {
  const opened = []
  const tree = Catalog({
    settings, query: '', filter: 'all', moreOpen: false, selectedId: null,
    onQuery: () => {}, onFilter: () => {}, onToggleMore: () => {}, onOpen: id => opened.push(id),
  })
  const nodes = flatten(tree)
  const groups = nodes.filter(node => node.props && node.props['data-provider-group']).map(node => node.props['data-provider-group'])
  assert.deepEqual(groups, ['recommended', 'popular', 'local', 'more'])
  const cards = nodes.filter(node => node.props && node.props['data-provider-id'])
  assert.ok(cards.some(node => node.props['data-provider-id'] === 'api88'))
  assert.ok(cards.some(node => node.props['data-provider-id'] === 'deepseek'))
  assert.ok(cards.some(node => node.props['data-provider-id'] === 'whisper'))
  assert.equal(cards.some(node => node.props['data-provider-id'] === 'openrouter'), false)
  const whisper = cards.find(node => node.props['data-provider-id'] === 'whisper')
  assert.match(textOf(whisper), /settings\.providers\.available/)
  const deepseek = cards.find(node => node.props['data-provider-id'] === 'deepseek')
  assert.match(textOf(deepseek), /settings\.providers\.configure/)
  const api88 = cards.find(node => node.props['data-provider-id'] === 'api88')
  assert.match(textOf(api88), /settings\.providers\.one_click/)
  deepseek.props.onClick()
  assert.deepEqual(opened, ['deepseek'])
})

test('search and capability filter show unconnected more-group providers', () => {
  const tree = Catalog({
    settings, query: 'OpenRouter', filter: 'all', moreOpen: false, selectedId: null,
    onQuery: () => {}, onFilter: () => {}, onToggleMore: () => {}, onOpen: () => {},
  })
  const cards = flatten(tree).filter(node => node.props && node.props['data-provider-id'])
  assert.equal(cards.length, 1)
  assert.equal(cards[0].props['data-provider-id'], 'openrouter')
  assert.match(textOf(cards[0]), /settings\.providers\.configure/)
})

test('detail shows a configure form for an unconnected preset without writing a connection', () => {
  const Detail = loadTs('ProviderDetail.tsx', {
    '../../i18n': i18n,
    '../../ui': ui,
    '../../utils/externalLinks': { openExternalLink: () => {} },
    '../../components/SpeechRecognitionConfig': { default: () => null },
    './ProviderFields': {
      default: ({ connection, onEdit }) => React.createElement('div', {
        'data-fields': connection?.provider || '',
        onClick: () => onEdit({ api_key: 'sk-test' }),
      }),
    },
    './ModelPicker': { default: () => null },
    './SenseVoiceConfig': { default: () => null },
  }).default
  const ensured = []
  const tree = Detail({
    preset: {
      id: 'siliconflow',
      display_name: '硅基流动',
      ui_name: '',
      short_name: '硅基流动',
      group: 'popular',
      protocol: 'openai-completions',
      base_url: 'https://api.siliconflow.cn/v1',
      capabilities: ['language', 'asr', 'image'],
      docs_url: 'https://cloud.siliconflow.cn/account/ak',
      hint: '硅基流动。国内直连，OpenAI 兼容。',
      auth: 'api_key',
    },
    m: {
      settings,
      lists: {},
      busy: {},
      listErrors: {},
      ensureCatalogProvider: (id, patch, assign) => { ensured.push({ id, patch, assign }) },
      assignAnalysisConnection: () => {},
      editConnection: () => {},
    },
    onBack: () => {},
  })
  const nodes = flatten(tree)
  assert.equal(nodes.find(node => node.props && node.props['data-provider-id'])?.props['data-connect-kind'], 'compatible')
  assert.match(textOf(tree), /settings\.providers\.unconnected_guide/)
  const fields = nodes.find(node => node.props && node.props['data-fields'] === 'compatible')
  assert.ok(fields)
  fields.props.onClick()
  assert.equal(ensured.length, 1)
  assert.equal(ensured[0].id, 'siliconflow')
  assert.equal(ensured[0].patch.api_key, 'sk-test')
  assert.equal(settings.connections.length, 0)
})

test('catalog source does not send search text, keys, or full URLs to telemetry', () => {
  const files = [
    'providerCatalogView.ts', 'ProviderCatalog.tsx', 'ProviderDetail.tsx',
  ].map(name => fs.readFileSync(path.join(__dirname, '../src/features/settings', name), 'utf8'))
  for (const source of files) {
    assert.equal(/track(Experience|Event|Sponsor|ApiKey)\([^)]*query/.test(source), false)
    assert.equal(/track(Experience|Event|Sponsor|ApiKey)\([^)]*api_key/.test(source), false)
    assert.equal(/track(Experience|Event|Sponsor|ApiKey)\([^)]*base_url/.test(source), false)
    assert.equal(source.includes('https://') && /track[A-Z]\w+\([^;]*https:\/\//.test(source), false)
  }
})

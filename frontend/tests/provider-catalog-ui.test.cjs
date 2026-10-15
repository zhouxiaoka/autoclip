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
    settings, query: '', filter: 'all', moreOpen: false, selectedId: null, asrReady: { whisper: true },
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

test('saved custom gateways appear as a repair entry', () => {
  const tree = Catalog({
    settings: {
      ...settings,
      connections: [{
        id: 'gw', name: 'Home gateway', provider: 'compatible',
        base_url: 'https://gw.home.example/v1', api_key: '', image_api: 'auto', image_base_url: '',
      }],
    },
    query: '', filter: 'all', moreOpen: false, selectedId: null,
    onQuery: () => {}, onFilter: () => {}, onToggleMore: () => {}, onOpen: () => {},
  })
  const nodes = flatten(tree)
  assert.ok(nodes.some(node => node.props && node.props['data-provider-group'] === 'custom'))
  const card = nodes.find(node => node.props && node.props['data-provider-id'] === 'custom:gw')
  assert.ok(card)
  assert.match(textOf(card), /settings\.providers\.repair_custom/)
})

test('whisper is not marked available until the local model is ready', () => {
  const tree = Catalog({
    settings, query: '', filter: 'all', moreOpen: false, selectedId: null,
    onQuery: () => {}, onFilter: () => {}, onToggleMore: () => {}, onOpen: () => {},
  })
  const whisper = flatten(tree).find(node => node.props && node.props['data-provider-id'] === 'whisper')
  assert.match(textOf(whisper), /settings\.providers\.configure/)
})

test('catalog distinguishes configured credentials from verified connections', () => {
  for (const validation_status of [undefined, 'unchecked', 'failed', 'ok']) {
    const tree = Catalog({
      settings: {
        ...settings,
        connections: [{ id: 'ds', name: 'DeepSeek', provider: 'deepseek', base_url: '', has_key: true, validation_status, image_api: 'auto', image_base_url: '' }],
      },
      query: '', filter: 'all', moreOpen: false,
      onQuery: () => {}, onFilter: () => {}, onToggleMore: () => {}, onOpen: () => {},
    })
    const card = flatten(tree).find(node => node.props?.['data-provider-id'] === 'deepseek')
    assert.equal(card.props.className.includes('is-connected'), validation_status === 'ok')
    assert.match(textOf(card), validation_status === 'ok' ? /settings\.providers\.connected/ : /已配置/)
    assert.equal(flatten(card).some(node => node.props?.['data-status']), validation_status === 'ok')
  }
})

test('catalog shows both ready local ASR engines while cloud transcription is selected', () => {
  const tree = Catalog({
    settings: { ...settings, transcription: { provider: 'cloud', model: 'test-asr', connection_id: 'asr' } },
    query: '', filter: 'asr', moreOpen: false, asrReady: { whisper: true, sensevoice: true },
    onQuery: () => {}, onFilter: () => {}, onToggleMore: () => {}, onOpen: () => {},
  })
  for (const id of ['whisper', 'sensevoice']) {
    const card = flatten(tree).find(node => node.props?.['data-provider-id'] === id)
    assert.match(textOf(card), /settings\.providers\.available/)
    assert.ok(card.props.className.includes('is-connected'))
  }
})

test('detail only shows a successful status for verified connections or ready local ASR', () => {
  const Detail = loadTs('ProviderDetail.tsx', {
    '../../i18n': i18n, '../../ui': ui,
    '../../utils/externalLinks': { openExternalLink: () => {} },
    '../../components/SpeechRecognitionConfig': { default: () => null },
    './ProviderFields': { default: () => null },
    './ModelPicker': { default: () => null },
    './EndpointProviderSetup': { default: () => null },
    './SenseVoiceConfig': { default: () => null },
  }).default
  const view = loadTs('providerCatalogView.ts', { '../../i18n': i18n })
  for (const id of ['deepseek', 'ollama']) {
    for (const validation_status of ['unchecked', 'failed', 'ok']) {
      const tree = Detail({
        preset: view.catalogPreset(id),
        m: {
          settings: { ...settings, connections: [{ ...view.catalogDraftConnection(view.catalogPreset(id)), has_key: true, validation_status }] },
          lists: {}, busy: {}, listErrors: {}, keyHints: {},
        },
        onBack: () => {},
      })
      const statuses = flatten(tree).filter(node => node.props?.['data-status'])
      assert.equal(statuses.length, validation_status === 'ok' ? 1 : 0)
      assert.match(textOf(tree), validation_status === 'ok' ? /settings\.providers\.connected|settings\.providers\.available/ : /已配置/)
    }
  }
  for (const id of ['whisper', 'sensevoice']) {
    const tree = Detail({
      preset: view.catalogPreset(id), m: { settings, lists: {}, busy: {}, listErrors: {} },
      asrReady: { [id]: true }, onBack: () => {},
    })
    assert.match(textOf(tree), /settings\.providers\.available/)
  }
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
    './EndpointProviderSetup': { default: () => null },
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

for (const requestedProvider of ['', 'deepseek', 'custom:ds']) {
  test(`manual model choice remains user-owned in ${requestedProvider || 'overview'}`, () => {
    const updates = []
    const value = {
      ...settings,
      saved: true,
      connections: [{ id: 'ds', name: 'Gateway', provider: requestedProvider.startsWith('custom:') ? 'compatible' : 'deepseek', base_url: 'https://gateway.example/v1', has_key: true }],
      analysis: { connection_id: 'ds', model: 'deepseek-flash', capability: 'auto', model_source: 'preset' },
    }
    const m = {
      settings: value, lists: {}, busy: {}, listErrors: {}, keyHints: {},
      main: value.connections[0], update: patch => updates.push(patch),
    }
    const Page = loadTs('AIModelSettings.tsx', {
      './AddCustomProviderDialog': { default: () => null },
      react: { ...React, useState: initial => [typeof initial === 'function' ? (requestedProvider.startsWith('custom:') ? requestedProvider : initial()) : initial, () => {}], useEffect: () => {} },
      'react-i18next': { useTranslation: () => {} },
      antd: { Select: () => null, Switch: () => null },
      '../../i18n': i18n,
      '../../ui': { ...ui, Section: () => null, Segmented: () => null },
      '../../utils/externalLinks': { openExternalLink: () => {} },
      '../../components/SpeechRecognitionConfig': { default: () => null },
      '../../services/api': {},
      './useModelSettings': { useModelSettings: () => m },
      './ProviderFields': { default: () => null },
      './ModelPicker': { default: () => null },
      './EndpointProviderSetup': { default: () => null },
    './SenseVoiceConfig': { default: () => null },
      './ProviderCatalog': { default: () => null },
      './DefaultModels': { default: () => React.createElement('div', { 'data-default-models': true }) },
    }).default
    const nodes = flatten(Page({ requestedSection: 'model', requestedProvider }))
    assert.equal(nodes.some(node => node.props?.['data-default-models']), !requestedProvider)
    if (requestedProvider.startsWith('custom:')) {
      assert.ok(nodes.some(node => node.props?.['data-connect-kind'] === 'compatible'))
    }
    const picker = nodes.find(node => node.props?.role === 'analysis')
    assert.ok(picker)
    picker.props.onChange('manually-selected-model')
    const { forSave } = loadTs('modelSettingsLogic.ts', { '../../i18n': i18n })
    const saved = forSave({ ...value, ...updates[0] })
    assert.equal(saved.analysis.model, 'manually-selected-model')
    assert.equal(saved.analysis.model_source, 'user', 'manual models must never opt into preset fallback')
  })
}

test('all endpoint-only catalog cards open an address entry flow without binding a default', () => {
  const view = loadTs('providerCatalogView.ts', { '../../i18n': i18n })
  const Detail = loadTs('ProviderDetail.tsx', {
    '../../i18n': i18n, '../../ui': ui,
    '../../utils/externalLinks': { openExternalLink: () => {} },
    '../../components/SpeechRecognitionConfig': { default: () => null },
    './ProviderFields': { default: () => null }, './ModelPicker': { default: () => null },
    './SenseVoiceConfig': { default: () => null },
    './EndpointProviderSetup': { default: ({ connection, onEdit }) => React.createElement('input', {
      'data-endpoint-setup': connection.catalog_provider_id, value: connection.base_url,
      onChange: event => onEdit({ base_url: event.target.value }),
    }) },
  }).default
  for (const preset of view.catalogProviders().filter(row => !row.base_url && row.protocol !== 'local')) {
    const opened = []
    const tree = Catalog({ settings, query: preset.id, filter: 'all', moreOpen: true,
      onQuery: () => {}, onFilter: () => {}, onToggleMore: () => {}, onOpen: id => opened.push(id) })
    flatten(tree).find(node => node.props?.['data-provider-id'] === preset.id).props.onClick()
    assert.deepEqual(opened, [preset.id])
    const edits = []
    const detail = Detail({ preset, m: { settings, lists: {}, busy: {}, listErrors: {},
      ensureCatalogProvider: (id, patch) => edits.push({ id, patch }) }, onBack: () => {} })
    const input = flatten(detail).find(node => node.props?.['data-endpoint-setup'] === preset.id)
    assert.ok(input)
    input.props.onChange({ target: { value: 'https://endpoint.example.test/v1' } })
    assert.deepEqual(edits, [{ id: preset.id, patch: { base_url: 'https://endpoint.example.test/v1' } }])
    assert.equal(settings.analysis, null)
  }
})

test('endpoint setup requires an address and model before sending validation', () => {
  const calls = []
  const Setup = loadTs('EndpointProviderSetup.tsx', {
    react: { ...React, useState: () => ['test-model', () => {}] },
    antd: { Input: props => React.createElement('input', props) },
    '../../i18n': i18n, '../../ui': ui,
    './ProviderFields': { default: () => null },
  }).default
  for (const base_url of ['', 'https://endpoint.example.test/v1']) {
    const connection = { id: 'endpoint', provider: 'compatible', base_url }
    const tree = Setup({ connection, onEdit: () => {}, m: { testing: false,
      validateCatalogConnection: (...args) => calls.push(args) } })
    const button = flatten(tree).find(node => node.type === 'button')
    assert.equal(button.props.disabled, !base_url)
    if (base_url) button.props.onClick()
  }
  assert.equal(calls.length, 1)
  assert.equal(calls[0][1], 'test-model')
})

test('R6 transient validation shows an existing hint without marking credentials invalid', () => {
  const access = loadTs('providerAccess.ts', { '../../i18n': i18n })
  const Fields = loadTs('ProviderFields.tsx', {
    react: { ...React, useState: () => [false, () => {}] },
    antd: { Input: Object.assign(() => null, { Password: 'password' }), Select: 'select' },
    '../../i18n': i18n, '../../ui': ui,
    '../../utils/externalLinks': { openExternalLink() {} },
    '../../analytics/events': { trackSponsorLinkOpened() {} },
    './providerAccess': access,
  }).default
  const endpoint = loadTs('endpointProvider.ts')
  for (const validation_status of ['transient', 'failed']) {
    const connection = { id:'endpoint', name:'Endpoint', provider:'compatible', catalog_provider_id:'azure-openai',
      base_url:'https://endpoint.example.test/v1', validation_status,
      validation_error_type: validation_status === 'transient' ? 'timeout' : 'invalid_key' }
    const tree = Fields({connection, placement:'settings_model', onChoose() {}, onEdit() {}})
    assert.ok(textOf(tree).includes(access.validationCopy(connection.validation_error_type)))
    const nodes = flatten(tree)
    assert.equal(nodes.some(node => node.props?.className?.includes('ac-note--error')), validation_status === 'failed')
    assert.equal(nodes.some(node => node.props?.status === 'error'), validation_status === 'failed')
    assert.equal(endpoint.endpointProviderReady(connection), validation_status === 'transient')
  }
})

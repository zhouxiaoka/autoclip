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
  const recommended = nodes.find(node => node.props && node.props['data-provider-group'] === 'recommended')
  const recommendedIds = flatten(recommended).filter(node => node.props && node.props['data-provider-id']).map(node => node.props['data-provider-id'])
  assert.deepEqual(recommendedIds, ['apimart', 'api88', 'infistar'])
  assert.ok(cards.some(node => node.props['data-provider-id'] === 'api88'))
  assert.ok(cards.some(node => node.props['data-provider-id'] === 'deepseek'))
  assert.ok(cards.some(node => node.props['data-provider-id'] === 'whisper'))
  assert.equal(cards.some(node => node.props['data-provider-id'] === 'openrouter'), false)
  const moreBtn = nodes.find(node => node.props && node.props.className === 'ac-provider-more')
  assert.ok(moreBtn)
  assert.equal(moreBtn.props['aria-expanded'], false)
  assert.match(textOf(moreBtn), /settings\.providers\.group\.more|更多服务商/)

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
  assert.match(textOf(tree), /测试连接|可用模型/)
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

test('overview uses DefaultModels and drops legacy CurrentAnalysis / transcription / cover blocks', () => {
  const value = {
    ...settings,
    saved: true,
    connections: [{ id: 'ds', name: 'DeepSeek', provider: 'deepseek', base_url: '', has_key: true, validation_status: 'ok' }],
    analysis: { connection_id: 'ds', model: 'deepseek-chat', capability: 'auto', model_source: 'user' },
  }
  const m = { settings: value, lists: {}, busy: {}, listErrors: {}, keyHints: {}, update: () => {}, save: async () => ({}), load: async () => {} }
  const Page = loadTs('AIModelSettings.tsx', {
    './AddCustomProviderDialog': { default: () => null },
    react: { ...React, useState: initial => [typeof initial === 'function' ? initial() : initial, () => {}], useEffect: () => {}, useRef: initial => ({ current: initial }) },
    'react-i18next': { useTranslation: () => {} },
    antd: { Select: () => null, Switch: () => null },
    '../../i18n': i18n,
    '../../ui': { ...ui, Section: () => null, Segmented: () => null },
    '../../utils/externalLinks': { openExternalLink: () => {} },
    '../../components/SpeechRecognitionConfig': { default: () => null },
    '../../services/api': { speechApi: { getRuntimeStatus: async () => ({}), getModels: async () => ([]) }, default: { get: async () => ({}) } },
    './useModelSettings': { useModelSettings: () => m },
    './ProviderFields': { default: () => null },
    './ModelPicker': { default: () => null },
    './EndpointProviderSetup': { default: () => null },
    './SenseVoiceConfig': { default: () => null },
    './ProviderCatalog': { default: props => React.createElement('div', { 'data-catalog': true, 'data-has-add': !!props.onAdd }) },
    './DefaultModels': { default: () => React.createElement('div', { 'data-default-models': true }) },
  }).default
  const nodes = flatten(Page({ requestedSection: 'model', requestedProvider: '' }))
  assert.ok(nodes.some(node => String(node.props?.['data-layout'] || '').startsWith('v6')))
  assert.ok(nodes.some(node => node.props?.['data-default-models']))
  assert.ok(nodes.some(node => node.props?.['data-catalog'] && node.props?.['data-has-add']))
  assert.equal(nodes.some(node => node.props?.role === 'analysis'), false)
})

test('manual model choice via DefaultModels slots stays user-owned', () => {
  const slots = loadTs('defaultModelSlots.ts', {
    '../../i18n': i18n,
    './modelSettingsLogic': loadTs('modelSettingsLogic.ts', { '../../i18n': i18n }),
    './providerCatalogView': loadTs('providerCatalogView.ts', { '../../i18n': i18n }),
    './modelDefaults': loadTs('modelDefaults.ts', { '../../i18n': i18n }),
    './providerPresets': loadTs('providerPresets.ts', { '../../i18n': i18n }),
  })
  const value = {
    ...settings,
    saved: true,
    connections: [{ id: 'ds', name: 'DeepSeek', provider: 'deepseek', base_url: '', has_key: true, validation_status: 'ok', api_key: '', image_api: 'auto', image_base_url: '' }],
    analysis: { connection_id: 'ds', model: 'deepseek-flash', capability: 'auto', model_source: 'preset' },
  }
  const next = slots.applyFixedSelection(value, 'analysis', 'manually-selected-model', 'ds')
  const { forSave } = loadTs('modelSettingsLogic.ts', { '../../i18n': i18n })
  const saved = forSave(next)
  assert.equal(saved.analysis.model, 'manually-selected-model')
  assert.equal(saved.analysis.model_source, 'user', 'manual models must never opt into preset fallback')
})

for (const requestedProvider of ['deepseek', 'custom:ds']) {
  test(`provider detail opens for ${requestedProvider}`, () => {
    const value = {
      ...settings,
      saved: true,
      connections: [{
        id: 'ds', name: 'Gateway',
        provider: requestedProvider.startsWith('custom:') ? 'compatible' : 'deepseek',
        base_url: 'https://gateway.example/v1', has_key: true,
      }],
      analysis: { connection_id: 'ds', model: 'deepseek-flash', capability: 'auto', model_source: 'preset' },
    }
    const m = {
      settings: value, lists: {}, busy: {}, listErrors: {}, keyHints: {},
      update: () => {}, save: async () => ({}),
    }
    const Page = loadTs('AIModelSettings.tsx', {
      './AddCustomProviderDialog': { default: () => null },
      react: {
        ...React,
        useState: initial => [typeof initial === 'function'
          ? (requestedProvider.startsWith('custom:') ? requestedProvider : (catalogId => catalogId)(requestedProvider === 'deepseek' ? 'deepseek' : initial()))
          : (requestedProvider === 'deepseek' ? 'deepseek' : initial), () => {}],
        useEffect: () => {},
        useRef: initial => ({ current: initial }),
      },
      'react-i18next': { useTranslation: () => {} },
      antd: { Select: () => null, Switch: () => null },
      '../../i18n': i18n,
      '../../ui': { ...ui, Section: () => null, Segmented: () => null },
      '../../utils/externalLinks': { openExternalLink: () => {} },
      '../../components/SpeechRecognitionConfig': { default: () => null },
      '../../services/api': { speechApi: { getRuntimeStatus: async () => ({}), getModels: async () => ([]) }, default: { get: async () => ({}) } },
      './useModelSettings': { useModelSettings: () => m },
      './ProviderFields': { default: () => null },
      './ModelPicker': { default: () => null },
      './EndpointProviderSetup': { default: () => null },
      './SenseVoiceConfig': { default: () => null },
      './ProviderCatalog': { default: () => null },
      './DefaultModels': { default: () => React.createElement('div', { 'data-default-models': true }) },
      './ProviderDetail': { default: ({ preset }) => React.createElement('div', { 'data-detail': preset?.id, 'data-layout': 'v6' }) },
    }).default
    // Force selectedId via requestedProvider prop effect is mocked; seed useState with provider id.
    const nodes = flatten(Page({ requestedSection: 'model', requestedProvider }))
    if (requestedProvider.startsWith('custom:')) {
      assert.ok(nodes.some(node => node.props?.['data-connect-kind'] === 'compatible'))
    } else {
      assert.ok(nodes.some(node => node.props?.['data-detail'] === 'deepseek' || node.props?.['data-provider-id'] === 'deepseek'))
    }
  })
}

test('provider detail uses two-column connect/models layout without analysis ModelPicker', () => {
  const Detail = loadTs('ProviderDetail.tsx', {
    '../../i18n': i18n, '../../ui': ui,
    '../../utils/externalLinks': { openExternalLink: () => {} },
    '../../components/SpeechRecognitionConfig': { default: () => null },
    './ProviderFields': { default: () => React.createElement('div', { 'data-fields': true }) },
    './EndpointProviderSetup': { default: () => null },
    './SenseVoiceConfig': { default: () => null },
  }).default
  const view = loadTs('providerCatalogView.ts', { '../../i18n': i18n })
  const tree = Detail({
    preset: view.catalogPreset('deepseek'),
    m: {
      settings: {
        ...settings,
        connections: [{ id: 'ds', name: 'DeepSeek', provider: 'deepseek', has_key: true, validation_status: 'ok', base_url: '', image_api: 'auto', image_base_url: '' }],
        analysis: { connection_id: 'ds', model: 'deepseek-chat', model_source: 'user' },
      },
      lists: {
        ds: {
          source: 'live', preview: false,
          models: [
            { id: 'deepseek-chat', analysis: true, capability: 'text' },
            { id: 'deepseek-vl', analysis: true, capability: 'multimodal' },
          ],
        },
      },
      busy: {}, listErrors: {}, keyHints: {},
      ensureCatalogProvider: () => {}, editConnection: () => {},
    },
    onBack: () => {},
  })
  const root = flatten(tree).find(node => String(node.props?.['data-layout'] || '').startsWith('v6'))
  assert.ok(root)
  assert.ok(flatten(tree).some(node => node.props?.['data-panel'] === 'connect'))
  assert.ok(flatten(tree).some(node => node.props?.['data-panel'] === 'models'))
  assert.equal(flatten(tree).some(node => node.props?.role === 'analysis'), false)
  assert.match(textOf(tree), /可用模型|测通后/)
})

test('locked catalog detail shows editable 接口地址 and 测试连接', () => {
  const view = loadTs('providerCatalogView.ts', { '../../i18n': i18n })
  const openai = view.catalogProviders().find(row => row.id === 'openai')
  assert.ok(openai && openai.locked && openai.base_url)
  const edits = []
  const tests = []
  const Detail = loadTs('ProviderDetail.tsx', {
    '../../i18n': i18n, '../../ui': ui,
    '../../utils/externalLinks': { openExternalLink: () => {} },
    '../../components/SpeechRecognitionConfig': { default: () => null },
    './ProviderFields': { default: ({ connection, onEdit }) => React.createElement('div', { 'data-fields': true },
      React.createElement('input', { 'aria-label': '接口地址', value: connection.base_url, onChange: e => onEdit({ base_url: e.target.value }) }),
      React.createElement('input', { 'aria-label': 'API Key', value: connection.api_key || '', onChange: e => onEdit({ api_key: e.target.value }) }),
    ) },
    './ModelPicker': { default: () => null },
    './SenseVoiceConfig': { default: () => null },
  }).default
  const detail = Detail({
    preset: openai,
    m: {
      settings, lists: {}, busy: {}, listErrors: {}, testing: false, keyHints: {},
      ensureCatalogProvider: (id, patch) => edits.push({ id, patch }),
      editConnection: (c, patch) => edits.push({ id: c.id, patch }),
      testCatalogProvider: (id, draft) => tests.push({ id, draft }),
    },
    onBack: () => {},
  })
  const nodes = flatten(detail)
  const address = nodes.find(node => node.props?.['aria-label'] === '接口地址')
  assert.ok(address)
  assert.equal(address.props.value, openai.base_url)
  const testBtn = nodes.find(node => node.type === 'button' && textOf(node).includes('测试连接'))
  assert.ok(testBtn)
  testBtn.props.onClick()
  assert.equal(tests.length, 1)
  assert.equal(tests[0].id, 'openai')
  assert.equal(tests[0].draft.base_url, openai.base_url)
})


test('all endpoint-only catalog cards open an address entry flow without binding a default', () => {
  const view = loadTs('providerCatalogView.ts', { '../../i18n': i18n })
  const Detail = loadTs('ProviderDetail.tsx', {
    '../../i18n': i18n, '../../ui': ui,
    '../../utils/externalLinks': { openExternalLink: () => {} },
    '../../components/SpeechRecognitionConfig': { default: () => null },
    './ProviderFields': { default: ({ connection, onEdit }) => React.createElement('input', {
      'data-endpoint-setup': connection.catalog_provider_id || connection.provider,
      'aria-label': '接口地址',
      value: connection.base_url,
      onChange: event => onEdit({ base_url: event.target.value }),
    }) },
    './ModelPicker': { default: () => null },
    './SenseVoiceConfig': { default: () => null },
  }).default
  for (const preset of view.catalogProviders().filter(row => !row.base_url && row.protocol !== 'local')) {
    const opened = []
    const tree = Catalog({ settings, query: preset.id, filter: 'all', moreOpen: true,
      onQuery: () => {}, onFilter: () => {}, onToggleMore: () => {}, onOpen: id => opened.push(id) })
    flatten(tree).find(node => node.props?.['data-provider-id'] === preset.id).props.onClick()
    assert.deepEqual(opened, [preset.id])
    const edits = []
    const tests = []
    const detail = Detail({ preset, m: { settings, lists: {}, busy: {}, listErrors: {}, testing: false,
      ensureCatalogProvider: (id, patch) => edits.push({ id, patch }),
      testCatalogProvider: (id, draft) => tests.push({ id, draft }),
      editConnection: () => {} }, onBack: () => {} })
    const nodes = flatten(detail)
    const input = nodes.find(node => node.props?.['data-endpoint-setup'] === preset.id)
    assert.ok(input, preset.id)
    assert.match(textOf(detail), /请先填写接口地址/)
    input.props.onChange({ target: { value: 'https://endpoint.example.test/v1' } })
    assert.deepEqual(edits, [{ id: preset.id, patch: { base_url: 'https://endpoint.example.test/v1' } }])
    const testBtn = nodes.find(node => node.type === 'button' && textOf(node).includes('测试连接'))
    assert.ok(testBtn, '测试连接 for ' + preset.id)
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


test('sponsor detail keeps only essentials: key, address, one-click, test, models', () => {
  const view = loadTs('providerCatalogView.ts', { '../../i18n': i18n })
  const Detail = loadTs('ProviderDetail.tsx', {
    '../../i18n': i18n, '../../ui': ui,
    '../../utils/externalLinks': { openExternalLink: () => {} },
    '../../components/SpeechRecognitionConfig': { default: () => null },
    './ProviderFields': { default: ({ connection }) => React.createElement('div', { 'data-fields': true },
      React.createElement('button', { type: 'button' }, 'settings.providers.one_click'),
      React.createElement('input', { 'aria-label': 'API 密钥', value: connection.api_key || '' }),
      React.createElement('input', { 'aria-label': '接口地址', value: connection.base_url }),
    ) },
    './ModelPicker': { default: () => null },
    './SenseVoiceConfig': { default: () => null },
  }).default
  for (const id of ['api88', 'infistar', 'apimart']) {
    const preset = view.catalogPreset(id)
    assert.ok(preset?.sponsor)
    const tree = Detail({
      preset,
      m: { settings, lists: {}, busy: {}, listErrors: {}, testing: false, keyHints: {},
        ensureCatalogProvider: () => {}, editConnection: () => {}, testCatalogProvider: () => {} },
      onBack: () => {},
    })
    const text = textOf(tree)
    assert.equal(/推广分成|项目维护|领取条件|注册并领取|接入说明|仅保存在本机|unconnected_guide|one_click_hint/.test(text), false)
    assert.match(text, /测试连接/)
    assert.match(text, /可用模型/)
    assert.ok(flatten(tree).some(n => n.props?.['aria-label'] === '接口地址'))
    assert.ok(flatten(tree).some(n => n.props?.['aria-label'] === 'API 密钥'))
    assert.ok(flatten(tree).some(n => n.type === 'button' && /one_click|一键获取/.test(textOf(n))))
  }
})

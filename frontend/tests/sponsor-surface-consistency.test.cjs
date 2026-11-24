const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const React = require('react')
const { act } = React
const { createRoot } = require('react-dom/client')
const { loadTs } = require('./load-ts.cjs')

const i18n = { t: (key, values) => (values && values.offer ? `${key}:${values.offer}` : key) }
const ui = {
  Btn: ({ children, onClick, disabled }) => React.createElement('button', { type: 'button', onClick, disabled }, children),
  StatusDot: ({ label }) => React.createElement('span', { 'data-status': true }, label),
  Icon: { Back: () => null, External: () => null, Check: () => null },
  Row: ({ label, children }) => React.createElement('div', null, label, children),
}

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

function promoView(patch) {
  return {
    choices: ['apimart', 'api88', 'other'],
    defaultChoice: 'apimart',
    statuses: {},
    registerUrls: {
      apimart: 'https://go.apimart.ai/tw-autoclip',
      api88: 'https://88api.ai/sign-up?aff=2PIc',
    },
    notices: {},
    ...patch,
  }
}

function button(root, label) {
  return [...root.querySelectorAll('button')].find(node => node.textContent === label)
}

test('setup choice uses a remote default that is not first, and falls back when it cannot', () => {
  const state = loadTs('sponsorPromoState.ts')
  const providers = loadTs('providers.ts', { '../../i18n': i18n, './sponsorPromoState': state })
  const listed = providers.recommendedSetupProviders()
  assert.deepEqual([...listed].slice(0, 3), ['deepseek', 'dashscope', 'apimart'])
  assert.equal(listed.includes('api88'), false)
  assert.equal(state.promotionSetupChoice(['deepseek', 'apimart']), 'deepseek')

  state.writePromoSnapshot(promoView({ defaultChoice: 'apimart' }))
  assert.equal(state.promotionSetupChoice(providers.recommendedSetupProviders()), 'apimart')

  state.writePromoSnapshot(promoView({
    choices: ['api88', 'other'],
    defaultChoice: 'apimart',
    statuses: { apimart: 'out_of_service', api88: 'healthy' },
  }))
  const stopped = providers.recommendedSetupProviders()
  assert.equal(stopped.includes('apimart'), false)
  assert.equal(stopped.includes('api88'), true)
  assert.deepEqual([...stopped].slice(0, 3), ['deepseek', 'dashscope', 'api88'])
  assert.equal(state.promotionSetupChoice(stopped), 'deepseek')

  state.writePromoSnapshot(promoView({ defaultChoice: 'other', choices: ['api88', 'other'] }))
  assert.equal(state.promotionSetupChoice(providers.recommendedSetupProviders()), providers.recommendedSetupProviders()[0])
  state.writePromoSnapshot(promoView({ defaultChoice: 'missing', choices: ['api88', 'other'] }))
  assert.equal(state.promotionSetupChoice(providers.recommendedSetupProviders()), providers.recommendedSetupProviders()[0])
  state.writePromoSnapshot(promoView({
    choices: ['other'],
    defaultChoice: 'api88',
    statuses: { api88: 'out_of_service', apimart: 'out_of_service' },
  }))
  assert.equal(state.promotionSetupChoice(['api88', 'apimart']), null)
  state.writePromoSnapshot(null)
  assert.equal(state.promotionSetupChoice([]), null)
})

test('catalog, detail and import card drop promotion together and keep the provider usable', () => {
  const state = loadTs('sponsorPromoState.ts')
  const view = loadTs('providerCatalogView.ts', { '../../i18n': i18n })
  const Catalog = loadTs('ProviderCatalog.tsx', {
    '../../i18n': i18n,
    '../../ui': ui,
    './sponsorPromoState': state,
  }).default
  const Detail = loadTs('ProviderDetail.tsx', {
    react: { ...React, useRef: current => ({ current }) },
    '../../i18n': i18n,
    '../../ui': ui,
    '../../utils/externalLinks': { openExternalLink() {} },
    '../../components/SpeechRecognitionConfig': { default: () => null },
    './ProviderFields': { default: () => React.createElement('div', { 'data-fields': '1' }) },
    './SenseVoiceConfig': { default: () => null },
    './TrialRunPanel': { default: () => null },
    './sponsorPromoState': state,
  }).default
  const settings = {
    version: 1, saved: true, connections: [],
    analysis: null, vision: null, cover: null,
    transcription: { provider: 'whisper_local', model: 'base' },
    cover_enabled: false, allow_send_frame: false, analysis_mode: 'auto', allow_visual_screening: true,
    chunk_size: 5000, min_score_threshold: .7, max_clips_per_collection: 5,
  }
  const store = { settings, lists: {}, busy: {}, listErrors: {}, lastTrialByConnection: {}, keyHints: {} }
  const cardOf = (tree, id) => flatten(tree).find(node => node.props?.['data-provider-id'] === id)
  const promoBadge = node => textOf(node).includes('推荐') || textOf(node).includes('settings.providers.badge.sponsor')

  state.writePromoSnapshot(promoView({ defaultChoice: 'apimart', statuses: { apimart: 'healthy', api88: 'healthy' } }))
  let catalog = Catalog({
    settings, query: '', filter: 'all', moreOpen: true, selectedId: null,
    onQuery() {}, onFilter() {}, onToggleMore() {}, onOpen() {},
  })
  assert.equal(promoBadge(cardOf(catalog, 'apimart')), true)
  assert.equal(promoBadge(cardOf(catalog, 'api88')), false)
  assert.equal(promoBadge(cardOf(catalog, 'infistar')), false)
  let detail = Detail({ preset: view.catalogPreset('apimart'), m: store, onBack() {} })
  assert.equal(flatten(detail).some(node => node.props?.['data-promo'] === 'sponsor'), true)
  assert.equal(flatten(detail).some(node => node.props?.['data-fields'] === '1'), true)

  state.writePromoSnapshot(promoView({
    choices: ['api88', 'other'],
    defaultChoice: 'api88',
    statuses: { apimart: 'out_of_service', api88: 'healthy' },
  }))
  catalog = Catalog({
    settings, query: '', filter: 'all', moreOpen: true, selectedId: null,
    onQuery() {}, onFilter() {}, onToggleMore() {}, onOpen() {},
  })
  assert.equal(promoBadge(cardOf(catalog, 'apimart')), false)
  assert.equal(promoBadge(cardOf(catalog, 'api88')), true)
  detail = Detail({ preset: view.catalogPreset('apimart'), m: store, onBack() {} })
  assert.equal(flatten(detail).some(node => node.props?.['data-promo'] === 'sponsor'), false)
  assert.equal(flatten(detail).some(node => node.props?.['data-sponsor'] === '1'), false)
  assert.equal(flatten(detail).some(node => node.props?.['data-fields'] === '1'), true)
  assert.equal(textOf(detail).includes('赞助合作伙伴'), false)
  const neutral = Detail({ preset: view.catalogPreset('infistar'), m: store, onBack() {} })
  assert.equal(flatten(neutral).some(node => node.props?.['data-promo'] === 'sponsor'), false)
  assert.equal(flatten(neutral).some(node => node.props?.['data-fields'] === '1'), true)
  const saved = { id: 'saved', provider: 'api88', base_url: 'https://api.88api.ai/v1', api_key: 'fixture-api88-key', has_key: true, name: '88API' }
  const kept = Detail({
    preset: view.catalogPreset('api88'),
    m: { ...store, settings: { ...settings, connections: [saved] } },
    onBack() {},
  })
  assert.equal(flatten(kept).some(node => node.props?.['data-promo'] === 'sponsor'), true)
  assert.equal(textOf(kept).includes('go.apimart.ai'), false)
  assert.equal(textOf(kept).includes('赞助合作伙伴'), false)
  assert.equal(saved.provider, 'api88')
  assert.equal(saved.base_url, 'https://api.88api.ai/v1')
  assert.equal(saved.api_key, 'fixture-api88-key')
  assert.match(textOf(detail), /OpenAI 兼容网关/)
  state.writePromoSnapshot(promoView({
    choices: ['apimart', 'other'],
    defaultChoice: 'apimart',
    statuses: { apimart: 'healthy' },
    registerUrls: { apimart: 'https://go.apimart.ai/tw-autoclip' },
    source: 'cache',
  }))
  const restored = Detail({ preset: view.catalogPreset('apimart'), m: store, onBack() {} })
  assert.equal(flatten(restored).some(node => node.props?.['data-promo'] === 'sponsor'), true)
  assert.equal(saved.api_key, 'fixture-api88-key')
  assert.equal(saved.provider, 'api88')
  state.writePromoSnapshot(null)
})

test('import card preselects the remote default and a late default cannot move a frozen identity', async () => {
  const { Window } = require('happy-dom')
  const window = new Window({ url: 'http://localhost/' })
  const previous = {
    window: globalThis.window, document: globalThis.document, navigator: globalThis.navigator,
    HTMLElement: globalThis.HTMLElement, IS_REACT_ACT_ENVIRONMENT: globalThis.IS_REACT_ACT_ENVIRONMENT,
  }
  globalThis.window = window
  globalThis.document = window.document
  globalThis.navigator = window.navigator
  globalThis.HTMLElement = window.HTMLElement
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  const calls = []
  const connection = { provider: '', api_key: '' }
  const store = {
    settings: { saved: false, connections: [], analysis: null },
    saving: false,
    error: '',
    selectProvider(provider) {
      connection.provider = provider
      connection.api_key = ''
      calls.push(['select', provider])
    },
    setKey(value) {
      connection.api_key = value
      calls.push(['key', connection.provider, value])
    },
    connect: async () => {
      calls.push(['connect', connection.provider, connection.api_key])
      return { ok: true }
    },
  }
  const state = loadTs('sponsorPromoState.ts')
  const providers = loadTs('providers.ts', { '../../i18n': i18n, './sponsorPromoState': state })
  let promo = null
  const listeners = new Set()
  const watch = {
    useSponsorPromo() {
      const [value, setValue] = React.useState(promo)
      React.useEffect(() => {
        const listen = () => setValue(promo)
        listeners.add(listen)
        return () => listeners.delete(listen)
      }, [])
      return value
    },
  }
  const publish = (next) => {
    promo = next
    state.writePromoSnapshot(next)
    listeners.forEach(listen => listen())
  }
  try {
    const Card = loadTs(path.join(__dirname, '../src/features/studio/ImportSetupCard.tsx'), {
      __globals: { window, document: window.document, navigator: window.navigator, HTMLElement: window.HTMLElement },
      'react-i18next': { useTranslation() {} },
      'react-router-dom': { useNavigate: () => () => {} },
      '../../i18n': i18n,
      '../../ui': ui,
      '../../analytics/experience': { trackExperience() {} },
      '../../analytics/events': { trackSponsorLinkOpened: props => calls.push(['open', props.sponsor]) },
      '../../analytics/successRateContract': { telemetryProvider: value => value },
      '../../analytics/workflow': { telemetryId: () => 't-surface' },
      '../../utils/externalLinks': { openExternalLink: url => calls.push(['link', url]) },
      '../settings/useQuickConnect': { useQuickConnect: () => store },
      '../settings/providers': providers,
      '../settings/sponsorPromoState': state,
      '../settings/sponsorPromoWatch': watch,
      './studio.css': {},
    }, path.join(__dirname, '../src/features/studio')).default
    const host = document.createElement('div')
    document.body.appendChild(host)
    const root = createRoot(host)
    await act(async () => { root.render(React.createElement(Card)) })
    const checked = () => [...host.querySelectorAll('[role="radio"]')].find(node => node.getAttribute('aria-checked') === 'true')
    assert.equal(checked().textContent.includes('DeepSeek'), true)
    assert.equal([...host.querySelectorAll('[role="radio"]')].some(node => node.textContent.includes('88API')), false)
    await act(async () => { publish(promoView({ defaultChoice: 'apimart', statuses: { apimart: 'healthy', api88: 'healthy' } })) })
    assert.equal(checked().textContent.includes('APIMart'), true)
    await act(async () => { checked().click() })
    await act(async () => { publish(promoView({ defaultChoice: 'api88', statuses: { apimart: 'healthy', api88: 'healthy' } })) })
    assert.equal(checked().textContent.includes('APIMart'), true)
    await act(async () => { button(host, '下一步').click() })
    assert.deepEqual(calls.filter(item => item[0] === 'select'), [['select', 'apimart']])
    await act(async () => { button(host, '获取 API Key').click() })
    assert.deepEqual(calls.filter(item => item[0] === 'open'), [['open', 'apimart']])
    assert.equal(calls.some(item => item[0] === 'link' && String(item[1]).includes('88api.ai')), false)
    const key = host.querySelector('input[aria-label="API 密钥"]')
    const propsKey = Object.keys(key).find(name => name.startsWith('__reactProps'))
    await act(async () => { key[propsKey].onChange({ target: { value: 'fixture-kept-key' } }) })
    await act(async () => { publish(promoView({ defaultChoice: 'api88' })) })
    await act(async () => { button(host, '下一步').click() })
    await act(async () => { button(host, '一键配置模型').click() })
    assert.deepEqual(calls.filter(item => item[0] === 'key'), [['key', 'apimart', 'fixture-kept-key']])
    assert.deepEqual(calls.filter(item => item[0] === 'connect'), [['connect', 'apimart', 'fixture-kept-key']])
    await act(async () => { button(host, '返回').click() })
    assert.equal(host.querySelector('input[aria-label="API 密钥"]').value, 'fixture-kept-key')
    await act(async () => { button(host, '返回').click() })
    assert.equal(host.querySelector('input[aria-label="API 密钥"]'), null)
    await act(async () => { publish(promoView({ defaultChoice: 'api88' })) })
    assert.equal(checked().textContent.includes('APIMart'), true)
    await act(async () => { button(host, '下一步').click() })
    assert.equal(host.querySelector('input[aria-label="API 密钥"]').value, '')
    state.writePromoSnapshot(null)
    await act(async () => { root.unmount() })
  } finally {
    window.happyDOM.abort?.(); window.close()
    for (const [key, value] of Object.entries(previous)) {
      if (value === undefined) delete globalThis[key]
      else globalThis[key] = value
    }
  }
})

function mountCard(providers, state) {
  const { Window } = require('happy-dom')
  const window = new Window({ url: 'http://localhost/' })
  const previous = {
    window: globalThis.window, document: globalThis.document, navigator: globalThis.navigator,
    HTMLElement: globalThis.HTMLElement, IS_REACT_ACT_ENVIRONMENT: globalThis.IS_REACT_ACT_ENVIRONMENT,
  }
  globalThis.window = window
  globalThis.document = window.document
  globalThis.navigator = window.navigator
  globalThis.HTMLElement = window.HTMLElement
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  const calls = []
  const store = {
    settings: { saved: false, connections: [], analysis: null },
    saving: false,
    error: '',
    selectProvider(provider) { calls.push(['select', provider]) },
    setKey(value) { calls.push(['key', value]) },
    connect: async () => { calls.push(['connect']); return { ok: true } },
  }
  const watch = { useSponsorPromo() { return state.readPromoSnapshot() } }
  const Card = loadTs(path.join(__dirname, '../src/features/studio/ImportSetupCard.tsx'), {
    __globals: { window, document: window.document, navigator: window.navigator, HTMLElement: window.HTMLElement },
    'react-i18next': { useTranslation() {} },
    'react-router-dom': { useNavigate: () => () => {} },
    '../../i18n': i18n,
    '../../ui': ui,
    '../../analytics/experience': { trackExperience() {} },
    '../../analytics/events': { trackSponsorLinkOpened() {} },
    '../../analytics/successRateContract': { telemetryProvider: value => value },
    '../../analytics/workflow': { telemetryId: () => 't-empty' },
    '../../utils/externalLinks': { openExternalLink() {} },
    '../settings/useQuickConnect': { useQuickConnect: () => store },
    '../settings/providers': providers,
    '../settings/sponsorPromoState': state,
    '../settings/sponsorPromoWatch': watch,
    './studio.css': {},
  }, path.join(__dirname, '../src/features/studio')).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const root = createRoot(host)
  const restore = () => {
    window.happyDOM.abort?.(); window.close()
    for (const [key, value] of Object.entries(previous)) {
      if (value === undefined) delete globalThis[key]
      else globalThis[key] = value
    }
  }
  return { host, root, calls, restore, Card }
}

test('removed or stopped sponsors fall back to a visible neutral provider', async () => {
  const state = loadTs('sponsorPromoState.ts')
  const providers = loadTs('providers.ts', { '../../i18n': i18n, './sponsorPromoState': state })
  state.writePromoSnapshot(promoView({
    choices: ['other'],
    defaultChoice: 'other',
    statuses: { apimart: 'out_of_service', api88: 'out_of_service' },
    registerUrls: {},
  }))
  const listed = providers.recommendedSetupProviders()
  assert.equal(listed[0], 'deepseek')
  assert.equal(listed[1], 'dashscope')
  assert.equal(listed.includes('api88'), false)
  assert.equal(listed.includes('apimart'), false)
  const mounted = mountCard(providers, state)
  try {
    await act(async () => { mounted.root.render(React.createElement(mounted.Card)) })
    const radios = [...mounted.host.querySelectorAll('[role="radio"]')]
    assert.equal(radios.some(node => node.textContent.includes('88API') || node.textContent.includes('APIMart')), false)
    assert.equal(radios[0].getAttribute('aria-checked'), 'true')
    assert.equal(radios[0].textContent.includes('DeepSeek'), true)
    await act(async () => { button(mounted.host, '下一步').click() })
    assert.deepEqual(mounted.calls.filter(item => item[0] === 'select'), [['select', 'deepseek']])
  } finally {
    await act(async () => { mounted.root.unmount() })
    mounted.restore()
    state.writePromoSnapshot(null)
  }
})

test('an empty candidate list does not invent a provider or open its key flow', async () => {
  const state = loadTs('sponsorPromoState.ts')
  const providers = loadTs('providers.ts', { '../../i18n': i18n, './sponsorPromoState': state })
  state.writePromoSnapshot(promoView({
    choices: ['other'],
    defaultChoice: 'other',
    statuses: { apimart: 'out_of_service', api88: 'out_of_service' },
    registerUrls: {},
  }))
  const hidden = { ...providers, recommendedSetupProviders: () => [] }
  const mounted = mountCard(hidden, state)
  try {
    await act(async () => { mounted.root.render(React.createElement(mounted.Card)) })
    assert.equal(mounted.host.querySelectorAll('[role="radio"]').length, 0)
    assert.equal(mounted.host.querySelector('[data-setup-empty]')?.getAttribute('data-setup-empty'), '1')
    assert.equal(button(mounted.host, '去设置选择其他服务商') != null, true)
    assert.equal(button(mounted.host, '先用示例视频看看效果') != null, true)
    const next = button(mounted.host, '下一步')
    assert.equal(next.disabled, true)
    await act(async () => { next.click() })
    assert.deepEqual(mounted.calls, [])
    assert.equal(mounted.host.querySelector('input[aria-label="API 密钥"]'), null)
  } finally {
    await act(async () => { mounted.root.unmount() })
    mounted.restore()
    state.writePromoSnapshot(null)
  }
})

test('locale routing splits zh and overseas surfaces without breaking saved providers', () => {
  const state = loadTs('sponsorPromoState.ts')
  const providers = loadTs('providers.ts', { '../../i18n': i18n, './sponsorPromoState': state })
  const catalogView = loadTs('providerCatalogView.ts', {
    '../../i18n': i18n,
    './sponsorPromoState': state,
    './providers': providers,
  })
  try {
    state.writePromoSnapshot(promoView({
      source: 'cache',
      choices: ['apimart', 'api88', 'other'],
      defaultChoice: 'apimart',
      statuses: { apimart: 'healthy', api88: 'healthy' },
      registerUrls: {
        apimart: 'https://go.apimart.ai/cn',
        api88: 'https://88api.ai/sign-up?aff=global',
      },
      byLocale: {
        zh: {
          choices: ['apimart', 'other'],
          defaultChoice: 'apimart',
          registerUrls: { apimart: 'https://go.apimart.ai/cn' },
        },
        en: {
          choices: ['api88', 'other'],
          defaultChoice: 'api88',
          registerUrls: { api88: 'https://88api.ai/sign-up?aff=global' },
        },
        ja: {
          choices: ['other'],
          defaultChoice: 'other',
          registerUrls: {},
        },
      },
    }))

    state.setPromoLocale('zh-CN')
    assert.equal(state.promotionCurrentlyPromoted('apimart'), true)
    assert.equal(state.promotionCurrentlyPromoted('api88'), false)
    assert.equal(state.promotionRecommends('apimart'), true)
    assert.equal(state.promotionRegisterUrl('apimart'), 'https://go.apimart.ai/cn')
    assert.equal(state.promotionRegisterUrl('api88'), null)
    assert.equal(state.promotionSetupChoice(providers.recommendedSetupProviders()), 'apimart')

    state.setPromoLocale('en-US')
    assert.equal(state.promotionCurrentlyPromoted('apimart'), false)
    assert.equal(state.promotionCurrentlyPromoted('api88'), true)
    assert.equal(state.promotionRecommends('api88'), true)
    assert.equal(state.promotionRecommends('apimart'), false)
    assert.equal(state.promotionRegisterUrl('api88'), 'https://88api.ai/sign-up?aff=global')
    assert.equal(state.promotionRegisterUrl('apimart'), null)
    assert.equal(state.promotionSetupChoice(providers.recommendedSetupProviders()), 'api88')
    const groupedEn = catalogView.groupCatalog(catalogView.catalogProviders())
    assert.equal(groupedEn.recommended.some(item => item.id === 'api88'), true)
    assert.equal(groupedEn.recommended.some(item => item.id === 'apimart'), false)
    assert.equal(groupedEn.popular.some(item => item.id === 'apimart'), true)

    state.setPromoLocale('ja')
    assert.equal(state.promotionCurrentlyPromoted('apimart'), false)
    assert.equal(state.promotionCurrentlyPromoted('api88'), false)
    assert.equal(state.promotionSetupChoice(providers.recommendedSetupProviders()), 'deepseek')
  } finally {
    state.setPromoLocale(null)
    state.writePromoSnapshot(null)
  }
})

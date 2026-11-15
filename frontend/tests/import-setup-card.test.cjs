const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const React = require('react')
const { act } = React
const { createRoot } = require('react-dom/client')
const { loadTs } = require('./load-ts.cjs')

const i18n = { t: text => text }

function button(root, label) {
  return [...root.querySelectorAll('button')].find(node => node.textContent === label)
}

test('quick connect fills an empty analysis model from the provider catalog', () => {
  const { quickConnectPatch } = loadTs('quickConnect.ts', { '../../i18n': i18n })
  const { analysisCandidates } = loadTs('providerPresets.ts')
  const settings = {
    version: 1,
    connections: [{ id: 's', name: '88API', provider: 'api88', base_url: 'https://api.88api.ai/v1', api_key: 'sk-test', image_api: 'auto', image_base_url: '' }],
    analysis: { connection_id: 's', model: '', capability: 'auto', model_source: 'preset' },
  }
  const patch = quickConnectPatch(settings)
  assert.equal(patch.analysis.model, analysisCandidates('api88')[0])
  assert.equal(patch.analysis.model_source, 'preset')
  assert.equal(quickConnectPatch({ ...settings, analysis: { ...settings.analysis, model: 'already' } }), undefined)
  assert.equal(JSON.stringify(patch).includes('sk-test'), false)
})

test('the import card walks provider, key and connect, and the example path needs no model', async () => {
  const { Window } = require('happy-dom')
  const window = new Window({ url: 'http://localhost/' })
  const previous = { window: globalThis.window, document: globalThis.document, navigator: globalThis.navigator, HTMLElement: globalThis.HTMLElement, IS_REACT_ACT_ENVIRONMENT: globalThis.IS_REACT_ACT_ENVIRONMENT }
  globalThis.window = window
  globalThis.document = window.document
  globalThis.navigator = window.navigator
  globalThis.HTMLElement = window.HTMLElement
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  const events = []
  const calls = []
  const examples = []
  const store = {
    settings: { saved: false, connections: [], analysis: null },
    saving: false,
    error: '',
    selectProvider(provider) { calls.push(['provider', provider]) },
    setKey(value) { calls.push(['key', value]) },
    connect: async () => { calls.push(['connect']); return { ok: true } },
  }
  try {
    const Card = loadTs(path.join(__dirname, '../src/features/studio/ImportSetupCard.tsx'), {
      __globals: { window, document: window.document, navigator: window.navigator, HTMLElement: window.HTMLElement },
      'react-i18next': { useTranslation() {} },
      'react-router-dom': { useNavigate: () => to => calls.push(['settings', to]) },
      '../../i18n': i18n,
      '../../ui': {
        Btn: ({ children, onClick, disabled }) => React.createElement('button', { type: 'button', onClick, disabled }, children),
        Icon: { Check: () => React.createElement('i', null, 'check') },
      },
      '../../analytics/experience': { trackExperience: (event, props) => events.push({ event, props }) },
      '../../analytics/events': { trackSponsorLinkOpened: props => events.push({ event: 'sponsor_link_opened', props }) },
      '../../analytics/successRateContract': { telemetryProvider: value => value },
      '../../analytics/workflow': { telemetryId: () => 't-aaaaaaaaaaaa' },
      '../../utils/externalLinks': { openExternalLink: url => calls.push(['link', url]) },
      '../settings/useQuickConnect': { useQuickConnect: () => store },
      '../settings/providers': loadTs('providers.ts', { '../../i18n': i18n }),
      './studio.css': {},
    }, path.join(__dirname, '../src/features/studio')).default
    const host = document.createElement('div')
    document.body.appendChild(host)
    const root = createRoot(host)
    await act(async () => { root.render(React.createElement(Card, { onExample: () => examples.push('open'), keptMaterial: true })) })
    assert.equal(host.textContent.includes('先连接 AI 服务'), true)
    assert.equal(host.textContent.includes('先用示例视频看看效果'), true)
    assert.equal(host.textContent.includes('刚才的链接或文件会留着'), true)
    assert.equal(events.some(item => item.event === 'setup_presented' && item.props.placement === 'import_card' && item.props.trigger === 'initial'), true)
    const radios = [...host.querySelectorAll('[role="radio"]')]
    assert.deepEqual(radios.map(node => node.getAttribute('aria-checked')), ['true', 'false', 'false', 'false'])
    assert.equal(radios[0].textContent.includes('88API'), true)
    assert.equal(radios[2].textContent.includes('DeepSeek'), true)
    assert.equal(radios.some(node => node.textContent.includes('无限星河') || node.textContent.includes('Infistar')), false)
    await act(async () => { button(host, '先用示例视频看看效果').click() })
    assert.deepEqual(examples, ['open'])
    await act(async () => { button(host, '下一步').click() })
    assert.deepEqual(calls[0], ['provider', 'api88'])
    assert.equal(events.some(item => item.event === 'setup_step_done' && item.props.step === 'provider' && item.props.placement === 'import_card'), true)
    const key = host.querySelector('input[aria-label="API 密钥"]')
    assert.ok(key)
    await act(async () => { button(host, '下一步').click() })
    assert.equal(calls.some(item => item[0] === 'key'), false)
    const propsKey = Object.keys(key).find(name => name.startsWith('__reactProps'))
    await act(async () => { key[propsKey].onChange({ target: { value: 'sk-live-secret' } }) })
    await act(async () => { button(host, '下一步').click() })
    assert.deepEqual(calls[1], ['key', 'sk-live-secret'])
    assert.equal(events.some(item => item.event === 'setup_step_done' && item.props.step === 'key'), true)
    assert.equal(JSON.stringify(events).includes('sk-live-secret'), false)
    await act(async () => { button(host, '连接并保存').click() })
    assert.deepEqual(calls[2], ['connect'])
    assert.equal(events.some(item => item.event === 'setup_step_done' && item.props.step === 'connect' && item.props.provider === 'api88'), true)
    await act(async () => { root.unmount() })
  } finally {
    window.happyDOM.abort?.(); window.close()
    for (const [key, value] of Object.entries(previous)) {
      if (value === undefined) delete globalThis[key]
      else globalThis[key] = value
    }
  }
})

test('later only dismisses the first-run overlay', async () => {
  const { Window } = require('happy-dom')
  const window = new Window({ url: 'http://localhost/' })
  const previous = { window: globalThis.window, document: globalThis.document, navigator: globalThis.navigator, HTMLElement: globalThis.HTMLElement, sessionStorage: globalThis.sessionStorage, IS_REACT_ACT_ENVIRONMENT: globalThis.IS_REACT_ACT_ENVIRONMENT }
  globalThis.window = window
  globalThis.document = window.document
  globalThis.navigator = window.navigator
  globalThis.HTMLElement = window.HTMLElement
  globalThis.sessionStorage = window.sessionStorage
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  const statuses = []
  try {
    const FirstRun = loadTs('FirstRunSetup.tsx', {
      __globals: { window, document: window.document, navigator: window.navigator, HTMLElement: window.HTMLElement, sessionStorage: window.sessionStorage },
      'react-i18next': { useTranslation() {} },
      'react-router-dom': { useNavigate: () => () => {} },
      antd: { ConfigProvider: ({ children }) => children },
      '../../analytics/experience': { trackExperience() {} },
      '../../analytics/events': { trackSponsorLinkOpened() {} },
      '../../analytics/workflow': { telemetryId: () => 't-aaaaaaaaaaaa' },
      '../../i18n': i18n,
      '../../ui': {
        Btn: ({ children, onClick }) => React.createElement('button', { type: 'button', onClick }, children),
        Dialog: ({ children, open, title, footer }) => open ? React.createElement('div', { role: 'dialog', title }, children, footer) : null,
        Icon: { Check: () => null },
        StatusDot: () => null,
      },
      '../../utils/externalLinks': { openExternalLink() {} },
      './useQuickConnect': { useQuickConnect: () => ({
        settings: { saved: false, connections: [], analysis: null },
        busy: {},
        keyHints: {},
        saving: false,
        error: '',
        chooseProvider() {},
        editConnection() {},
        save: async () => ({ ok: true }),
      }) },
      './providers': loadTs('providers.ts', { '../../i18n': i18n }),
      './ProviderFields': { default: () => null },
      './modelSettingsLogic': {
        needsSetup: () => true,
        mainConnection: () => undefined,
        connectionReady: () => false,
      },
      './firstRunGuidance': loadTs('firstRunGuidance.ts'),
    }).default
    const host = document.createElement('div')
    document.body.appendChild(host)
    const root = createRoot(host)
    await act(async () => { root.render(React.createElement(FirstRun, { onStatus: value => statuses.push(value) })) })
    assert.ok(host.querySelector('[role="dialog"]'))
    assert.ok(statuses.length >= 1 && statuses.every(value => value === true))
    await act(async () => { button(host, '稍后设置').click() })
    assert.equal(host.querySelector('[role="dialog"]'), null)
    assert.equal(window.sessionStorage.getItem('autoclip.firstRunSetup.dismissed'), '1')
    assert.ok(statuses.every(value => value === true))
    await act(async () => { root.unmount() })
  } finally {
    window.happyDOM.abort?.(); window.close()
    for (const [key, value] of Object.entries(previous)) {
      if (value === undefined) delete globalThis[key]
      else globalThis[key] = value
    }
  }
})

test('leaving the provider step freezes one identity across a later promotion', async () => {
  const { Window } = require('happy-dom')
  const window = new Window({ url: 'http://localhost/' })
  const previous = { window: globalThis.window, document: globalThis.document, navigator: globalThis.navigator, HTMLElement: globalThis.HTMLElement, IS_REACT_ACT_ENVIRONMENT: globalThis.IS_REACT_ACT_ENVIRONMENT }
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
      store.settings = { connections: [{ id: 's', provider, api_key: '', name: provider }], analysis: { connection_id: 's' } }
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
    state.writePromoSnapshot({
      choices: next.choices, defaultChoice: next.default, statuses: next.statuses || {},
      registerUrls: next.register_urls || {}, notices: next.notices || {},
    })
    listeners.forEach(listen => listen())
  }
  try {
    const Card = loadTs(path.join(__dirname, '../src/features/studio/ImportSetupCard.tsx'), {
      __globals: { window, document: window.document, navigator: window.navigator, HTMLElement: window.HTMLElement },
      'react-i18next': { useTranslation() {} },
      'react-router-dom': { useNavigate: () => () => {} },
      '../../i18n': i18n,
      '../../ui': { Btn: ({ children, onClick, disabled }) => React.createElement('button', { type: 'button', onClick, disabled }, children), Icon: { Check: () => null } },
      '../../analytics/experience': { trackExperience() {} },
      '../../analytics/events': { trackSponsorLinkOpened: props => calls.push(['open', props.sponsor]) },
      '../../analytics/successRateContract': { telemetryProvider: value => value },
      '../../analytics/workflow': { telemetryId: () => 't-identity' },
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
    const radios = [...host.querySelectorAll('[role="radio"]')]
    assert.equal(radios[0].textContent.includes('88API'), true)
    assert.equal(radios[0].getAttribute('aria-checked'), 'true')
    await act(async () => { button(host, '下一步').click() })
    assert.deepEqual(calls.filter(item => item[0] === 'select'), [['select', 'api88']])
    await act(async () => {
      publish({
        choices: ['apimart', 'api88', 'other'],
        default: 'apimart',
        statuses: { apimart: 'healthy', api88: 'healthy' },
        register_urls: { apimart: 'https://api.apimart.ai/register', api88: 'https://88api.ai/sign-up' },
      })
    })
    await act(async () => { button(host, '获取 API Key').click() })
    assert.deepEqual(calls.filter(item => item[0] === 'open'), [['open', 'api88']])
    assert.equal(calls.some(item => item[0] === 'link' && String(item[1]).includes('apimart')), false)
    const key = host.querySelector('input[aria-label="API 密钥"]')
    const propsKey = Object.keys(key).find(name => name.startsWith('__reactProps'))
    await act(async () => { key[propsKey].onChange({ target: { value: 'fixture-apimart-key' } }) })
    await act(async () => { button(host, '下一步').click() })
    await act(async () => { button(host, '连接并保存').click() })
    assert.deepEqual(calls.filter(item => item[0] === 'key'), [['key', 'api88', 'fixture-apimart-key']])
    assert.deepEqual(calls.filter(item => item[0] === 'connect'), [['connect', 'api88', 'fixture-apimart-key']])
    assert.equal(providers.PROVIDERS.infistar === undefined, false)
    await act(async () => { root.unmount() })
  } finally {
    window.happyDOM.abort?.(); window.close()
    for (const [key, value] of Object.entries(previous)) {
      if (value === undefined) delete globalThis[key]
      else globalThis[key] = value
    }
  }
})

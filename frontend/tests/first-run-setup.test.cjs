const { test } = require('node:test')
const assert = require('node:assert/strict')
const React = require('react')
const { loadTs } = require('./load-ts.cjs')

function flatten(node) {
  if (typeof node?.type === 'function') {
    try { return flatten(node.type(node.props || {})) } catch { return [node] }
  }
  if (Array.isArray(node)) return node.flatMap(flatten)
  if (!React.isValidElement(node)) return [node]
  const children = React.Children.toArray(node.props?.children)
  const extra = []
  if (node.props?.footer) extra.push(node.props.footer)
  if (node.props?.description) extra.push(node.props.description)
  return [node, ...children.flatMap(flatten), ...extra.flatMap(flatten)]
}

function renderFirstRun() {
  const events = []
  const links = []
  const navigations = []
  let settings = { saved: false, connections: [], analysis: null }
  const store = {
    settings,
    busy: {}, lists: {}, listErrors: {},
    saving: false,
    error: '',
    chooseProvider(_role, provider) {
      settings = { ...settings, connections: [{ id: 's', name: provider, provider, base_url: '', api_key: '', image_api: 'auto', image_base_url: '' }], analysis: { connection_id: 's', model: '', capability: 'auto' } }
      store.settings = settings
    },
    editConnection() {},
    save: async () => ({ ok: true }),
  }
  let cursor = 0
  const slots = []
  const react = {
    useState(value) {
      const i = cursor++
      if (!(i in slots)) slots[i] = value
      return [slots[i], next => { slots[i] = typeof next === 'function' ? next(slots[i]) : next }]
    },
    useRef(value) {
      const i = cursor++
      if (!(i in slots)) slots[i] = { current: value }
      return slots[i]
    },
    useEffect() {},
  }
  const providers = loadTs('providers.ts', { '../../i18n': { t: text => text } })
  const FirstRun = loadTs('FirstRunSetup.tsx', {
    react,
    'react-i18next': { useTranslation() {} },
    'react-router-dom': { useNavigate: () => to => navigations.push(to) },
    antd: { ConfigProvider: ({ children }) => children },
    '../../analytics/experience': { trackExperience: (event, props) => events.push({ event, props }) },
    '../../analytics/events': { trackSponsorLinkOpened: props => events.push({ event: 'sponsor_link_opened', props }) },
    '../../analytics/workflow': { telemetryId: () => 't-aaaaaaaaaaaa' },
    '../../i18n': { t: (text, values) => (values && values.name ? text.replace('{{name}}', values.name) : text) },
    '../../ui': {
      Btn: ({ children, onClick }) => React.createElement('button', { onClick }, children),
      Dialog: ({ children, title, footer, description }) => React.createElement('dialog', { title, description }, children, footer),
      Icon: { Check: () => React.createElement('i', null, 'check') },
      StatusDot: 'status',
    },
    '../../utils/externalLinks': { openExternalLink: url => links.push(url) },
    './useQuickConnect': { useQuickConnect: () => store },
    './providers': providers,
    './ModelPicker': { default: () => null },
    './ProviderFields': { default: () => React.createElement('div', { className: 'fields' }) },
    './modelSettingsLogic': {
      needsSetup: () => true,
      mainConnection: value => value.connections[0],
      connectionReady: connection => !!(connection.api_key || connection.has_key),
    },
    './firstRunGuidance': loadTs('firstRunGuidance.ts'),
  }).default
  const render = () => { cursor = 0; return FirstRun({}) }
  return { events, links, navigations, store, providers, render }
}

function radios(nodes) {
  return nodes.filter(n => n?.props?.['aria-checked'] !== undefined)
}

function textOf(node) {
  return flatten(node).filter(item => typeof item === 'string').join('')
}

test('first-run chooser defaults to APIMart, opens its register URL, and never pastes the clipboard', () => {
  const { events, links, navigations, store, providers, render } = renderFirstRun()
  const nodes = flatten(render())
  const dialog = nodes.find(n => n?.props?.title)
  assert.equal(dialog?.props.title, '选择 AI 服务商')
  assert.equal(dialog?.props.description, undefined)
  assert.equal(JSON.stringify(nodes).includes('没有字幕的视频需要转写'), false)
  assert.equal(JSON.stringify(nodes).includes('AutoClip 通过 AI 服务商理解视频'), false)
  const options = radios(nodes)
  assert.equal(options[0].props['aria-checked'], true)
  assert.match(textOf(options[0]), /APIMart/)
  assert.equal(options.slice(1).every(item => item.props['aria-checked'] === false), true)
  const cta = nodes.filter(n => n?.type === 'button').at(-1)
  assert.match(String(cta.props.children), /APIMart/)
  cta.props.onClick()
  assert.equal(links[0], providers.PROVIDERS.apimart.sponsor.registerUrl)
  assert.equal(events.some(e => e.event === 'setup_action' && e.props.action === 'one_click' && e.props.provider === 'apimart'), true)
  assert.equal(JSON.stringify(events).includes('sk-'), false)
  assert.equal(JSON.stringify(events).includes(links[0]), false)
  assert.equal(store.settings.connections[0].provider, 'apimart')
  assert.equal(store.settings.connections[0].base_url, '')
  assert.equal(navigations.length, 0)
})

test('first-run does not offer 88API, and its saved preset stays usable', () => {
  const { providers, render } = renderFirstRun()
  const shown = radios(flatten(render()))
  assert.equal(shown.some(node => textOf(node).includes('88API')), false)
  assert.equal(providers.PROVIDERS.api88.sponsor, undefined)
  assert.equal(providers.PROVIDERS.api88.cloud.baseUrl, 'https://api.88api.ai/v1')
  assert.equal(providers.PROVIDERS.api88.apiKeyField, 'api88_api_key')
})

test('first-run does not promote Infistar; the saved preset and other providers remain', () => {
  const infistar = renderFirstRun()
  const shown = radios(flatten(infistar.render()))
  assert.equal(shown.some(node => textOf(node).includes('Infistar')), false)
  assert.equal(infistar.providers.PROVIDERS.infistar.sponsor, undefined)
  assert.equal(infistar.providers.PROVIDERS.infistar.cloud.baseUrl, 'https://infistar.cc/v1')

  const other = renderFirstRun()
  radios(flatten(other.render())).find(node => textOf(node).includes('其他')).props.onClick()
  const chosen = flatten(other.render())
  assert.match(chosen.filter(n => typeof n === 'string').join(''), /建议先连接 DeepSeek/)
  const settingsButton = chosen.find(n => n?.type === 'button' && String(n.props?.children).includes('去设置选择其他服务商'))
  assert.ok(settingsButton)
  settingsButton.props.onClick()
  assert.equal(other.navigations[0], '/settings?section=ai&return_import=1')
  assert.equal(other.events.some(e => e.event === 'setup_action' && e.props.action === 'open_settings'), true)

  const connect = renderFirstRun()
  radios(flatten(connect.render())).find(node => textOf(node).includes('其他')).props.onClick()
  flatten(connect.render()).filter(n => n?.type === 'button').at(-1).props.onClick()
  assert.equal(connect.links.length, 0)
  assert.equal(connect.navigations.length, 0)
  assert.equal(connect.store.settings.connections[0].provider, 'deepseek')
  assert.equal(connect.events.some(e => e.event === 'setup_action' && e.props.action === 'connect_recommended' && e.props.provider === 'deepseek'), true)
})

function button(root, label) {
  return [...root.querySelectorAll('button')].find(node => node.textContent === label)
}

async function mountFirstRun() {
  const { Window } = require('happy-dom')
  const { act } = React
  const { createRoot } = require('react-dom/client')
  const window = new Window({ url: 'http://localhost/' })
  const previous = {
    window: globalThis.window, document: globalThis.document, navigator: globalThis.navigator,
    HTMLElement: globalThis.HTMLElement, sessionStorage: globalThis.sessionStorage,
    IS_REACT_ACT_ENVIRONMENT: globalThis.IS_REACT_ACT_ENVIRONMENT,
  }
  globalThis.window = window
  globalThis.document = window.document
  globalThis.navigator = window.navigator
  globalThis.HTMLElement = window.HTMLElement
  globalThis.sessionStorage = window.sessionStorage
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  const links = []
  const calls = []
  const store = {
    settings: { saved: false, connections: [], analysis: null },
    busy: {}, lists: {}, listErrors: {},
    keyHints: {},
    saving: false,
    error: '',
    chooseProvider(_role, provider) {
      calls.push(provider)
      store.settings = {
        saved: false,
        connections: [{
          id: 's', provider, name: provider,
          base_url: 'https://api.apimart.ai/v1',
          api_key: 'fixture-kept-key',
        }],
        analysis: { connection_id: 's', model: '' },
      }
    },
    editConnection() {},
    save: async () => ({ ok: true }),
  }
  const state = loadTs('sponsorPromoState.ts')
  const providers = loadTs('providers.ts', { '../../i18n': { t: text => text }, './sponsorPromoState': state })
  const FirstRun = loadTs('FirstRunSetup.tsx', {
    __globals: {
      window, document: window.document, navigator: window.navigator,
      HTMLElement: window.HTMLElement, sessionStorage: window.sessionStorage,
    },
    'react-i18next': { useTranslation() {} },
    'react-router-dom': { useNavigate: () => () => {} },
    antd: { ConfigProvider: ({ children }) => children },
    '../../analytics/experience': { trackExperience() {} },
    '../../analytics/events': { trackSponsorLinkOpened() {} },
    '../../analytics/workflow': { telemetryId: () => 't-mounted' },
    '../../i18n': { t: (text, values) => (values && values.name ? text.replace('{{name}}', values.name) : text) },
    '../../ui': {
      Btn: ({ children, onClick }) => React.createElement('button', { type: 'button', onClick }, children),
      Dialog: ({ children, open, title, footer, description }) => open ? React.createElement('div', { role: 'dialog', title, description }, children, footer) : null,
      Icon: { Check: () => null },
      StatusDot: () => null,
    },
    '../../utils/externalLinks': { openExternalLink: url => links.push(url) },
    './useQuickConnect': { useQuickConnect: () => store },
    './providers': providers,
    './ModelPicker': { default: () => null },
    './ProviderFields': {
      default: ({ connection }) => React.createElement('div', {
        'data-fields': connection?.provider || '',
        'data-key': connection?.api_key || '',
        'data-base': connection?.base_url || '',
      }),
    },
    './modelSettingsLogic': {
      needsSetup: () => true,
      mainConnection: value => value.connections?.find(item => item.id === value.analysis?.connection_id),
      connectionReady: connection => !!(connection?.api_key || connection?.has_key),
    },
    './firstRunGuidance': loadTs('firstRunGuidance.ts'),
    './sponsorPromoState': state,
    './sponsorPromoWatch': {
      readSponsorPromo: () => null,
      subscribeSponsorPromo: () => () => {},
    },
  }).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const root = createRoot(host)
  await act(async () => { root.render(React.createElement(FirstRun, { openRequest: 1 })) })
  return {
    window, previous, host, root, links, calls, store, state, act,
    close: async () => {
      state.writePromoSnapshot(null)
      await act(async () => { root.unmount() })
      window.happyDOM.abort?.(); window.close()
      for (const [key, value] of Object.entries(previous)) {
        if (value === undefined) delete globalThis[key]
        else globalThis[key] = value
      }
    },
  }
}

test('mounted first-run keeps a hand-selected provider when a healthy snapshot drops it', async () => {
  const mounted = await mountFirstRun()
  try {
    const radios = () => [...mounted.host.querySelectorAll('[role="radio"]')]
    assert.equal(radios()[0].textContent.includes('APIMart'), true)
    assert.equal(radios().some(node => node.textContent.includes('88API')), false)
    await mounted.act(async () => { radios()[0].click() })
    await mounted.act(async () => {
      mounted.state.writePromoSnapshot({
        choices: ['other'],
        defaultChoice: 'other',
        statuses: { apimart: 'healthy' },
        registerUrls: { apimart: 'https://go.apimart.ai/tw-autoclip' },
        notices: { apimart: { zh: '已撤下推荐' } },
        source: 'cache',
      })
    })
    const selected = radios().find(node => node.getAttribute('aria-checked') === 'true')
    assert.equal(selected.textContent.includes('APIMart'), true)
    assert.equal(selected.textContent.includes('推荐'), false)
    assert.equal(selected.textContent.includes('赞助'), false)
    assert.equal(selected.textContent.includes('获取 API Key'), false)
    assert.match(selected.textContent, /兼容网关/)
    assert.equal(radios().some(node => node.textContent.includes('其他')), true)
    assert.match(mounted.host.textContent, /已撤下推荐/)
    await mounted.act(async () => { button(mounted.host, '下一步').click() })
    assert.deepEqual(mounted.links, [])
    assert.deepEqual(mounted.calls, ['apimart'])
    assert.equal(mounted.host.querySelector('[data-fields]').getAttribute('data-fields'), 'apimart')
    assert.equal(mounted.host.querySelector('[data-fields]').getAttribute('data-key'), 'fixture-kept-key')
    assert.equal(mounted.store.settings.connections[0].base_url, 'https://api.apimart.ai/v1')
  } finally {
    await mounted.close()
  }
})

test('mounted first-run does not open a stale register link after out_of_service', async () => {
  const mounted = await mountFirstRun()
  try {
    const radios = () => [...mounted.host.querySelectorAll('[role="radio"]')]
    await mounted.act(async () => { radios()[0].click() })
    await mounted.act(async () => {
      mounted.state.writePromoSnapshot({
        choices: ['other'],
        defaultChoice: 'other',
        statuses: { apimart: 'out_of_service' },
        registerUrls: { apimart: 'https://go.apimart.ai/tw-autoclip' },
        notices: { apimart: { zh: '暂停服务' } },
        source: 'cache',
      })
    })
    const selected = radios().find(node => node.getAttribute('aria-checked') === 'true')
    assert.equal(selected.textContent.includes('APIMart'), true)
    assert.equal(selected.textContent.includes('推荐'), false)
    assert.equal(selected.textContent.includes('赞助'), false)
    await mounted.act(async () => { button(mounted.host, '下一步').click() })
    assert.deepEqual(mounted.links, [])
    assert.deepEqual(mounted.calls, ['apimart'])
    assert.equal(mounted.store.settings.connections[0].api_key, 'fixture-kept-key')
  } finally {
    await mounted.close()
  }
})

test('mounted key step keeps the saved provider after the recommendation is withdrawn', async () => {
  const mounted = await mountFirstRun()
  try {
    await mounted.act(async () => { button(mounted.host, '通过 APIMart 一键获取').click() })
    assert.equal(mounted.links[0], mounted.state.promotionRegisterUrl('apimart', 'https://go.apimart.ai/tw-autoclip') || 'https://go.apimart.ai/tw-autoclip')
    assert.equal(mounted.links.length, 1)
    assert.deepEqual(mounted.calls, ['apimart'])
    assert.equal(mounted.host.querySelector('[data-fields]').getAttribute('data-key'), 'fixture-kept-key')
    await mounted.act(async () => {
      mounted.state.writePromoSnapshot({
        choices: ['api88', 'other'],
        defaultChoice: 'api88',
        statuses: { apimart: 'out_of_service', api88: 'healthy' },
        registerUrls: {
          apimart: 'https://go.apimart.ai/tw-autoclip',
          api88: 'https://88api.ai/sign-up?aff=2PIc',
        },
        source: 'cache',
      })
    })
    assert.deepEqual(mounted.calls, ['apimart'])
    assert.equal(mounted.links.length, 1)
    assert.equal(mounted.links[0].includes('88api.ai'), false)
    assert.equal(mounted.host.querySelector('[data-fields]').getAttribute('data-fields'), 'apimart')
    assert.equal(mounted.host.querySelector('[data-fields]').getAttribute('data-key'), 'fixture-kept-key')
    assert.equal(mounted.host.querySelector('[data-fields]').getAttribute('data-base'), 'https://api.apimart.ai/v1')
    assert.equal(mounted.store.settings.connections[0].provider, 'apimart')
    await mounted.act(async () => { button(mounted.host, '返回').click() })
    const back = [...mounted.host.querySelectorAll('[role="radio"]')]
    const selected = back.find(node => node.getAttribute('aria-checked') === 'true')
    assert.equal(selected.textContent.includes('APIMart'), true)
    assert.equal(selected.textContent.includes('推荐'), false)
    assert.equal(selected.textContent.includes('赞助'), false)
    const restored = back.find(node => node.textContent.includes('88API'))
    assert.ok(restored)
    assert.match(restored.textContent, /推荐/)
    assert.equal(restored.getAttribute('aria-checked'), 'false')
    assert.deepEqual(mounted.calls, ['apimart'])
    assert.equal(mounted.store.settings.connections[0].api_key, 'fixture-kept-key')
    assert.equal(mounted.links.length, 1)
  } finally {
    await mounted.close()
  }
})

test('an unselected withdrawn recommendation leaves the first-run list and can return', async () => {
  const mounted = await mountFirstRun()
  try {
    const radios = () => [...mounted.host.querySelectorAll('[role="radio"]')]
    await mounted.act(async () => { radios().find(node => node.textContent.includes('其他')).click() })
    await mounted.act(async () => {
      mounted.state.writePromoSnapshot({
        choices: ['other'],
        defaultChoice: 'other',
        statuses: { apimart: 'healthy' },
        registerUrls: { apimart: 'https://go.apimart.ai/tw-autoclip' },
        source: 'cache',
      })
    })
    assert.equal(radios().some(node => node.textContent.includes('APIMart')), false)
    assert.equal(radios().some(node => node.textContent.includes('推荐')), false)
    assert.equal(radios().find(node => node.getAttribute('aria-checked') === 'true').textContent.includes('其他'), true)
    await mounted.act(async () => {
      mounted.state.writePromoSnapshot({
        choices: ['apimart', 'other'],
        defaultChoice: 'apimart',
        statuses: { apimart: 'healthy' },
        registerUrls: { apimart: 'https://go.apimart.ai/tw-autoclip?seq=2' },
        source: 'cache',
      })
    })
    const restored = radios()
    const apimart = restored.find(node => node.textContent.includes('APIMart'))
    assert.ok(apimart)
    assert.match(apimart.textContent, /推荐/)
    assert.equal(restored.find(node => node.getAttribute('aria-checked') === 'true').textContent.includes('其他'), true)
    await mounted.act(async () => { button(mounted.host, '连接 DeepSeek').click() })
    assert.deepEqual(mounted.calls, ['deepseek'])
    assert.deepEqual(mounted.links, [])
  } finally {
    await mounted.close()
  }
})

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
    busy: {},
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
    './useModelSettings': { useModelSettings: () => store },
    './providers': providers,
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

test('first-run chooser defaults to 88API, opens the register URL, and never pastes the clipboard', () => {
  const { events, links, navigations, store, providers, render } = renderFirstRun()
  const nodes = flatten(render())
  const dialog = nodes.find(n => n?.props?.title)
  assert.equal(dialog?.props.title, '选择 AI 服务商')
  assert.equal(dialog?.props.description, undefined)
  assert.equal(JSON.stringify(nodes).includes('没有字幕的视频需要转写'), false)
  assert.equal(JSON.stringify(nodes).includes('AutoClip 通过 AI 服务商理解视频'), false)
  const options = nodes.filter(n => n?.props?.['aria-checked'] !== undefined)
  assert.deepEqual(options.map(n => n.props['aria-checked']), [true, false, false])
  const cta = nodes.filter(n => n?.type === 'button').at(-1)
  assert.match(String(cta.props.children), /88API/)
  cta.props.onClick()
  assert.equal(links[0], providers.PROVIDERS.api88.sponsor.registerUrl)
  assert.equal(events.some(e => e.event === 'setup_action' && e.props.action === 'one_click' && e.props.provider === 'api88'), true)
  assert.equal(JSON.stringify(events).includes('sk-'), false)
  assert.equal(JSON.stringify(events).includes(links[0]), false)
  assert.equal(store.settings.connections[0].provider, 'api88')
  assert.equal(navigations.length, 0)
})

test('first-run Infistar opens its register URL; other providers go to settings', () => {
  const infistar = renderFirstRun()
  flatten(infistar.render()).filter(n => n?.props?.['aria-checked'] !== undefined)[1].props.onClick()
  flatten(infistar.render()).filter(n => n?.type === 'button').at(-1).props.onClick()
  assert.equal(infistar.links[0], infistar.providers.PROVIDERS.infistar.sponsor.registerUrl)
  assert.equal(infistar.events.some(e => e.event === 'setup_action' && e.props.action === 'one_click' && e.props.provider === 'infistar'), true)
  assert.equal(infistar.navigations.length, 0)

  const other = renderFirstRun()
  flatten(other.render()).filter(n => n?.props?.['aria-checked'] !== undefined)[2].props.onClick()
  flatten(other.render()).filter(n => n?.type === 'button').at(-1).props.onClick()
  assert.equal(other.links.length, 0)
  assert.equal(other.navigations[0], '/settings?section=ai')
  assert.equal(other.events.some(e => e.event === 'setup_action' && e.props.action === 'open_settings'), true)
})

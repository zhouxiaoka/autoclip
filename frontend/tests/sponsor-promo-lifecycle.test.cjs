const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

const i18n = { t: text => text }
const nodeTimers = { setTimeout, clearTimeout, setInterval, clearInterval }

function view(extra) {
  return {
    choices: ['apimart', 'api88', 'other'],
    default: 'apimart',
    statuses: {},
    notices: {},
    register_urls: {},
    ...extra,
  }
}

function deferred() {
  let resolve
  const promise = new Promise(result => { resolve = result })
  return { promise, resolve }
}

function loadWatch(api, react = { useEffect() {}, useState: value => [value, () => {}] }) {
  return loadTs('sponsorPromoWatch.ts', {
    '../../i18n': i18n,
    '../../services/api': { default: api },
    react,
    __globals: nodeTimers,
  })
}

test('a delayed accept is published by the same watch, and a disposed host does not publish', async () => {
  const first = deferred()
  const second = deferred()
  const calls = []
  const api = {
    get(_url, opts) {
      calls.push(opts.params)
      return calls.length === 1 ? first.promise : second.promise
    },
  }
  const watch = loadWatch(api)
  const stop = watch.startSponsorPromoWatch()
  first.resolve({ data: view({ pending: true, revision: 1, source: 'bundled' }) })
  second.resolve({ data: view({ pending: false, revision: 2, sequence: 50, source: 'cache', default: 'apimart' }) })
  await first.promise
  await second.promise
  await new Promise(resolve => setTimeout(resolve, 30))
  assert.equal(watch.readSponsorPromo().sequence, 50)
  assert.equal(calls.some(params => params && params.wait === 2), true)
  stop()
  assert.equal(watch.readSponsorPromo().sequence, 50)
})

test('an older startup response and its cleanup cannot replace or clear a newer host', async () => {
  const older = deferred()
  const newer = deferred()
  let count = 0
  const api = {
    get() {
      count += 1
      return count === 1 ? older.promise : newer.promise
    },
  }
  const watch = loadWatch(api)
  const stopOld = watch.startSponsorPromoWatch()
  const stopNew = watch.startSponsorPromoWatch()
  newer.resolve({ data: view({ default: 'apimart', sequence: 4, pending: false }) })
  await newer.promise
  await new Promise(resolve => setTimeout(resolve, 30))
  assert.equal(watch.readSponsorPromo().defaultChoice, 'apimart')
  older.resolve({ data: view({ choices: ['api88', 'apimart', 'other'], default: 'api88', sequence: 3, pending: false }) })
  await older.promise
  await new Promise(resolve => setTimeout(resolve, 30))
  assert.equal(watch.readSponsorPromo().defaultChoice, 'apimart')
  assert.equal(watch.readSponsorPromo().sequence, 4)
  stopOld()
  assert.equal(watch.readSponsorPromo().sequence, 4)
  stopNew()
  assert.equal(watch.readSponsorPromo().sequence, 4)
})

test('an out of service sponsor is not upsold, and an existing provider stays listed', () => {
  const state = loadTs('sponsorPromoState.ts')
  const providers = loadTs('providers.ts', { '../../i18n': i18n, './sponsorPromoState': state })
  const failureAction = loadTs(path.join(__dirname, '../src/features/studio/failureAction.ts'), {
    '../settings/sponsorPromoState': state,
  })
  const catalog = loadTs('providerCatalogView.ts', {
    '../../i18n': i18n,
    './sponsorPromoState': state,
    './providers': providers,
  })
  assert.equal(providers.PROVIDERS.infistar === undefined, false)
  state.writePromoSnapshot({
    choices: ['api88', 'other'],
    defaultChoice: 'api88',
    statuses: { apimart: 'out_of_service', api88: 'healthy' },
    registerUrls: { api88: 'https://88api.ai/sign-up?aff=kept' },
    notices: { apimart: { en: 'Down', ja: '停止', zh: '暂停' } },
  })
  assert.equal(state.promotionRecommends('api88'), true)
  assert.equal(state.promotionRecommends('apimart'), false)
  assert.equal(state.promotionAllowsUpsell('apimart'), null || false)
  assert.equal(state.promotionRegisterUrl('apimart', 'https://api.apimart.ai/register'), null)
  assert.equal(state.promotionRegisterUrl('api88', 'https://88api.ai/register'), 'https://88api.ai/sign-up?aff=kept')
  assert.equal(state.promotionEligible('apimart'), false)
  assert.equal(state.promotionEligible('api88'), true)
  assert.equal(failureAction.rechargeTarget('apimart'), null)
  assert.equal(failureAction.rechargeTarget('api88').sponsor, true)
  assert.equal(failureAction.rechargeTarget('deepseek') === null, false)
  const listed = providers.recommendedSetupProviders()
  assert.equal(listed.includes('apimart'), false)
  assert.equal(listed.includes('api88'), true)
  assert.equal(providers.PROVIDERS.apimart === undefined, false)
  const grouped = catalog.groupCatalog(catalog.catalogProviders())
  assert.equal(grouped.recommended.some(item => item.id === 'apimart'), false)
  assert.equal(grouped.popular.some(item => item.id === 'apimart'), true)
  assert.equal(grouped.popular.some(item => item.id === 'infistar') || grouped.recommended.some(item => item.id === 'infistar'), true)
  assert.equal(promoNotice(state), '暂停')
})

function promoNotice(state) {
  const { loadTs } = require('./load-ts.cjs')
  const promo = loadTs('sponsorPromo.ts', {
    '../../i18n': i18n,
    '../../services/api': { default: { get() { return Promise.resolve({ data: null }) } } },
    './providers': loadTs('providers.ts', { '../../i18n': i18n, './sponsorPromoState': state }),
  })
  const applied = promo.applySponsorPromo({
    choices: state.readPromoSnapshot().choices,
    default: state.readPromoSnapshot().defaultChoice,
    statuses: state.readPromoSnapshot().statuses,
    notices: state.readPromoSnapshot().notices,
  })
  return promo.providerServiceNotice(applied, 'apimart', 'zh').text
}

test('a mounted screen still receives the accept after more than 15 pending rounds', { timeout: 30000 }, async () => {
  let resumes = 0
  const calls = []
  const api = {
    async get(_url, opts) {
      const params = opts.params || {}
      calls.push(params)
      if (params.trigger === 'resume') resumes += 1
      if (resumes <= 16) return { data: view({ pending: true, revision: resumes, source: 'bundled' }) }
      return { data: view({ pending: false, revision: resumes + 1, sequence: 77, source: 'cache' }) }
    },
  }
  const React = require('react')
  const watch = loadWatch(api, React)
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
  const { act } = React
  const { createRoot } = require('react-dom/client')
  function Host() {
    const [textValue, setTextValue] = React.useState('none')
    React.useEffect(() => {
      const stop = watch.startSponsorPromoWatch()
      const unsub = watch.subscribeSponsorPromo(() => {
        const sequence = watch.readSponsorPromo()?.sequence
        if (sequence) React.act(() => setTextValue(String(sequence)))
      })
      return () => { stop(); unsub() }
    }, [])
    return React.createElement('output', { id: 'promo-sequence' }, textValue)
  }
  const host = window.document.createElement('div')
  window.document.body.appendChild(host)
  const root = createRoot(host)
  const text = () => host.querySelector('#promo-sequence')?.textContent
  try {
    await act(async () => { root.render(React.createElement(Host)) })
    const deadline = Date.now() + 8000
    while (Date.now() < deadline && watch.readSponsorPromo()?.sequence !== 77) {
      await new Promise(resolve => nodeTimers.setTimeout(resolve, 40))
    }
    await act(async () => { await new Promise(resolve => nodeTimers.setTimeout(resolve, 0)) })
    assert.equal(watch.readSponsorPromo()?.sequence, 77, `resumes=${resumes} calls=${calls.length}`)
    assert.equal(text(), '77')
    assert.ok(resumes > 15, `resume rounds ${resumes}`)
    assert.equal(calls.some(params => params.trigger === 'interval'), false)
    const beforeStop = calls.length
    await act(async () => { root.unmount() })
    await new Promise(resolve => setTimeout(resolve, 500))
    const afterQuiet = calls.length
    await new Promise(resolve => setTimeout(resolve, 800))
    assert.equal(calls.length, afterQuiet)
    assert.ok(afterQuiet - beforeStop < 4)
    assert.equal(watch.readSponsorPromo().sequence, 77)
  } finally {
    root.unmount()
    globalThis.window = previous.window
    globalThis.document = previous.document
    globalThis.navigator = previous.navigator
    globalThis.HTMLElement = previous.HTMLElement
    globalThis.IS_REACT_ACT_ENVIRONMENT = previous.IS_REACT_ACT_ENVIRONMENT
  }
})

test('StrictMode keeps one host, and a late old response cannot replace it or survive unmount', async () => {
  const { Window } = require('happy-dom')
  const window = new Window({ url: 'http://localhost/' })
  const previous = {
    window: globalThis.window, document: globalThis.document, HTMLElement: globalThis.HTMLElement,
    IS_REACT_ACT_ENVIRONMENT: globalThis.IS_REACT_ACT_ENVIRONMENT,
  }
  globalThis.window = window
  globalThis.document = window.document
  globalThis.HTMLElement = window.HTMLElement
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  const React = require('react')
  const { act } = React
  const { createRoot } = require('react-dom/client')
  const pending = []
  const api = {
    get() {
      let resolve
      const promise = new Promise(result => { resolve = result })
      pending.push(resolve)
      return promise
    },
  }
  const watch = loadWatch(api, React)
  function Host() {
    React.useEffect(() => watch.startSponsorPromoWatch(), [])
    const promo = watch.useSponsorPromo()
    return React.createElement('output', { id: 'promo-sequence' }, String(promo?.defaultChoice ?? 'none'))
  }
  const node = window.document.createElement('div')
  window.document.body.appendChild(node)
  const root = createRoot(node)
  try {
    await act(async () => {
      root.render(React.createElement(React.StrictMode, null, React.createElement(Host)))
      await new Promise(resolve => setTimeout(resolve, 30))
    })
    assert.ok(pending.length >= 1)
    const started = pending.length
    await act(async () => {
      pending[pending.length - 1]({ data: view({ pending: false, revision: 2, sequence: 8, default: 'apimart' }) })
      await new Promise(resolve => setTimeout(resolve, 30))
    })
    assert.equal(node.querySelector('#promo-sequence').textContent, 'apimart')
    if (pending.length > 1) {
      await act(async () => {
        pending[0]({ data: view({ pending: false, revision: 1, sequence: 3, default: 'api88', choices: ['api88', 'apimart', 'other'] }) })
        await new Promise(resolve => setTimeout(resolve, 30))
      })
    }
    assert.equal(watch.readSponsorPromo().defaultChoice, 'apimart')
    assert.equal(watch.readSponsorPromo().sequence, 8)
    await act(async () => { root.unmount() })
    const after = pending.length
    await new Promise(resolve => setTimeout(resolve, 50))
    assert.equal(pending.length, after)
    assert.ok(started >= 1)
  } finally {
    root.unmount()
    globalThis.window = previous.window
    globalThis.document = previous.document
    globalThis.HTMLElement = previous.HTMLElement
    globalThis.IS_REACT_ACT_ENVIRONMENT = previous.IS_REACT_ACT_ENVIRONMENT
  }
})

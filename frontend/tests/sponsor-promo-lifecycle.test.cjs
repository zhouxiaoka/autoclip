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
  assert.equal(state.promotionAllowsUpsell('apimart'), false)
  assert.equal(state.promotionRegisterUrl('apimart', 'https://go.apimart.ai/tw-autoclip'), null)
  assert.equal(state.promotionRegisterUrl('api88', 'https://88api.ai/register'), 'https://88api.ai/sign-up?aff=kept')
  assert.equal(state.promotionEligible('apimart'), false)
  assert.equal(state.promotionEligible('api88'), true)
  assert.equal(failureAction.rechargeTarget('apimart'), null)
  assert.equal(failureAction.rechargeTarget('api88'), null)
  assert.equal(failureAction.rechargeTarget('deepseek') === null, false)
  const listed = providers.recommendedSetupProviders()
  assert.equal(listed.includes('apimart'), false)
  assert.equal(listed.includes('api88'), true)
  assert.deepEqual([...listed].slice(0, 3), ['deepseek', 'dashscope', 'api88'])
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

async function untilSequence(watch, sequence) {
  const deadline = Date.now() + 2000
  while (Date.now() < deadline && watch.readSponsorPromo()?.sequence !== sequence) {
    await new Promise(resolve => setTimeout(resolve, 10))
  }
}

test('settings and the idle interval still accept a snapshot published after startup follow ends', async () => {
  const saved = { provider: 'api88', api_key: 'fixture-key', base_url: 'https://api.88api.ai/v1' }
  const before = JSON.stringify(saved)
  let mode = 'startup'
  const calls = []
  const api = {
    async get(_url, opts) {
      const params = opts.params || {}
      calls.push(params)
      if (params.trigger === 'startup') {
        return { data: view({ pending: false, revision: 5, sequence: 10, instance: 'boot-1', source: 'cache' }) }
      }
      if (params.trigger === 'resume') {
        const sequence = mode === 'interval' ? 12 : 11
        return { data: view({ pending: false, revision: 6, sequence, instance: 'boot-1', source: 'cache' }) }
      }
      return { data: view({ pending: true, revision: 5, sequence: mode === 'interval' ? 11 : 10, instance: 'boot-1', source: 'cache' }) }
    },
  }
  const watch = loadWatch(api)
  const stop = watch.startSponsorPromoWatch()
  try {
    await untilSequence(watch, 10)
    assert.equal(watch.readSponsorPromo().sequence, 10)
    assert.equal(calls.some(params => params.trigger === 'resume'), false)
    mode = 'settings'
    const settingsCalls = calls.length
    await watch.refreshSponsorPromo('settings')
    assert.equal(watch.readSponsorPromo().sequence, 11)
    assert.ok(calls.slice(settingsCalls).filter(params => params.wait).length >= 2)
    assert.equal(calls.slice(settingsCalls).some(params => params.trigger === 'resume'), true)
    mode = 'interval'
    const intervalCalls = calls.length
    await watch.refreshSponsorPromo('interval')
    assert.equal(watch.readSponsorPromo().sequence, 12)
    assert.ok(calls.slice(intervalCalls).filter(params => params.wait).length >= 2)
    assert.equal(calls.slice(intervalCalls).some(params => params.trigger === 'resume'), true)
    assert.equal(JSON.stringify(saved), before)
    assert.equal(JSON.stringify(watch.readSponsorPromo()).includes('fixture-key'), false)
    assert.equal(JSON.stringify(watch.readSponsorPromo()).includes('api.88api.ai'), false)
  } finally {
    stop()
  }
})

test('a pending settings read stops when the watch host is gone', async () => {
  let calls = 0
  const api = {
    async get(_url, opts) {
      calls += 1
      const trigger = opts.params && opts.params.trigger
      if (trigger === 'startup') {
        return { data: view({ pending: false, sequence: 10, revision: 2, source: 'cache' }) }
      }
      return { data: view({ pending: true, sequence: 10, revision: 2, source: 'cache' }) }
    },
  }
  const watch = loadWatch(api)
  const stop = watch.startSponsorPromoWatch()
  await untilSequence(watch, 10)
  const pending = watch.refreshSponsorPromo('settings')
  const started = Date.now()
  while (calls < 4 && Date.now() - started < 2000) {
    await new Promise(resolve => setTimeout(resolve, 20))
  }
  assert.ok(calls >= 4)
  stop()
  await pending
  const after = calls
  await new Promise(resolve => setTimeout(resolve, 700))
  assert.ok(calls - after < 3, `kept reading after dispose: ${calls - after}`)
  assert.equal(watch.readSponsorPromo().sequence, 10)
})

test('a restarted publisher accepts a higher sequence with a lower revision and rejects an older one', async () => {
  const saved = { provider: 'apimart', api_key: 'entered-key' }
  const before = JSON.stringify(saved)
  const script = [
    { pending: false, revision: 5, sequence: 10, instance: 'proc-a', source: 'cache' },
    { pending: false, revision: 1, sequence: 11, instance: 'proc-b', source: 'cache', default: 'api88', choices: ['api88', 'apimart', 'other'] },
    { pending: false, revision: 8, sequence: 9, instance: 'proc-b', source: 'cache', default: 'apimart' },
    { pending: false, revision: 0, sequence: 11, instance: 'proc-b', source: 'cache', default: 'apimart' },
    { choices: ['evil', 'other'], default: 'other', pending: false, revision: 9, sequence: 12, instance: 'proc-b', source: 'cache' },
  ]
  let index = 0
  const api = {
    get() {
      const body = script[Math.min(index, script.length - 1)]
      index += 1
      return Promise.resolve({ data: view(body) })
    },
  }
  const watch = loadWatch(api)
  const stop = watch.startSponsorPromoWatch()
  try {
    await untilSequence(watch, 10)
    assert.equal(watch.readSponsorPromo().instance, 'proc-a')
    await watch.refreshSponsorPromo('settings')
    assert.equal(watch.readSponsorPromo().sequence, 11)
    assert.equal(watch.readSponsorPromo().revision, 1)
    assert.equal(watch.readSponsorPromo().instance, 'proc-b')
    assert.equal(watch.readSponsorPromo().defaultChoice, 'api88')
    await watch.refreshSponsorPromo('interval')
    assert.equal(watch.readSponsorPromo().sequence, 11)
    assert.equal(watch.readSponsorPromo().defaultChoice, 'api88')
    await watch.refreshSponsorPromo('settings')
    assert.equal(watch.readSponsorPromo().sequence, 11)
    assert.equal(watch.readSponsorPromo().defaultChoice, 'api88')
    assert.equal(watch.readSponsorPromo().instance, 'proc-b')
    await watch.refreshSponsorPromo('interval')
    assert.equal(watch.readSponsorPromo().sequence, 11)
    assert.equal(watch.readSponsorPromo().defaultChoice, 'api88')
    assert.equal(JSON.stringify(saved), before)
  } finally {
    stop()
  }
})

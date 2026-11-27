const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

const i18n = { t: text => text }
const promo = loadTs('sponsorPromo.ts', {
  '../../i18n': i18n,
  '../../services/api': { default: { get: () => Promise.resolve({ data: null }) } },
  './providers': loadTs('providers.ts', { '../../i18n': i18n }),
})

const profile = {
  saved: true,
  connections: [{ provider: 'api88', base_url: 'https://api.88api.ai/v1', api_key: 'fixture-key' }],
  analysis: { model: 'qwen3.8-flash' },
}

test('a promotion view reorders new users and keeps an existing profile object untouched', () => {
  const before = JSON.stringify(profile)
  const applied = promo.applySponsorPromo({
    choices: ['api88', 'apimart', 'other'],
    default: 'api88',
    statuses: { api88: 'healthy', apimart: 'fault' },
    notices: { apimart: { zh: '暂时不稳定', en: 'Degraded' } },
    register_urls: { api88: 'https://88api.ai/sign-up?aff=kept' },
  })
  assert.equal(JSON.stringify(applied.choices), JSON.stringify(['api88', 'apimart', 'other']))
  assert.equal(applied.defaultChoice, 'api88')
  assert.equal(applied.notices.apimart.en, 'Degraded')
  assert.equal(applied.notices.apimart.zh, '暂时不稳定')
  assert.equal(promo.noticeText(applied.notices.apimart, 'en'), 'Degraded')
  assert.equal(promo.noticeText(applied.notices.apimart, 'ja'), 'Degraded')
  assert.equal(promo.noticeText({ zh: '仅中文' }, 'ja'), '仅中文')
  assert.equal(applied.registerUrls.api88, 'https://88api.ai/sign-up?aff=kept')
  assert.equal(applied.registerUrls.apimart, undefined)
  assert.equal(applied.statuses.api88, 'healthy')
  assert.equal(JSON.stringify(profile), before)
  assert.equal(promo.applySponsorPromo({
    choices: ['api88', 'other'], default: 'api88',
    register_urls: { api88: 'https://go.apimart.ai/tw-autoclip' },
  }), null)
  assert.equal(promo.applySponsorPromo({
    choices: ['api88', 'other'], default: 'api88',
    register_urls: { api88: 'https://api.88api.ai/sign-up' },
  }), null)
})

test('out of service, deleted ids, bad hosts and unsigned shapes are ignored', () => {
  assert.equal(promo.applySponsorPromo({ choices: ['apimart', 'other'], default: 'apimart', statuses: { apimart: 'out_of_service' } }), null)
  assert.equal(promo.applySponsorPromo({ choices: ['evil', 'other'], default: 'other' }), null)
  assert.equal(promo.applySponsorPromo({ choices: ['apimart', 'other'], default: 'apimart', register_urls: { apimart: 'https://evil.example/key' } }), null)
  assert.equal(promo.applySponsorPromo({ choices: ['apimart'], default: 'apimart' }), null)
  const bundled = promo.bundledSponsorPromo()
  assert.equal(JSON.stringify(bundled.choices), JSON.stringify(['apimart', 'other']))
  assert.equal(bundled.defaultChoice, 'apimart')
  assert.equal(bundled.choices.includes('infistar'), false)
  assert.equal(bundled.choices.includes('api88'), false)
})

test('a saved Infistar connection can show a fault notice without a promotion link', () => {
  const before = JSON.stringify(profile)
  const applied = promo.applySponsorPromo({
    choices: ['infistar', 'apimart', 'other'],
    default: 'infistar',
    statuses: { infistar: 'fault', apimart: 'healthy' },
    notices: { infistar: { zh: '当前不稳定' } },
    register_urls: { infistar: 'https://www.infistar.cc/register?aff=1' },
  })
  assert.equal(JSON.stringify(applied.choices), JSON.stringify(['infistar', 'apimart', 'other']))
  assert.equal(applied.defaultChoice, 'infistar')
  assert.equal(applied.registerUrls.infistar, 'https://www.infistar.cc/register?aff=1')
  const notice = promo.providerServiceNotice(applied, 'infistar')
  assert.equal(notice.status, 'fault')
  assert.equal(notice.text, '当前不稳定')
  assert.equal(promo.providerServiceNotice(applied, 'apimart'), null)
  assert.equal(JSON.stringify(profile), before)
})

test('startup, settings open and the idle interval are wired, and the notice does not rewrite a provider', () => {
  const app = fs.readFileSync(path.join(__dirname, '../src/App.tsx'), 'utf8')
  const settings = fs.readFileSync(path.join(__dirname, '../src/features/settings/AIModelSettings.tsx'), 'utf8')
  const watch = fs.readFileSync(path.join(__dirname, '../src/features/settings/sponsorPromoWatch.ts'), 'utf8')
  assert.match(app, /startSponsorPromoWatch\(/)
  assert.match(app, /refreshSponsorPromo\('settings'\)/)
  assert.match(watch, /refreshSponsorPromo\(trigger, ticket\)/)
  assert.match(watch, /'startup' \| 'resume'/)
  assert.match(watch, /refreshSponsorPromo\('interval'/)
  assert.match(settings, /data-provider-service-notice/)
  assert.match(settings, /已保存的接口和密钥保持不变/)
  const setup = fs.readFileSync(path.join(__dirname, '../src/features/settings/FirstRunSetup.tsx'), 'utf8')
  const primary = setup.slice(setup.indexOf('const primary'), setup.indexOf('const main'))
  assert.ok(primary.indexOf('frozen.current = true') < primary.indexOf('chooseProvider'))
  assert.match(primary, /promotionRegisterUrl\(sponsor, packaged\)/)
  assert.equal(primary.includes('registerUrls[sponsor]'), false)
  assert.match(setup, /promotionRecommends\(id\) && <span className="ac-badge">\{t\('推荐'\)\}<\/span>/)
  assert.match(setup, /choicesFor\(nextChoices, choiceRef\.current, locked\)/)
  assert.match(settings, /enabledUsageNotices/)
  const switched = promo.enabledUsageNotices([
    { provider: 'apimart', label: 'analysis' },
    { provider: 'api88', label: 'vision' },
    { provider: 'api88', label: 'cover' },
    { provider: 'api88', label: 'cover' },
    { provider: 'deepseek', label: 'transcription' },
  ], promo.applySponsorPromo({
    choices: ['apimart', 'other'],
    default: 'apimart',
    statuses: { apimart: 'healthy', api88: 'out_of_service' },
    notices: { api88: { en: 'Stopped', ja: '停止', zh: '暂停' } },
  }), 'ja')
  assert.equal(switched.length, 2)
  assert.equal(switched[0].label, 'vision')
  assert.equal(switched[1].label, 'cover')
  assert.equal(switched[0].text, '停止')
  assert.equal(promo.enabledUsageNotices(switched, promo.applySponsorPromo({
    choices: ['apimart', 'other'], default: 'apimart', statuses: { api88: 'out_of_service' },
    notices: { api88: { en: 'Stopped', ja: '停止', zh: '暂停' } },
  }), 'en')[0].text, 'Stopped')
})

test('by_locale slices are validated against trusted hosts and out_of_service rules', () => {
  const applied = promo.applySponsorPromo({
    choices: ['apimart', 'api88', 'other'],
    default: 'apimart',
    statuses: { apimart: 'healthy', api88: 'healthy' },
    register_urls: { apimart: 'https://go.apimart.ai/cn', api88: 'https://88api.ai/sign-up?aff=global' },
    by_locale: {
      zh: { choices: ['apimart', 'other'], default: 'apimart', register_urls: { apimart: 'https://go.apimart.ai/cn' } },
      en: { choices: ['api88', 'other'], default: 'api88', register_urls: { api88: 'https://88api.ai/sign-up?aff=global' } },
      ja: { choices: ['other'], default: 'other', register_urls: {} },
    },
  })
  assert.equal(JSON.stringify(applied.byLocale.zh.choices), JSON.stringify(['apimart', 'other']))
  assert.equal(applied.byLocale.zh.registerUrls.apimart, 'https://go.apimart.ai/cn')
  assert.equal(JSON.stringify(applied.byLocale.en.choices), JSON.stringify(['api88', 'other']))
  assert.equal(applied.byLocale.en.defaultChoice, 'api88')
  assert.equal(JSON.stringify(applied.byLocale.ja.choices), JSON.stringify(['other']))

  assert.equal(promo.applySponsorPromo({
    choices: ['apimart', 'other'],
    default: 'apimart',
    by_locale: {
      en: { choices: ['apimart', 'other'], default: 'apimart', register_urls: { apimart: 'https://evil.example/steal' } },
    },
  }), null)

  assert.equal(promo.applySponsorPromo({
    choices: ['other'],
    default: 'other',
    statuses: { apimart: 'out_of_service' },
    by_locale: {
      zh: { choices: ['apimart', 'other'], default: 'apimart', register_urls: {} },
    },
  }), null)

  // 19-locale expansion (nl, it, ar, etc.) is supported; unknown valid ISO codes (sv) are ignored gracefully;
  // malformed locale keys are still rejected.
  const expanded = promo.applySponsorPromo({
    choices: ['other'],
    default: 'other',
    by_locale: {
      nl: { choices: ['other'], default: 'other', register_urls: {} },
      ar: { choices: ['apimart', 'other'], default: 'apimart', register_urls: {} },
      sv: { choices: ['other'], default: 'other', register_urls: {} },
    },
  })
  assert.ok(expanded)
  assert.equal(JSON.stringify(expanded.byLocale.nl.choices), JSON.stringify(['other']))
  assert.equal(JSON.stringify(expanded.byLocale.ar.choices), JSON.stringify(['apimart', 'other']))
  assert.equal(expanded.byLocale.sv, undefined)

  assert.equal(promo.applySponsorPromo({
    choices: ['other'],
    default: 'other',
    by_locale: {
      '../zh': { choices: ['other'], default: 'other', register_urls: {} },
    },
  }), null)

  // Invalid host inside a future ISO locale slice is still rejected
  assert.equal(promo.applySponsorPromo({
    choices: ['apimart', 'other'],
    default: 'apimart',
    by_locale: {
      sv: { choices: ['apimart', 'other'], default: 'apimart', register_urls: { apimart: 'https://evil.example/steal' } },
    },
  }), null)
})

test('v2 dynamic providers validate strictly, appear in catalog, and persist as compatible', () => {
  const dynProvider = {
    id: 'cloudgw',
    name: { zh: '云网关', en: 'CloudGW' },
    base_url: 'https://router.cloudgw.example/api/v1',
    register_url: 'https://www.cloudgw.example/?from=AutoClip',
    docs_url: 'https://console.cloudgw.example/keys',
    hint: { zh: '测试云网关。', en: 'Test cloud gateway.' },
    offer: { zh: '送5元', en: '$5 credit' },
    icon_url: 'https://cdn.cloudgw.example/icon.png',
    capabilities: ['language', 'image', 'video'],
    candidates: { analysis: ['gpt-5-mini'], vision: ['gpt-5-mini'] },
    group: 'popular',
  }
  const applied = promo.applySponsorPromo({
    choices: ['cloudgw', 'apimart', 'other'],
    default: 'cloudgw',
    statuses: { cloudgw: 'healthy', apimart: 'healthy' },
    register_urls: { cloudgw: 'https://www.cloudgw.example/?from=AutoClip' },
    providers: [dynProvider],
  })
  assert.ok(applied)
  assert.equal(applied.defaultChoice, 'cloudgw')
  assert.equal(applied.registerUrls.cloudgw, 'https://www.cloudgw.example/?from=AutoClip')
  assert.equal(applied.providers.length, 1)
  assert.equal(applied.providers[0].id, 'cloudgw')
  assert.equal(applied.providers[0].baseUrl, 'https://router.cloudgw.example/api/v1')

  // Reject built-in shadowing, non-HTTPS/IP base_url, and mismatched register host
  assert.equal(promo.applySponsorPromo({
    choices: ['openai', 'other'],
    default: 'openai',
    providers: [{ ...dynProvider, id: 'openai' }],
  }), null)
  assert.equal(promo.applySponsorPromo({
    choices: ['cloudgw', 'other'],
    default: 'cloudgw',
    providers: [{ ...dynProvider, base_url: 'http://router.cloudgw.example/api/v1' }],
  }), null)
  assert.equal(promo.applySponsorPromo({
    choices: ['cloudgw', 'other'],
    default: 'cloudgw',
    providers: [{ ...dynProvider, base_url: 'https://127.0.0.1/v1' }],
  }), null)
  assert.equal(promo.applySponsorPromo({
    choices: ['cloudgw', 'other'],
    default: 'cloudgw',
    register_urls: { cloudgw: 'https://evil.example/?from=AutoClip' },
    providers: [dynProvider],
  }), null)

  // Verify catalog integration and persistence as standard "compatible" connection
  const state = loadTs('sponsorPromoState.ts')
  const presetsMod = loadTs('providerPresets.ts', { './sponsorPromoState': state })
  const catalogView = loadTs('providerCatalogView.ts', {
    '../../i18n': i18n,
    './providerPresets': presetsMod,
    './sponsorPromoState': state,
  })
  const providersMod = loadTs('providers.ts', {
    '../../i18n': i18n,
    './providerPresets': presetsMod,
    './sponsorPromoState': state,
  })
  state.writePromoSnapshot({
    source: 'cache',
    choices: applied.choices,
    defaultChoice: applied.defaultChoice,
    statuses: applied.statuses,
    notices: applied.notices,
    registerUrls: applied.registerUrls,
    providers: applied.providers,
  })
  assert.equal(state.promotionRegisterUrl('cloudgw', ''), 'https://www.cloudgw.example/?from=AutoClip')
  const preset = presetsMod.getProvider('cloudgw')
  assert.ok(preset)
  assert.equal(preset.dynamic, true)
  assert.equal(preset.base_url, 'https://router.cloudgw.example/api/v1')
  assert.equal(preset.icon_url, 'https://cdn.cloudgw.example/icon.png')
  assert.equal(catalogView.catalogProviders().some(row => row.id === 'cloudgw'), true)
  assert.equal(providersMod.recommendedSetupProviders().includes('cloudgw'), true)
  const created = catalogView.ensureCatalogConnection({
    version: 1, saved: false, connections: [],
    analysis: null, vision: null, cover: null,
    transcription: { provider: 'whisper_local', model: 'base' },
    cover_enabled: false, allow_send_frame: true, analysis_mode: 'auto', allow_visual_screening: true,
    chunk_size: 5000, min_score_threshold: .7, max_clips_per_collection: 5,
  }, preset, undefined, () => 'conn-dyn')
  assert.equal(created.changed, true)
  assert.equal(created.connection.provider, 'compatible')
  assert.equal(created.connection.base_url, 'https://router.cloudgw.example/api/v1')
  assert.equal(catalogView.matchedCatalogPreset(created.connection).id, 'cloudgw')
  assert.equal(catalogView.findCatalogConnection(created.settings, preset).id, 'conn-dyn')
})

test('v2 dynamic providers hot-update through sponsorPromoWatch (create, update, delete) without breaking saved connections', async () => {
  const state = loadTs('sponsorPromoState.ts')
  const promoMod = loadTs('sponsorPromo.ts', {
    './sponsorPromoState': state,
    './providers': { PROVIDERS: { apimart: { sponsor: { registerUrl: 'https://go.apimart.ai/demo' } } } },
  })
  const presetsMod = loadTs('providerPresets.ts', { './sponsorPromoState': state })
  const catalogView = loadTs('providerCatalogView.ts', {
    '../../i18n': i18n,
    './providerPresets': presetsMod,
    './sponsorPromoState': state,
  })
  const providersMod = loadTs('providers.ts', {
    '../../i18n': i18n,
    './providerPresets': presetsMod,
    './sponsorPromoState': state,
  })

  const dynV1 = {
    id: 'cloudgw',
    name: { zh: '云网关', en: 'CloudGW' },
    base_url: 'https://router.cloudgw.example/api/v1',
    register_url: 'https://www.cloudgw.example/?from=AutoClip',
    docs_url: 'https://console.cloudgw.example/keys',
    hint: { zh: '初始说明', en: 'Initial hint' },
    capabilities: ['language'],
    candidates: { analysis: ['gpt-5-mini'] },
    group: 'popular',
  }
  const payloads = [
    // Create (seq 10)
    {
      sequence: 10, revision: 1, instance: 'inst-1', pending: false, source: 'cache',
      choices: ['cloudgw', 'apimart', 'other'], default: 'cloudgw',
      statuses: { cloudgw: 'healthy', apimart: 'healthy' },
      register_urls: { cloudgw: 'https://www.cloudgw.example/?from=AutoClip' },
      providers: [dynV1],
    },
    // Update (seq 11)
    {
      sequence: 11, revision: 2, instance: 'inst-1', pending: false, source: 'cache',
      choices: ['cloudgw', 'apimart', 'other'], default: 'cloudgw',
      statuses: { cloudgw: 'healthy', apimart: 'healthy' },
      register_urls: { cloudgw: 'https://www.cloudgw.example/?from=AutoClip' },
      providers: [{ ...dynV1, name: { zh: '云网关 Pro', en: 'CloudGW Pro' }, hint: { zh: '更新说明', en: 'Updated hint' } }],
    },
    // Delete (seq 12)
    {
      sequence: 12, revision: 3, instance: 'inst-1', pending: false, source: 'cache',
      choices: ['apimart', 'other'], default: 'apimart',
      statuses: { apimart: 'healthy' },
      register_urls: {},
    },
  ]
  let idx = 0
  const watch = loadTs('sponsorPromoWatch.ts', {
    './sponsorPromo': {
      ...promoMod,
      loadSponsorPromo: async () => promoMod.applySponsorPromo(payloads[idx++]),
    },
    './sponsorPromoState': state,
  })

  let notifications = 0
  const unsub = state.subscribePromoSnapshot(() => { notifications += 1 })

  // 1. Create
  await watch.refreshSponsorPromo('settings')
  assert.equal(notifications, 1)
  assert.equal(presetsMod.getProvider('cloudgw', 'en').display_name, 'CloudGW')
  assert.equal(catalogView.catalogProviders().some(row => row.id === 'cloudgw'), true)
  assert.equal(providersMod.recommendedSetupProviders().includes('cloudgw'), true)

  // Save a user connection while cloudgw exists
  const saved = catalogView.ensureCatalogConnection({
    version: 1, saved: false, connections: [],
    analysis: null, vision: null, cover: null,
    transcription: { provider: 'whisper_local', model: 'base' },
    cover_enabled: false, allow_send_frame: true, analysis_mode: 'auto', allow_visual_screening: true,
    chunk_size: 5000, min_score_threshold: .7, max_clips_per_collection: 5,
  }, presetsMod.getProvider('cloudgw', 'en'), undefined, () => 'conn-saved')

  // 2. Update (hot-reload without restart)
  await watch.refreshSponsorPromo('settings')
  assert.equal(notifications, 2)
  assert.equal(presetsMod.getProvider('cloudgw', 'en').display_name, 'CloudGW Pro')
  assert.equal(presetsMod.getProvider('cloudgw', 'zh').hint, '更新说明')

  // 3. Delete (hot-reload without restart) — catalog removes it, saved user connection stays intact as compatible
  await watch.refreshSponsorPromo('settings')
  assert.equal(notifications, 3)
  assert.equal(presetsMod.getProvider('cloudgw'), undefined)
  assert.equal(catalogView.catalogProviders().some(row => row.id === 'cloudgw'), false)
  assert.equal(providersMod.recommendedSetupProviders().includes('cloudgw'), false)
  assert.equal(saved.connection.provider, 'compatible')
  assert.equal(saved.connection.base_url, 'https://router.cloudgw.example/api/v1')
  assert.equal(catalogView.isUnmatchedCompatible(saved.connection), true)
  unsub()
})

test('cloud-configurable sponsor badges parse cleanly and reject unsafe strings', () => {
  const applied = promo.applySponsorPromo({
    choices: ['apimart', 'cometapi', 'other'],
    default: 'apimart',
    statuses: { apimart: 'healthy', cometapi: 'healthy' },
    badges: {
      apimart: '',
      cometapi: { zh: '赞助', en: 'Sponsor', sv: 'Sponsor SV' },
    },
  })
  assert.ok(applied)
  assert.equal(applied.badges.apimart, '')
  assert.equal(applied.badges.cometapi.zh, '赞助')
  assert.equal(applied.badges.cometapi.en, 'Sponsor')
  assert.equal(applied.badges.cometapi.sv, undefined)

  assert.equal(promo.applySponsorPromo({
    choices: ['apimart', 'other'],
    default: 'apimart',
    badges: { apimart: '<script>bad</script>' },
  }), null)
  assert.equal(promo.applySponsorPromo({
    choices: ['apimart', 'other'],
    default: 'apimart',
    badges: { apimart: 'https://evil.example' },
  }), null)
})

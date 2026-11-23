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

  assert.equal(promo.applySponsorPromo({
    choices: ['other'],
    default: 'other',
    by_locale: {
      nl: { choices: ['other'], default: 'other', register_urls: {} },
    },
  }), null)
})

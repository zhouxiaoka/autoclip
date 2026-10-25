const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

const guide = loadTs('keyGuide.ts')

const SPONSORS = ['api88', 'infistar', 'apimart']
const TARGETS = [
  { id: 'openai', hosts: ['api.openai.com'] },
  { id: 'gemini', hosts: ['generativelanguage.googleapis.com'] },
  { id: 'grok', hosts: ['api.x.ai'] },
  { id: 'openrouter', hosts: ['openrouter.ai'] },
  { id: 'dashscope', hosts: ['dashscope.aliyuncs.com'] },
  { id: 'deepseek', hosts: ['api.deepseek.com'] },
  { id: 'api88', hosts: ['api.88api.ai', '88api.ai'] },
  { id: 'infistar', hosts: ['infistar.cc', 'www.infistar.cc'] },
  { id: 'apimart', hosts: ['api.apimart.ai'] },
]

const GENERIC = 'sk-abCDefghijklmnopqrstuvwx'
const OPENAI = 'sk-proj-abcdefghijklmnopqrstuvwxyz'
const GEMINI = 'AIzaSyA1234567890abcdefghijklmnop'
const OR = 'sk-or-v1-abcdefghijklmnopqrstuvwxyz'

test('prefixes land on one provider and a generic sk- does not pick a sponsor', () => {
  assert.equal(guide.prefixProviderId(OPENAI), 'openai')
  assert.equal(guide.prefixProviderId('sk-svcacct-abcdefghijklmnopqrstuvwxyz'), 'openai')
  assert.equal(guide.prefixProviderId(GEMINI), 'gemini')
  assert.equal(guide.prefixProviderId('xai-abcdefghijklmnopqrstuvwxyz'), 'grok')
  assert.equal(guide.prefixProviderId(OR), 'openrouter')
  assert.equal(guide.prefixProviderId(GENERIC), null)
  assert.equal(guide.prefixProviderId('sk-88api' + 'a'.repeat(24)), null)
  const routed = guide.routeKey(GENERIC, '', TARGETS)
  assert.equal(routed.providerId, null)
  assert.equal(routed.conflict, false)
  for (const id of SPONSORS) assert.notEqual(routed.providerId, id)
})

test('extraction keeps one key and rejects urls, sentences, and short tokens', () => {
  assert.equal(guide.extractApiKey(`api_key: ${GENERIC}`), GENERIC)
  assert.equal(guide.extractApiKey(`{"token":"${GENERIC}"}`), GENERIC)
  assert.equal(guide.extractApiKey(`Bearer ${OPENAI}`), OPENAI)
  assert.equal(guide.extractApiKey('密钥：' + GEMINI), GEMINI)
  assert.equal(guide.extractApiKey('https://example.com/' + GENERIC), null)
  assert.equal(guide.extractApiKey('please paste the key from the dashboard'), null)
  assert.equal(guide.extractApiKey('dQw4w9WgXcQ'), null)
  assert.equal(guide.extractApiKey('person@example.com'), null)
  assert.equal(guide.extractApiKey('sk-generic-88api'), null)
  assert.equal(guide.extractApiKey('a'.repeat(32)), null)
  assert.equal(guide.extractApiKey('123e4567-e89b-12d3-a456-426614174000'), null)
  assert.equal(guide.extractApiKey(`${GENERIC} ${OPENAI}`), null)
  assert.equal(guide.looksLikeApiKey('autoclip://import?key=' + GENERIC), false)
})

test('autoclip links keep the key out of the path and reject other schemes', () => {
  const link = guide.parseAutoclipLink(`autoclip://import?key=${GENERIC}&base_url=https://gw.example/v1/chat/completions`)
  assert.equal(link.key, GENERIC)
  assert.equal(link.baseUrl, 'https://gw.example/v1')
  assert.equal(link.providerId, null)
  assert.equal(guide.parseAutoclipLink('http://example.com/?key=' + GENERIC), null)
  assert.equal(guide.parseAutoclipLink(`autoclip://user:secret@import?key=${GENERIC}`), null)
  assert.equal(guide.parseAutoclipLink('autoclip://import?key=short'), null)
  assert.equal(guide.normalizeGuideBaseUrl('https://user:pass@gw.example/v1'), '')
  assert.equal(guide.normalizeGuideBaseUrl('https://api.deepseek.com'), 'https://api.deepseek.com/v1')
})

test('host match wins, prefix disagreement and an explicit mismatch are conflicts', () => {
  const dash = guide.inferProviderId(GENERIC, 'https://dashscope.aliyuncs.com/compatible-mode/v1', TARGETS)
  assert.equal(dash.providerId, 'dashscope')
  assert.equal(dash.conflict, false)
  const openai = guide.inferProviderId(OPENAI, 'https://api.openai.com/v1', TARGETS)
  assert.equal(openai.providerId, 'openai')
  assert.equal(openai.conflict, false)
  const unknown = guide.inferProviderId(GENERIC, 'https://gw.example/v1', TARGETS)
  assert.equal(unknown.providerId, null)
  assert.equal(unknown.conflict, false)
  const clash = guide.inferProviderId(GEMINI, 'https://dashscope.aliyuncs.com/compatible-mode/v1', TARGETS)
  assert.equal(clash.providerId, null)
  assert.equal(clash.conflict, true)
  const named = guide.routeKey(GENERIC, '', TARGETS, 'api88')
  assert.equal(named.providerId, 'api88')
  assert.equal(named.conflict, false)
  const namedClash = guide.routeKey(GENERIC, 'https://dashscope.aliyuncs.com/compatible-mode/v1', TARGETS, 'api88')
  assert.equal(namedClash.providerId, null)
  assert.equal(namedClash.conflict, true)
  assert.equal(guide.routeKey(GENERIC, '', [{ id: 'other', hosts: [] }], 'nope').providerId, null)
})

test('overwrite is required for a saved or masked key and placement stops without confirmation', () => {
  const masked = { id: 'c1', providerId: 'dashscope', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', hasKey: true }
  assert.equal(guide.needsOverwrite(masked, GENERIC), true)
  assert.equal(guide.needsOverwrite({ ...masked, apiKey: GENERIC, hasKey: true }, GENERIC), false)
  assert.equal(guide.needsOverwrite({ ...masked, apiKey: '', hasKey: false }, GENERIC), false)
  const blocked = guide.planPlacement({
    endpoints: [masked], providerId: 'dashscope', apiKey: GENERIC, overwrite: false, officialBaseUrl: masked.baseUrl,
  })
  assert.equal(blocked.action, 'blocked')
  const update = guide.planPlacement({
    endpoints: [masked], providerId: 'dashscope', apiKey: GENERIC, overwrite: true, officialBaseUrl: masked.baseUrl,
  })
  assert.equal(update.action, 'update')
  assert.equal(update.apiKey, GENERIC)
  assert.equal(update.baseUrl, undefined)
  const same = guide.planPlacement({
    endpoints: [{ ...masked, apiKey: GENERIC }], providerId: 'dashscope', apiKey: GENERIC, overwrite: false, officialBaseUrl: masked.baseUrl,
  })
  assert.equal(same.action, 'unchanged')
  const created = guide.planPlacement({
    endpoints: [], providerId: guide.CUSTOM_PROVIDER_ID, apiKey: GENERIC, baseUrl: 'https://gw.example/chat/completions', overwrite: false,
  })
  assert.equal(created.action, 'create')
  assert.equal(created.custom, true)
  assert.equal(created.baseUrl, 'https://gw.example/v1')
  assert.equal(created.providerId, 'compatible')
})

test('the dialog tail is four characters and save toasts distinguish a bad key', () => {
  assert.equal(guide.keyTail(GENERIC), GENERIC.slice(-4))
  assert.notEqual(guide.keyTail(GENERIC), GENERIC)
  assert.equal(guide.keyTail('short'), '')
  const invalid = guide.saveToast([{ status: 'failed', errorType: 'invalid_key' }])
  assert.equal(invalid.kind, 'invalid')
  assert.equal(invalid.errorType, 'invalid_key')
  assert.equal(guide.saveToast([{ status: 'failed', errorType: 'permission_denied' }]).kind, 'invalid')
  assert.equal(guide.saveToast([{ status: 'failed', errorType: 'insufficient_quota' }]).kind, 'invalid')
  assert.equal(guide.saveToast([{ status: 'failed', errorType: 'unknown' }]).kind, 'failed')
  assert.equal(guide.saveToast([{ status: 'transient', errorType: 'timeout' }]).kind, 'unverified')
  assert.equal(guide.saveToast([{ status: 'ok' }]).kind, 'saved')
  assert.equal(guide.pasteShouldMove(GEMINI, 'openai', TARGETS), true)
  assert.equal(guide.pasteShouldMove(OPENAI, 'openai', TARGETS), false)
  assert.equal(guide.pasteShouldMove(GENERIC, 'openai', TARGETS), false)
})

test('a pasted prefix for another provider is offered without storing the key', () => {
  const offers = []
  const pasted = loadTs('keyGuideWatch.ts', {
    '../../utils/desktopMode': { isDesktopMode: async () => false },
    './keyGuideBus': { publishOffer: offer => offers.push(offer) },
  })
  pasted.setKeyGuideTargets(TARGETS)
  assert.equal(pasted.offerPastedKey(GEMINI, 'openai'), true)
  assert.equal(offers.length, 1)
  assert.equal(offers[0].source, 'paste')
  assert.equal(offers[0].hintedProviderId, 'gemini')
  assert.equal(offers[0].key, GEMINI)
  assert.equal(pasted.offerPastedKey(GENERIC, 'dashscope'), false)
  assert.equal(offers.length, 1)
})

test('invalid-key saves still persist and the success toast is not the invalid path', () => {
  const hook = fs.readFileSync(path.join(__dirname, '../src/features/settings/useModelSettings.ts'), 'utf8')
  const saveAt = hook.indexOf('const value = await modelSettingsApi.save')
  const toastAt = hook.indexOf("toast.kind === 'invalid'")
  assert.ok(saveAt > 0 && toastAt > saveAt)
  assert.match(hook, /settings\.key_guide\.invalid_saved/)
  assert.ok(hook.includes('if (!failed && !visionFailed) notifySettingsSaved()'))
  assert.equal((hook.match(/telemetryProvider\(/g) || []).length, 5)
  assert.equal(/console\.(log|debug|info|warn|error)\([^)]*apiKey/.test(hook), false)
})

test('key-guide strings exist in all eight locales', () => {
  const keys = [
    'settings.key_guide.clipboard', 'settings.key_guide.deeplink', 'settings.key_guide.paste',
    'settings.key_guide.fill', 'settings.key_guide.ignore', 'settings.key_guide.replace',
    'settings.key_guide.keep', 'settings.key_guide.pick', 'settings.key_guide.pick_required',
    'settings.key_guide.custom', 'settings.key_guide.endpoint', 'settings.key_guide.detect',
    'settings.key_guide.none', 'settings.key_guide.invalid_saved', 'settings.key_guide.unverified',
    'settings.key_guide.masked', 'settings.key_guide.title', 'settings.key_guide.conflict',
  ]
  const locales = ['zh', 'en', 'ja', 'ko', 'es', 'pt', 'ru', 'fr'].map(lang => (
    JSON.parse(fs.readFileSync(path.join(__dirname, `../src/i18n/locales/${lang}.json`), 'utf8'))
  ))
  for (const key of keys) {
    const values = locales.map(locale => locale[key])
    for (const value of values) assert.equal(typeof value, 'string', key)
    for (const value of values) assert.ok(value.trim(), key)
    assert.equal(new Set(values).size > 1, true, key)
  }
  assert.match(locales[1]['settings.key_guide.paste'], /\{\{name\}\}/)
  assert.match(locales[0]['settings.key_guide.masked'], /\{\{tail\}\}/)
})

test('deep link docs keep the New API placeholder line and do not log the key', () => {
  const doc = fs.readFileSync(path.join(__dirname, '../../docs/KEY_GUIDE.md'), 'utf8')
  assert.match(doc, /autoclip:\/\/import\?key=\{key\}&base_url=\{address\}\/v1/)
  assert.match(doc, /不打印/)
  const rust = fs.readFileSync(path.join(__dirname, '../../src-tauri/src/lib.rs'), 'utf8')
  assert.equal(/println!\([^)]*argv/.test(rust), false)
  assert.equal(/eprintln!\([^)]*argv/.test(rust), false)
  assert.match(rust, /deep_link\(\)\.register_all/)
})

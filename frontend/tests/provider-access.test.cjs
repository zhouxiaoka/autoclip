const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

const providers = {
  PROVIDERS: {
    gemini: { name: 'Google Gemini' }, openai: { name: 'OpenAI' }, grok: { name: 'Grok' },
    compatible: { name: '自定义兼容' }, api88: { keyUrl: 'https://88api.ai/sign-up?aff=2PIc' },
    infistar: { keyUrl: 'https://www.infistar.cc/register' }, ollama: { local: { baseUrl: 'http://localhost:11434/v1' } },
  },
}
function loadContract() {
  return loadTs(path.join(__dirname, '../src/analytics/successRateContract.ts'))
}
const contract = loadContract()
const urls = loadTs('providerUrl.ts')
const access = loadTs('providerAccess.ts', {
  '../../i18n': { t: (x, v) => (v && v.name ? x.replace('{{name}}', v.name) : x) },
  './providers': providers,
  '../../analytics/successRateContract': contract,
})

test('compatible URLs gain /v1, drop chat completions, and flag console hosts', () => {
  const missing = access.normalizeCompatibleUrl(' https://gw.example/ ')
  assert.equal(missing.url, 'https://gw.example/v1')
  assert.ok(missing.warnings.includes('missing_v1'))
  const pasted = access.normalizeCompatibleUrl('https://example.com/v1/chat/completions')
  assert.equal(pasted.url, 'https://example.com/v1')
  assert.ok(pasted.warnings.includes('chat_completions'))
  const consoleHost = access.normalizeCompatibleUrl('https://platform.openai.com/api-keys')
  assert.ok(consoleHost.warnings.includes('console_host'))
  assert.equal(consoleHost.url, 'https://platform.openai.com/api-keys')
  // Presets keep an editable「接口地址」(default prefilled); Azure/Cloudflare style empty URLs too.
  assert.ok(access.canEditAddress('api88'))
  assert.ok(access.canEditAddress('openai'))
  assert.ok(access.canEditAddress('dashscope'))
  assert.ok(access.canEditAddress('compatible'))
  assert.ok(access.canEditAddress('ollama'))
  assert.ok(access.canEditAddress('azure-openai'))
  assert.ok(access.canEditAddress('cloudflare-workers-ai'))
  assert.ok(access.canEditAddress('cloudflare-ai-gateway'))
  const source = fs.readFileSync(path.join(__dirname, '../src/features/settings/providerAccess.ts'), 'utf8')
  assert.match(source, /normalizeProviderUrl/)
  assert.doesNotMatch(source, /VERSIONED/)
})

test('validation and settings share Gemini and ordinary chat roots', () => {
  const root = 'https://generativelanguage.googleapis.com'
  for (const [suffix, expected] of [['/v1beta', '/v1beta/openai'], ['/v1beta/openai', '/v1beta/openai'], ['/v1', '/v1']]) {
    assert.equal(access.normalizeCompatibleUrl(root + suffix).url, root + expected)
    assert.equal(access.normalizeCompatibleUrl(root + suffix).url, urls.normalizeProviderBaseUrl(root + suffix))
  }
})

test('wrong-provider keys are hinted, never treated as a switch, and hosts stay sanitized', () => {
  assert.equal(access.hintProviderForKey('  AIzaSyLooksLikeGemini  '), 'gemini')
  assert.equal(access.hintProviderForKey('sk-generic-88api'), null)
  assert.match(access.keyHintCopy('gemini'), /Google Gemini/)
  assert.equal(access.telemetryHost('https://88api.ai/v1/chat/completions?key=secret'), '88api.ai')
  assert.equal(access.telemetryHost('http://127.0.0.1:11434/v1'), 'local')
  assert.equal(access.sponsorKeyLink('api88').href.includes('88api.ai'), true)
  assert.equal(access.validationCopy('insufficient_quota'), contract.UPSTREAM_HINT_KEYS.insufficient_quota)
  assert.equal(
    access.validationCopy('invalid_key', contract.UPSTREAM_HINT_KEYS.bad_endpoint),
    contract.UPSTREAM_HINT_KEYS.bad_endpoint,
  )
  assert.equal(access.passed({ success: false, error_type: 'invalid_key' }), false)
  assert.equal(access.passed({ success: true }), true)
  assert.equal(access.VISION_UNSUPPORTED, 'vision_unsupported')
  assert.match(access.validationCopy('vision_unsupported'), /不能看图/)
})

test('settings URL wrapper shares Gemini chat-root normalization', () => {
  const root = 'https://generativelanguage.googleapis.com/v1beta'
  for (const provider of ['gemini', 'compatible']) {
    const normalized = access.normalizeCompatibleUrl(root, provider)
    assert.equal(normalized.url, root + '/openai')
    const pasted = access.normalizeCompatibleUrl(root + '/chat/completions', provider)
    assert.equal(pasted.url, root + '/openai')
    assert.ok(pasted.warnings.includes('chat_completions'))
  }
})

// Catalog API and legacy hosts take precedence over website/console hints.
test('Infistar API host is accepted and console detection follows the catalog', () => {
  assert.equal(access.isConsoleHost('infistar.ai'), false)
  assert.equal(access.normalizeCompatibleUrl('https://infistar.ai/v1').warnings.includes('console_host'), false)
  const catalogAccess = loadTs('providerAccess.ts', {
    '../../i18n': { t: x => x },
    './providers': providers,
    '../../analytics/successRateContract': contract,
    './providerPresets': { getCatalog: () => ({
      console_hosts: ['platform.deepseek.com', 'aistudio.google.com', 'platform.openai.com', 'console.fixture.test'],
      console_suffixes: ['.console.fixture.test'],
      providers: {
      fixture: { base_url: 'https://platform.deepseek.com/v1', accepted_hosts: ['aistudio.google.com'] },
    } }) },
  })
  assert.equal(catalogAccess.isConsoleHost('platform.deepseek.com'), false)
  assert.equal(catalogAccess.isConsoleHost('aistudio.google.com'), false)
  assert.equal(catalogAccess.isConsoleHost('platform.openai.com'), true)
  assert.equal(catalogAccess.isConsoleHost('console.fixture.test'), true)
  assert.equal(catalogAccess.isConsoleHost('account.console.fixture.test'), true)
  assert.equal(catalogAccess.isConsoleHost('bailian.console.aliyun.com'), false)
})


test('Infistar API is accepted and address locks are projected from the catalog', () => {
  const catalog = JSON.parse(fs.readFileSync(path.join(__dirname, '../../backend/presets/provider_presets.json'), 'utf8'))
  assert.equal(access.isConsoleHost('infistar.ai'), false)
  assert.equal(access.normalizeCompatibleUrl('https://infistar.ai/v1').warnings.length, 0)
  assert.deepEqual(Array.from(access.ADDRESS_LOCKED).sort(), Object.entries(catalog.providers)
    .filter(([, row]) => row.locked && row.base_url).map(([id]) => id).sort())
})

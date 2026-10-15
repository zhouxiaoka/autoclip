const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')
const { loadTs } = require('./load-ts.cjs')

const providers = {
  PROVIDERS: {
    gemini: { name: 'Google Gemini' }, openai: { name: 'OpenAI' }, grok: { name: 'Grok' },
    compatible: { name: '自定义兼容' }, api88: { keyUrl: 'https://88api.ai/sign-up?aff=2PIc' },
    infistar: { keyUrl: 'https://www.infistar.cc/register' }, ollama: { local: { baseUrl: 'http://localhost:11434/v1' } },
  },
}
function loadContract() {
  const source = path.join(__dirname, '../src/analytics/successRateContract.ts')
  const module = { exports: {} }
  vm.runInNewContext(
    ts.transpileModule(fs.readFileSync(source, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText,
    { exports: module.exports, module, URL },
    { filename: source },
  )
  return module.exports
}
const contract = loadContract()
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
  assert.ok(!access.canEditAddress('api88'))
  assert.ok(!access.canEditAddress('openai'))
  assert.ok(!access.canEditAddress('dashscope'))
  assert.ok(access.canEditAddress('compatible'))
  assert.ok(access.canEditAddress('ollama'))
  const source = fs.readFileSync(path.join(__dirname, '../src/features/settings/providerAccess.ts'), 'utf8')
  assert.match(source, /normalizeProviderUrl/)
  assert.doesNotMatch(source, /VERSIONED/)
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

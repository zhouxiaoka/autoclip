// RC156 Win QA #14b: local models need a larger context for long videos; the setup shows how.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), ts = require('typescript')
const React = require('react')
const dir = path.join(__dirname, '../src/features/settings')
function load(file, mocks) {
  const exports = {}
  const code = ts.transpileModule(fs.readFileSync(path.join(dir, file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText
  vm.runInNewContext(code, { exports, URL, require: id => {
    if (id in mocks) return mocks[id]
    if (id === 'react/jsx-runtime') return require(id)
    throw Error(id)
  } })
  return exports
}
const providers = load('providers.ts', { '../../i18n': { t: text => text } })
const flatten = node => !React.isValidElement(node) ? [node] : [node, ...React.Children.toArray(node.props.children).flatMap(flatten)]
const locales = Object.fromEntries(['zh', 'en', 'ja', 'ko', 'es', 'pt', 'ru', 'fr'].map(lang =>
  [lang, JSON.parse(fs.readFileSync(path.join(__dirname, `../src/i18n/locales/${lang}.json`), 'utf8'))]))
const OLLAMA = '长视频请把上下文调到 16384 以上（环境变量 OLLAMA_CONTEXT_LENGTH 或模型参数 num_ctx），否则字幕开头会被截掉。'
const LMSTUDIO = '长视频请在 LM Studio 加载模型时把上下文长度（Context Length）调到 16384 以上，否则会报错或截断字幕。'
const GENERIC = '本机或局域网模型：长视频请把上下文长度调到 16384 以上，否则字幕会被截断。'

test('local presets and local compatible servers get a context hint; cloud providers do not', () => {
  assert.equal(providers.contextHintFor('ollama'), OLLAMA)
  assert.equal(providers.contextHintFor('lmstudio'), LMSTUDIO)
  for (const url of ['http://localhost:8080/v1', 'http://127.0.0.1:8000/v1', 'http://192.168.1.9:8000/v1', 'http://10.0.0.5/v1', 'http://172.20.1.1/v1', 'http://gpu.local:8000/v1'])
    assert.equal(providers.contextHintFor('compatible', url), GENERIC, url)
  for (const url of ['https://openrouter.ai/api/v1', 'http://172.32.0.1/v1', '', 'not a url'])
    assert.equal(providers.contextHintFor('compatible', url), '', url)
  for (const key of ['dashscope', 'openai', 'deepseek', 'kimi', 'infistar', 'api88', 'gemini', 'seed', 'glm', 'grok'])
    assert.equal(providers.contextHintFor(key, 'http://localhost:1234/v1'), '', key)
  assert.equal(providers.contextHintFor(undefined), '')
})

test('the address row shows the hint for local setups only', () => {
  const Fields = load('ProviderFields.tsx', {
    react: { useState: () => [false, () => {}] },
    antd: { Input: Object.assign(() => null, { Password: 'password' }), Select: 'select' },
    '../../i18n': { t: text => text }, '../../ui': { Btn: 'button', Row: 'row' },
    '../../utils/externalLinks': { openExternalLink() {} },
    '../../analytics/events': { trackSponsorLinkOpened() {} },
    './providers': providers, './modelSettingsLogic': { presetKey: c => c.provider },
  }).default
  const hints = connection => flatten(Fields({ connection, placement: 'settings_model', onChoose() {}, onEdit() {} }))
    .filter(node => React.isValidElement(node) && node.type === 'row').map(node => node.props.hint).filter(h => typeof h === 'string')
  assert.ok(hints({ provider: 'ollama', base_url: '' }).some(h => h.includes(OLLAMA) && h.includes('本机服务无需 API Key')))
  assert.ok(hints({ provider: 'lmstudio', base_url: '' }).some(h => h.includes(LMSTUDIO)))
  assert.ok(hints({ provider: 'compatible', base_url: 'http://localhost:8000/v1', api_key: '' }).includes(GENERIC))
  assert.ok(!hints({ provider: 'compatible', base_url: 'https://openrouter.ai/api/v1', api_key: '' }).some(h => h.includes('16384')))
  assert.ok(!hints({ provider: 'dashscope', base_url: '', api_key: '' }).some(h => h.includes('16384')))
})

test('the hints are translated in all 8 locales', () => {
  for (const key of [OLLAMA, LMSTUDIO, GENERIC]) {
    assert.equal(locales.zh[key], key)
    for (const lang of ['en', 'ja', 'ko', 'es', 'pt', 'ru', 'fr']) {
      assert.ok(locales[lang][key] && locales[lang][key] !== key, `${lang}: ${key}`)
      assert.ok(locales[lang][key].includes('16384'), lang)
    }
  }
  assert.ok(locales.en[OLLAMA].includes('OLLAMA_CONTEXT_LENGTH') && locales.en[OLLAMA].includes('num_ctx'))
})

test('backend presets and the frontend show the same sentences', () => {
  const py = fs.readFileSync(path.join(__dirname, '../../backend/core/local_presets.py'), 'utf8')
  for (const key of [OLLAMA, LMSTUDIO, GENERIC]) assert.ok(py.includes(key), key)
})

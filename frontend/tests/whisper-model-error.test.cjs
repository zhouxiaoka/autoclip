// R12 #13: Whisper download failure copy is chosen by errorCode and translated in 8 locales.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path')
const { loadTs } = require('./load-ts.cjs')
const KEY = 'Whisper 模型下载失败。请检查网络后到「设置 → 转写」重新下载，或在下载源中改用 hf-mirror 镜像。'

test('errorCode selects translated copy; unknown code falls back to the server message', () => {
  const { whisperModelErrorText } = loadTs(path.join(__dirname, '../src/utils/whisperModelError.ts'))
  const t = s => `T(${s})`
  assert.equal(whisperModelErrorText(t, { errorCode: 'whisper_download_failed', errorMessage: 'raw' }), `T(${KEY})`)
  assert.equal(whisperModelErrorText(t, { errorCode: null, errorMessage: 'legacy text' }), 'legacy text')
  assert.equal(whisperModelErrorText(t, {}), '')
})

// R13 #24: render the real SpeechRecognitionConfig (not a source regex) in all 8 locales.
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const LANGS = ['zh', 'en', 'es', 'fr', 'ja', 'ko', 'pt', 'ru']
function renderSettings(lang, model) {
  const cat = JSON.parse(fs.readFileSync(path.join(__dirname, `../src/i18n/locales/${lang}.json`), 'utf8'))
  const t = (key, vars) => String(cat[key] || key).replace(/\{\{(\w+)\}\}/g, (_, k) => (vars || {})[k] ?? '')
  const h = React.createElement
  const ui = {
    Row: ({ label, hint, children }) => h('section', null, h('b', null, label), h('i', { className: 'hint' }, hint), children),
    Btn: ({ children }) => h('button', null, children), ProgressLine: () => null, StatusDot: () => null,
  }
  // Seed the component's own state in hook order (runtime, models, loading) — SSR runs no effects.
  const seeded = [{ status: 'installed', platform_supported: true }, [model], false]
  const fakeReact = { ...React, default: undefined, useState: (init) => React.useState(seeded.length ? seeded.shift() : init) }
  fakeReact.default = fakeReact
  const mod = loadTs(path.join(__dirname, '../src/components/SpeechRecognitionConfig.tsx'), {
    react: fakeReact, '../i18n': { t }, '../../i18n': { t }, 'react-i18next': { useTranslation: () => ({ t }) },
    antd: { Select: () => null, Popconfirm: ({ children }) => children, message: { error() {} } },
    '../services/api': { speechApi: {} }, '../ui': ui, '../../ui': ui,
  })
  return { html: renderToStaticMarkup(h(mod.default, { selectedModel: 'base' })), cat }
}

test('SpeechRecognitionConfig renders the errorCode copy translated in all eight locales', () => {
  for (const lang of LANGS) {
    const { html, cat } = renderSettings(lang, { name: 'base', size: '142MB', status: 'error', errorCode: 'whisper_download_failed', errorMessage: 'server raw text' })
    const expected = cat[KEY] || KEY
    const escaped = renderToStaticMarkup(React.createElement('i', null, expected)).slice(3, -4)
    assert.ok(html.includes(escaped), `${lang} must render the translated download-failure copy`)
    assert.ok(!html.includes('server raw text'), lang)
  }
})

test('SpeechRecognitionConfig falls back to the server text for an unknown errorCode', () => {
  for (const lang of LANGS) {
    const { html } = renderSettings(lang, { name: 'base', size: '142MB', status: 'error', errorCode: 'something_new', errorMessage: 'server raw text' })
    assert.ok(html.includes('server raw text'), lang)
  }
})

test('download failure copy exists in all eight locales', () => {
  for (const lang of ['zh', 'en', 'es', 'fr', 'ja', 'ko', 'pt', 'ru']) {
    const cat = JSON.parse(fs.readFileSync(path.join(__dirname, `../src/i18n/locales/${lang}.json`), 'utf8'))
    assert.ok(cat[KEY], lang)
    if (lang !== 'zh') assert.notEqual(cat[KEY], KEY, lang)
  }
})

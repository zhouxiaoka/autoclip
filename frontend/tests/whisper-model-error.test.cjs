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

test('WhisperModel carries optional errorCode and the settings hint displays by code', () => {
  const api = fs.readFileSync(path.join(__dirname, '../src/services/api.ts'), 'utf8')
  assert.match(api, /errorCode\?: 'whisper_download_failed' \| string \| null/)
  const ui = fs.readFileSync(path.join(__dirname, '../src/components/SpeechRecognitionConfig.tsx'), 'utf8')
  assert.match(ui, /selected\?\.status === 'error' && installed \? whisperModelErrorText\(t, selected\)/)
  assert.doesNotMatch(ui, /installed \? selected\.errorMessage/)
})

test('download failure copy exists in all eight locales', () => {
  for (const lang of ['zh', 'en', 'es', 'fr', 'ja', 'ko', 'pt', 'ru']) {
    const cat = JSON.parse(fs.readFileSync(path.join(__dirname, `../src/i18n/locales/${lang}.json`), 'utf8'))
    assert.ok(cat[KEY], lang)
    if (lang !== 'zh') assert.notEqual(cat[KEY], KEY, lang)
  }
})

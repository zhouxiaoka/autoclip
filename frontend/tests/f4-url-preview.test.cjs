const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('path')
const { runInSandbox } = require('./vm-sandbox.cjs')
const ts = require('typescript')

function load(relative, requireImpl) {
  const file = path.join(__dirname, relative)
  const exports = {}
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText
  runInSandbox(code, {
    exports,
    require: requireImpl || ((name) => {
      if (name === '../../i18n') return { t: (s, vars) => vars ? `${s}:${JSON.stringify(vars)}` : s }
      if (name.endsWith('/etaModel') || name === './etaModel') return { estimate: () => ({ etaMin: 12, overrun: false, initialMin: 12, errorRatio: null }) }
      if (name.endsWith('/planningCopy') || name === './planningCopy') return { VISUAL_SOURCE_TOO_LONG_MESSAGE: '画面分析最长支持 120 分钟的素材，已改用字幕分析继续制作。' }
      if (name.endsWith('/importReadiness') || name === './importReadiness') return readiness
      return {}
    }),
  })
  return exports
}

const readiness = load('../src/features/studio/importReadiness.ts', () => ({}))
const paste = load('../src/features/studio/pasteStart.ts', () => ({}))

test('F4: transcriptionRoute prefers preview route over skippedWhisper guess', () => {
  assert.equal(readiness.transcriptionRoute({ hasSubtitle: false, skippedWhisper: true, previewRoute: 'local_transcription' }), 'whisper')
  assert.equal(readiness.transcriptionRoute({ hasSubtitle: false, skippedWhisper: false, previewRoute: 'platform_subtitle' }), 'platform_subs')
  assert.equal(readiness.transcriptionRoute({ hasSubtitle: true, skippedWhisper: false }), 'srt')
  assert.equal(readiness.transcriptionRoute({ hasSubtitle: false, skippedWhisper: true }), 'platform_subs')
})

test('F4: durationBucket and transcriptionEtaMinutes', () => {
  assert.equal(readiness.durationBucket(60), 'short')
  assert.equal(readiness.durationBucket(600), 'medium')
  assert.equal(readiness.durationBucket(3600), 'long')
  assert.equal(readiness.durationBucket(null), 'unknown')
  assert.equal(readiness.transcriptionEtaMinutes(90), 2)
  assert.equal(readiness.transcriptionEtaMinutes(0), null)
})

test('F4: autostart arms only after preview for paste', () => {
  assert.equal(paste.shouldArmAutostart('autostart', 'paste', false), false)
  assert.equal(paste.shouldArmAutostart('autostart', 'paste', true), true)
  assert.equal(paste.shouldArmAutostart('autostart', 'drop', false), true)
  assert.equal(paste.shouldArmAutostart('button', 'paste', true), false)
})

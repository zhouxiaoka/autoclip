const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

const gate = loadTs(path.resolve(__dirname, '../src/features/studio/importReadiness.ts'))
const report = (code, mode = 'subtitle') => ({ analysis_mode: mode, ready: true, checks: { analysis: { ok: true }, transcription: { ok: false, code, repair: 'install_whisper' } } })

test('1.5.8 local file without SRT and missing local Whisper opens the install gate', () => {
  assert.equal(gate.localTranscriptionGate(report('whisper_not_installed'), false, 'file'), true)
  assert.equal(gate.localTranscriptionGate(report('whisper_install_failed'), false, 'file'), true)
  assert.equal(gate.localTranscriptionGate(report('whisper_not_installed'), true, 'file'), false)
  assert.equal(gate.localTranscriptionGate(report('whisper_not_installed'), false, 'link'), false)
  assert.equal(gate.localTranscriptionGate(report('whisper_not_installed', 'visual'), false, 'file'), false)
  assert.equal(gate.localTranscriptionGate(report('cloud_not_configured'), false, 'file'), false)
  assert.equal(gate.submissionBlock(report('whisper_not_installed'), false, true, { source: 'file' }), 'transcription')
  assert.equal(gate.CLOUD_TRANSCRIPTION_DESTINATION, '/settings?section=speech&provider=cloud')
})

test('1.5.8 install gate copy exists in all 8 languages and the UI wires install + explicit cloud choice', () => {
  const keys = ['需要先安装本地转写', '视频没有字幕，所选的本地 Whisper 还没装好。安装完成后再开始，或改用云端转写。', '一键安装', '改用云端转写',
    '需要先安装本地转写：视频没有字幕，所选的本地 Whisper 还没装好。请到「设置 → 转写」一键安装，或改用云端转写后再导入。']
  for (const lang of ['en', 'es', 'fr', 'ja', 'ko', 'pt', 'ru', 'zh']) {
    const data = JSON.parse(fs.readFileSync(path.resolve(__dirname, `../src/i18n/locales/${lang}.json`), 'utf8'))
    for (const key of keys) assert.ok(typeof data[key] === 'string' && data[key].length > 0, `${lang}: ${key}`)
  }
  const ui = fs.readFileSync(path.resolve(__dirname, '../src/features/studio/CreativeImport.tsx'), 'utf8')
  assert.match(ui, /localTranscriptionGate\(readiness, !!subtitle, nextSource\)\) \{ setError\(LOCAL_TRANSCRIPTION_GATE\)/)
  assert.match(ui, /repair: 'install_whisper'/)  // reuses the existing Settings → Transcription install flow
  assert.match(ui, /navigate\(CLOUD_TRANSCRIPTION_DESTINATION\)/)  // only on click
  assert.doesNotMatch(ui, /provider:\s*'cloud'/)  // never switches provider by itself
})

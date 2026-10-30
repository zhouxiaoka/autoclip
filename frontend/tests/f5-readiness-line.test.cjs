const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('path')
const { runInSandbox } = require('./vm-sandbox.cjs')
const ts = require('typescript')

function load(relative) {
  const file = path.join(__dirname, relative)
  const exports = {}
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText
  runInSandbox(code, {
    exports,
    require: (name) => {
      if (name === '../../i18n') return { t: (s, vars) => vars ? `${s}:${JSON.stringify(vars)}` : s }
      return {}
    },
  })
  return exports
}

const readiness = load('../src/features/studio/importReadiness.ts')

function report(overrides = {}) {
  return {
    analysis_mode: 'auto',
    ready: true,
    checks: {
      analysis: { ok: true, code: 'configured', repair: 'none', label: 'deepseek-chat', trial_ok: true },
      transcription: { ok: true, code: 'whisper_installed', repair: 'none', label: '本地 small' },
      visual: { ok: true, code: 'optional', repair: 'none', label: '未启用' },
      ffmpeg: { ok: true, code: 'available', repair: 'none', label: 'FFmpeg' },
      ...overrides,
    },
  }
}

test('F5: readinessLineItems all-green with labels', () => {
  const items = readiness.readinessLineItems(report())
  assert.equal(items.length, 4)
  assert.equal(items[0].key, 'analysis'); assert.equal(items[0].mark, 'ok'); assert.equal(items[0].detail, 'deepseek-chat'); assert.equal(items[0].badge, undefined)
  assert.equal(items[1].key, 'transcription'); assert.equal(items[1].mark, 'ok'); assert.equal(items[1].detail, '本地 small')
  assert.equal(items[2].key, 'visual'); assert.equal(items[2].mark, 'dash'); assert.equal(items[2].detail, '未启用')
  assert.equal(items[3].key, 'ffmpeg'); assert.equal(items[3].mark, 'ok'); assert.equal(items[3].detail, 'FFmpeg')
  // Clickable even when repair was none — jump to settings section
  assert.equal(items[0].repair, 'settings_ai')
  assert.equal(items[1].repair, 'settings_transcription')
  assert.equal(items[2].repair, 'settings_vision')
  assert.equal(items[3].repair, 'none')
  assert.equal(items.every(i => !i.needsFix), true)
})

test('F5: failed F2 trial shows ⚠ 未通过试跑 badge (F2 language)', () => {
  const items = readiness.readinessLineItems(report({
    analysis: { ok: true, code: 'configured', repair: 'none', label: 'deepseek-chat', trial_ok: false },
  }))
  assert.equal(items[0].mark, 'ok')
  assert.equal(items[0].badge, '⚠ 未通过试跑')
  assert.equal(items[0].needsFix, false)
})

test('F5: missing ASR is ✗ with one-click install_whisper fix', () => {
  const items = readiness.readinessLineItems(report({
    transcription: { ok: false, code: 'whisper_not_installed', repair: 'install_whisper', label: '本地 small' },
  }))
  assert.equal(items[1].mark, 'fail')
  assert.equal(items[1].needsFix, true)
  assert.equal(items[1].repair, 'install_whisper')
  assert.equal(items[1].detail, '本地 small')
})

test('F5: unchecked trial (null) does not show badge', () => {
  const items = readiness.readinessLineItems(report({
    analysis: { ok: true, code: 'configured', repair: 'none', label: 'gpt-4o', trial_ok: null },
  }))
  assert.equal(items[0].badge, undefined)
})

test('F5: CreativeImport always mounts ReadinessLine', () => {
  const src = fs.readFileSync(path.join(__dirname, '../src/features/studio/CreativeImport.tsx'), 'utf8')
  assert.match(src, /import ReadinessLine from '\.\/ReadinessLine'/)
  assert.match(src, /<ReadinessLine\s+report=\{readiness\}/)
})

test('F5: ReadinessLine component exists with data-testid', () => {
  const src = fs.readFileSync(path.join(__dirname, '../src/features/studio/ReadinessLine.tsx'), 'utf8')
  assert.match(src, /data-testid="readiness-line"/)
  assert.match(src, /data-testid=\{`readiness-line-\$\{item\.key\}`\}/)
})

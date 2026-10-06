const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

function transpile(file) {
  const exports = {}
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 },
  }).outputText
  return { exports, code }
}

function loadReadiness() {
  const file = path.join(__dirname, '../src/features/studio/importReadiness.ts')
  const { exports, code } = transpile(file)
  vm.runInNewContext(code, { exports, require() { throw new Error('unexpected import') } })
  return exports
}

const readiness = loadReadiness()
const check = (ok, code, repair) => ({ ok, code, repair })
function report(overrides = {}) {
  return {
    analysis_mode: 'auto',
    ready: false,
    checks: {
      analysis: check(true, 'configured', 'none'),
      transcription: check(true, 'whisper_installed', 'none'),
      visual: check(true, 'optional', 'none'),
      ffmpeg: check(true, 'available', 'none'),
      ...overrides,
    },
  }
}

test('submit waits for the probe, then blocks analysis, visual, ffmpeg, and transcription without an srt', () => {
  const { submissionBlock } = readiness
  assert.equal(submissionBlock(null, false, false), 'pending')
  assert.equal(submissionBlock(null, false, true), null)
  assert.equal(submissionBlock(report({ analysis: check(false, 'not_configured', 'settings_ai') }), true, true), 'analysis')
  assert.equal(submissionBlock(report({ transcription: check(false, 'whisper_not_installed', 'install_whisper') }), false, true), 'transcription')
  assert.equal(submissionBlock(report({ transcription: check(false, 'whisper_not_installed', 'install_whisper') }), true, true), null)
  assert.equal(submissionBlock(report({ visual: check(false, 'not_configured', 'settings_vision') }), false, true), 'visual')
  assert.equal(submissionBlock(report({ ffmpeg: check(false, 'missing', 'none') }), true, true), 'ffmpeg')
  assert.equal(submissionBlock(report(), false, true), null)
})

test('an attached subtitle hides the transcription nag and repair targets match settings sections', () => {
  const value = report({
    transcription: check(false, 'whisper_not_installed', 'install_whisper'),
    ffmpeg: check(false, 'missing', 'none'),
  })
  assert.equal(readiness.visibleIssues(value, false).map(item => item.key).join(','), 'transcription,ffmpeg')
  assert.equal(readiness.visibleIssues(value, true).map(item => item.key).join(','), 'ffmpeg')
  assert.equal(readiness.repairDestination('settings_ai'), '/settings?section=ai')
  assert.equal(readiness.repairDestination('settings_transcription'), '/settings?section=speech')
  assert.equal(readiness.repairDestination('settings_vision'), '/settings?section=vision')
  assert.equal(readiness.repairDestination('install_whisper'), null)
  assert.equal(readiness.repairDestination('none'), null)
})

class FormDataMock {
  constructor() { this.rows = [] }
  append(key, value) { this.rows.push([key, String(value)]) }
  get(key) { const row = this.rows.find(item => item[0] === key); return row && row[1] }
  entries() { return this.rows.values() }
}

function nodes(value) {
  return !value || typeof value !== 'object' ? [] : Array.isArray(value) ? value.flatMap(nodes) : [value, ...nodes(value.props?.children)]
}

function render(options = {}) {
  const calls = []
  const navigations = []
  const installs = []
  const blocked = []
  let index = 0
  const value = options.report === undefined ? report() : options.report
  const states = [
    [options.source || 'link', () => {}],
    [options.url === undefined ? 'https://youtube.com/watch?v=video' : options.url, () => {}],
    [null, () => {}],
    [options.subtitle || null, () => {}],
    [{ goal: 'auto', language: 'source', aspect: null, duration: null, instruction: '' }, () => {}],
    ['', () => {}],
    [['douyin'], () => {}],
    [false, () => {}],
    [false, () => {}],
    ['', () => {}],
    [value, () => {}],
    [options.settled !== false, () => {}],
    [false, () => {}],
  ]
  const { exports, code } = transpile(path.join(__dirname, '../src/features/studio/CreativeImport.tsx'))
  const mocks = {
    'react-i18next': { useTranslation() {} },
    '../../i18n': { t: text => text },
    react: { useState: () => states[index++], useEffect() {} },
    antd: { Select: 'select' },
    'react-router-dom': { useNavigate: () => destination => navigations.push(destination) },
    'react/jsx-runtime': { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }), Fragment: 'fragment' },
    '../../ui': { Btn: 'button', Segmented: 'segmented', Dialog: 'dialog', StatusDot: 'status' },
    './PlatformPicker': { default: 'platform-picker' },
    './api': {
      studioApi: {
        import: async body => { calls.push(body); return { project_id: 'project-1' } },
        readiness: async () => value,
      },
      errorText: String,
    },
    '../../analytics/studio': { trackQuickOutputPlatforms() {} },
    '../../analytics/experience': { trackExperience() {} },
    './types': { defaultImportOptions: { goal: 'auto', language: 'source', aspect: null, duration: null, instruction: '' } },
    './ImportPreferences': { default: 'preferences' },
    '../../services/api': { speechApi: { installRuntime: async () => { installs.push('whisper'); return { started: true, message: '' } } } },
    './importReadiness': readiness,
    './studio.css': {},
    './quick-output.css': {},
  }
  vm.runInNewContext(code, { FormData: FormDataMock, exports, require: id => { assert.ok(id in mocks, id); return mocks[id] } })
  const tree = nodes(exports.default({ onImported: async () => {}, blocked: !!options.blocked, onBlocked: () => blocked.push('setup') }))
  return { tree, calls, navigations, installs, blocked }
}

function button(tree, label) {
  return tree.find(node => node.type === 'button' && node.props?.children === label)
}

test('the banner installs whisper, opens first-run setup, and blocks an unready import', async () => {
  const failing = report({
    analysis: check(false, 'not_configured', 'settings_ai'),
    transcription: check(false, 'whisper_not_installed', 'install_whisper'),
  })
  const opened = render({ report: failing, blocked: true })
  assert.ok(opened.tree.some(node => node.props?.className === 'studio-readiness'))
  await button(opened.tree, '连接 AI 服务').props.onClick()
  assert.deepEqual(opened.blocked, ['setup'])
  assert.deepEqual(opened.navigations, [])
  await button(opened.tree, '安装 Whisper').props.onClick()
  assert.deepEqual(opened.installs, ['whisper'])
  const unready = render({ report: failing })
  await button(unready.tree, '生成成片').props.onClick()
  assert.equal(unready.calls.length, 0)

  const withSubtitle = render({
    report: report({ transcription: check(false, 'sensevoice_not_ready', 'settings_transcription') }),
    subtitle: { name: 'captions.srt' },
  })
  assert.equal(withSubtitle.tree.some(node => node.props?.className === 'studio-readiness'), false)
  await button(withSubtitle.tree, '生成成片').props.onClick()
  assert.equal(withSubtitle.calls.length, 1)
  assert.equal(withSubtitle.calls[0].get('subtitle'), '[object Object]')
})

test('vision repair opens the vision settings section', async () => {
  const view = render({ report: report({ visual: check(false, 'not_configured', 'settings_vision') }) })
  await button(view.tree, '视觉设置').props.onClick()
  assert.deepEqual(view.navigations, ['/settings?section=vision'])
})

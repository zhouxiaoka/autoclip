const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { runInSandbox } = require('./vm-sandbox.cjs')
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
  runInSandbox(code, { exports, require() { throw new Error('unexpected import') } })
  return exports
}

const readiness = loadReadiness()
const realErrorText = require('./load-ts.cjs').loadTs(path.join(__dirname, '../src/features/studio/errorText.ts'), {}, path.join(__dirname, '../src/features/studio'))
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
  assert.equal(submissionBlock(null, false, true), null)  // submit re-probes first, then the backend gate decides
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
  const errors = []
  const probes = []
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
    ['', text => errors.push(text)],
    [value, () => {}],
    [options.settled !== false, () => {}],
    [false, () => {}],
    [false, () => {}],
    [null, () => {}],
    [{ open: false, durationSec: null }, () => {}],
  ]
  const { exports, code } = transpile(path.join(__dirname, '../src/features/studio/CreativeImport.tsx'))
  const mocks = {
    'react-i18next': { useTranslation() {} },
    '../../i18n': { t: text => text },
    react: { useState: () => states[index++], useEffect() {}, useRef: current => ({ current }) },
    antd: { Select: 'select' },
    'react-router-dom': { useNavigate: () => destination => navigations.push(destination) },
    'react/jsx-runtime': { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }), Fragment: 'fragment' },
    '../../ui': { Btn: 'button', Segmented: 'segmented', Dialog: 'dialog', StatusDot: 'status' },
    './PlatformPicker': { default: 'platform-picker' },
    './api': {
      studioApi: {
        import: async body => { calls.push(body); if (options.importError) throw options.importError; return { project_id: 'project-1' } },
        readiness: async () => { probes.push(1); if (options.probeFails) throw new Error('readiness down'); return options.probeValue === undefined ? value : options.probeValue },
      },
      errorText: realErrorText.errorText,
      errorCode: realErrorText.errorCode,
    },
    '../../analytics/studio': { trackQuickOutputPlatforms() {}, trackAsrReadiness() {}, trackOneClickStarted() {}, trackOneClickUndone() {}, trackAutoChoiceOverridden() {} },
    '../../analytics/workflow': { telemetryId: () => 't-importflow-aaaaaaaa' },
    '../../analytics/flags': { useFlag: () => false, flagEnabled: () => false, flagValue: () => 'button', flagAssigned: () => false, featureSnapshot: () => ({ pkg_templates_v1: false }) },
    './TemplatePicker': { default: 'template-picker', templateImportFields: () => ({}) },
    './StyleProbeLine': { default: 'style-probe' },
    './editingStyleSession': { readStyle: () => ({ key: '', status: 'idle', result: null, latencyMs: 0 }) },
    '../../analytics/experience': { trackExperience() {} },
    './platformLabel': { platformLabel: id => id },
    './platformMemory': { readRememberedPlatforms: () => null, resolvePlatforms: () => ({ platforms: ['douyin'], source: 'user' }), samePlatforms: () => true, writeRememberedPlatforms() {} },
    './pasteStart': { claimBackgroundWhisperInstall: () => false, importUrlKind: () => null, isVideoFile: () => false, shouldAutoStart: () => false, shouldBackgroundInstallWhisper: () => false, UNDO_MS: 3000 },
    './importPreferencesStore': { readImportPreferences: () => null },
    './types': { defaultImportOptions: { goal: 'auto', language: 'source', aspect: null, duration: null, instruction: '' } },
    './ImportPreferences': { default: 'preferences' },
    '../../services/api': { speechApi: {
      installRuntime: async () => { installs.push('whisper'); return { started: true, message: '' } },
      downloadModel: async model => { installs.push('model:' + model); return { status: 'downloading', model, message: '' } },
    } },
    './importReadiness': readiness,
    './settingsReturn': { SETTINGS_SAVED_EVENT: 'autoclip:model-settings-saved' },
    './TranscriptionGatePrompt':{default:'transcription-gate'},'./transcriptionRecovery':{isRecoveryCode:c=>['whisper_not_installed','whisper_install_failed','whisper_model_missing','whisper_model_failed','whisper_installing','whisper_model_downloading'].includes(c)},'./useTranscriptionRecovery':{useTranscriptionRecovery:()=>[{phase:'idle',percent:null},{open:(c,m)=>{(globalThis.__recoveryOpened||(globalThis.__recoveryOpened=[])).push(c);installs.push('open:'+c+(m?':'+m:''))},close(){},install:async()=>{installs.push('controller.install')},retry:async()=>{}}]},
    './studio.css': {},
    './quick-output.css': {},
    '../settings/OutputCaptionsSetting': { OutputCaptionsSwitch: () => null },
  }
  runInSandbox(code, { FormData: FormDataMock, exports, require: id => { assert.ok(id in mocks, id); return mocks[id] } })
  const tree = nodes(exports.default({ onImported: async () => {}, blocked: !!options.blocked, onBlocked: () => blocked.push('setup') }))
  return { tree, calls, navigations, installs, blocked, errors, probes }
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
  // #353: the banner button goes through the one recovery controller, never a page-owned install call.
  assert.deepEqual(opened.installs, ['open:whisper_not_installed', 'controller.install'])
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

test('a failed provider check blocks generation and points at model settings', async () => {
  const failing = report({ analysis: check(false, 'validation_failed', 'settings_ai') })
  assert.equal(readiness.submissionBlock(failing, true, true), 'analysis')
  const view = render({ report: failing })
  assert.ok(view.tree.some(node => node.type === 'status' && String(node.props?.label || '').includes('未通过校验')))
  await button(view.tree, '去设置修改').props.onClick()
  assert.deepEqual(view.navigations, ['/settings?section=ai'])
  await button(view.tree, '生成成片').props.onClick()
  assert.equal(view.calls.length, 0)
})

test('vision repair opens the vision settings section', async () => {
  const view = render({ report: report({ visual: check(false, 'not_configured', 'settings_vision') }) })
  await button(view.tree, '视觉设置').props.onClick()
  assert.deepEqual(view.navigations, ['/settings?section=vision'])
})

test('B5: failed separate vision validation blocks generation and offers repair', async () => {
  const failing = report({ visual: check(false, 'validation_failed', 'settings_vision') })
  assert.equal(readiness.submissionBlock(failing, true, true), 'visual')
  const view = render({ report: failing, subtitle: { name: 'fixture.srt' } })
  await button(view.tree, '视觉设置').props.onClick()
  assert.deepEqual(view.navigations, ['/settings?section=vision'])
  await button(view.tree, '生成成片').props.onClick()
  assert.equal(view.calls.length, 0)
})

test('a text-only vision follow blocks generation with a clear message', async () => {
  const failing = report({ visual: check(false, 'vision_unsupported', 'settings_vision') })
  assert.equal(readiness.submissionBlock(failing, true, true), 'visual')
  const view = render({ report: failing })
  assert.ok(view.tree.some(node => node.type === 'status' && String(node.props?.label || '').includes('不能看图')))
  await button(view.tree, '视觉设置').props.onClick()
  assert.deepEqual(view.navigations, ['/settings?section=vision'])
  await button(view.tree, '生成成片').props.onClick()
  assert.equal(view.calls.length, 0)
})

test('an installed runtime without its model offers the model download, not another install', async () => {
  // RC156 Win QA #5: readiness used to report ready with only the runtime installed.
  const missing = report({ transcription: { ...check(false, 'whisper_model_missing', 'install_whisper'), model: 'small' } })
  const view = render({ report: missing })
  assert.equal(button(view.tree, '安装 Whisper'), undefined)
  await button(view.tree, '下载转写模型').props.onClick()
  assert.deepEqual(view.installs, ['open:whisper_model_missing:small', 'controller.install'], 'the controller downloads the model (#353)')
  assert.equal(readiness.submissionBlock(missing, false, true), 'transcription')
  assert.equal(readiness.submissionBlock(missing, true, true), null)
  const downloading = render({ report: report({ transcription: { ...check(false, 'whisper_model_downloading', 'none'), model: 'small' } }) })
  assert.ok(downloading.tree.some(node => node.type === 'status' && node.props?.label === '正在下载转写模型…' && node.props?.tone === 'accent'))
  const unready = render({ report: missing })
  await button(unready.tree, '生成成片').props.onClick()
  assert.equal(unready.calls.length, 0)
})

test('AUTOCLIP-FRONTEND-C: a readiness report without checks or transcription does not throw', () => {
  for (const partial of [
    { analysis_mode: 'auto', ready: false },
    { analysis_mode: 'auto', ready: false, checks: null },
    { analysis_mode: 'auto', ready: false, checks: {} },
    { analysis_mode: 'auto', ready: false, checks: { analysis: check(true, 'configured', 'none') } },
  ]) {
    assert.equal(readiness.visibleIssues(partial, false).length, 0)
    assert.equal(readiness.submissionBlock(partial, false, true), null)
  }
  const onlyFfmpeg = { analysis_mode: 'auto', ready: false, checks: { ffmpeg: check(false, 'ffmpeg_missing', 'none') } }
  assert.equal(readiness.submissionBlock(onlyFfmpeg, false, true), 'ffmpeg')
  assert.equal(readiness.visibleIssues(onlyFfmpeg, false).map(item => item.key).join(','), 'ffmpeg')
})

test('ASR readiness properties infer provider from the check code and never need a model name', () => {
  const { asrReadinessProperties } = readiness
  const local = asrReadinessProperties(report({ transcription: check(false, 'whisper_not_installed', 'install_whisper') }), false)
  assert.equal(local.provider, 'whisper_local')
  assert.equal(local.code, 'whisper_not_installed')
  assert.equal(local.has_subtitle, false)
  assert.equal(local.blocked, true)
  const sense = asrReadinessProperties(report({ transcription: check(false, 'sensevoice_not_ready', 'settings_transcription') }), true)
  assert.equal(sense.provider, 'sensevoice_local')
  assert.equal(sense.blocked, false)
  const cloud = asrReadinessProperties(report({ transcription: check(false, 'cloud_not_configured', 'settings_transcription') }), false)
  assert.equal(cloud.provider, 'cloud')
  assert.equal(cloud.blocked, true)
  assert.equal(asrReadinessProperties({ analysis_mode: 'auto', ready: false }, false).provider, 'whisper_local')
  assert.equal(asrReadinessProperties({ analysis_mode: 'auto', ready: false }, false).blocked, false)
})

test('R19 #115: a failed readiness probe is re-checked 3 times, then the import goes to the backend gate', async () => {
  const view = render({ report: null, probeFails: true })
  await button(view.tree, '生成成片').props.onClick()
  assert.equal(view.probes.length, 3)
  assert.equal(view.calls.length, 1)
})

test('R19 #115: a re-check that recovers uses the fresh report (blocked by the local gate, no request)', async () => {
  const view = render({ report: null, probeValue: report({ transcription: check(false, 'whisper_not_installed', 'install_whisper') }) })
  await button(view.tree, '生成成片').props.onClick()
  assert.equal(view.probes.length, 1)
  assert.equal(view.calls.length, 0)
  assert.equal(view.errors.at(-1), '还没有可用的转写。可以附上 SRT 字幕，或先准备好转写。')
})

const axios422 = detail => Object.assign(new Error('Request failed with status code 422'), { response: { status: 422, data: { detail } } })

test('R20 #168: a coded backend 422 opens the install prompt (and the installing prompt) from the code', async () => {
  const gate = render({ importError: axios422({ code: 'whisper_not_installed', message: 'any wording' }) })
  await button(gate.tree, '生成成片').props.onClick()
  assert.equal(gate.calls.length, 1)
  globalThis.__recoveryOpened = []
  await button(gate.tree, '生成成片').props.onClick()
  const wait = render({ importError: axios422({ code: 'whisper_installing', message: 'any wording' }) })
  await button(wait.tree, '生成成片').props.onClick()
  const failed = render({ importError: axios422({ code: 'whisper_install_failed', message: 'x' }) })
  await button(failed.tree, '生成成片').props.onClick()
  // #418 rewrite: the coded refusal opens the shared recovery controller with the code itself
  assert.deepEqual(globalThis.__recoveryOpened, ['whisper_not_installed', 'whisper_installing', 'whisper_install_failed'])
})

test('R20 #168: the prompt is never chosen from the Chinese text; an uncoded 422 shows its message', async () => {
  const text = '需要先安装本地转写：视频没有字幕，所选的本地 Whisper 还没装好。'
  const view = render({ importError: axios422(text) })
  await button(view.tree, '生成成片').props.onClick()
  assert.equal(view.errors.at(-1), text)
  const source = fs.readFileSync(path.join(__dirname, '../src/features/studio/CreativeImport.tsx'), 'utf8')
  assert.doesNotMatch(source, /startsWith\(LOCAL_TRANSCRIPTION/)
})

test('R21: the desktop follows the backend skippable flag instead of inferring the visual route', () => {
  const missing = check(false, 'whisper_not_installed', 'install_whisper')
  const skippable = { ...report({ transcription: { ...missing, skippable: true } }), analysis_mode: 'visual' }
  assert.equal(readiness.submissionBlock(skippable, false, true, { source: 'file' }), null)
  // visual mode without the flag (e.g. no vision model): blocked like any other missing transcriber
  const visualOnly = { ...report({ transcription: missing }), analysis_mode: 'visual' }
  assert.equal(readiness.submissionBlock(visualOnly, false, true, { source: 'file' }), 'transcription')
  const source = fs.readFileSync(path.join(__dirname, '../src/features/studio/importReadiness.ts'), 'utf8')
  assert.doesNotMatch(source, /analysis_mode === 'visual'/)
})

test('R19 #115: no settings file -> default local Whisper not installed, no SRT: blocked before start', async () => {
  // /studio/readiness with no settings document reports the defaults (whisper_local, not installed).
  const view = render({ report: report({ transcription: check(false, 'whisper_not_installed', 'install_whisper') }) })
  await button(view.tree, '生成成片').props.onClick()
  assert.equal(view.calls.length, 0)
})

test('R22 #212: a whisper failure offers transcription settings (install entry), other failures keep model settings', () => {
  for (const code of ['whisper_not_installed', 'whisper_install_failed']) {
    assert.deepEqual({ ...readiness.failureSettings(code) }, { label: '打开转写设置', to: '/settings?section=speech' })
  }
  for (const code of ['llm_not_configured', '', null, undefined]) {
    assert.deepEqual({ ...readiness.failureSettings(code) }, { label: '模型设置', to: '/settings?section=ai' })
  }
  // a source failure is fixed with another file, not in settings.
  for (const code of ['source_unreadable', 'source_too_short', 'source_no_audio', 'source_not_found']) {
    assert.deepEqual({ ...readiness.failureSettings(code) }, { label: '换一个视频', to: '/' })
  }
})

const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const React = require('react')
const ts = require('typescript')
const { runInSandbox } = require('./vm-sandbox.cjs')
const { loadTs } = require('./load-ts.cjs')

const check = (ok, code, repair) => ({ ok, code, repair })
function report(overrides = {}) {
  return {
    analysis_mode: 'auto',
    ready: Object.values(overrides).every(item => item.ok !== false),
    checks: {
      analysis: check(true, 'configured', 'none'),
      transcription: check(true, 'whisper_installed', 'none'),
      visual: check(true, 'optional', 'none'),
      ffmpeg: check(true, 'available', 'none'),
      ...overrides,
    },
  }
}

function nodes(value) {
  return !value || typeof value !== 'object' ? [] : Array.isArray(value) ? value.flatMap(nodes) : [value, ...nodes(value.props?.children)]
}

function flatten(node) {
  if (typeof node?.type === 'function') {
    try { return flatten(node.type(node.props || {})) } catch { return [node] }
  }
  if (Array.isArray(node)) return node.flatMap(flatten)
  if (!React.isValidElement(node)) return [node]
  const children = React.Children.toArray(node.props?.children)
  const extra = []
  if (node.props?.footer) extra.push(node.props.footer)
  if (node.props?.description) extra.push(node.props.description)
  return [node, ...children.flatMap(flatten), ...extra.flatMap(flatten)]
}

function button(tree, label) {
  return tree.find(node => node.type === 'button' && node.props?.children === label)
}

function createHooks() {
  const slots = []
  let cursor = 0
  const pending = []
  return {
    begin() { cursor = 0 },
    flush() {
      const effects = pending.splice(0)
      for (const effect of effects) {
        const cleanup = effect.fn()
        effect.cleanup = typeof cleanup === 'function' ? cleanup : null
      }
    },
    react: {
      useState(init) {
        const index = cursor++
        if (!(index in slots)) slots[index] = { state: typeof init === 'function' ? init() : init }
        const slot = slots[index]
        return [slot.state, next => { slot.state = typeof next === 'function' ? next(slot.state) : next }]
      },
      useRef(init) {
        const index = cursor++
        if (!(index in slots)) slots[index] = { current: init }
        return slots[index]
      },
      useEffect(fn, deps) {
        const index = cursor++
        const prev = slots[index]
        const changed = !prev || !deps || !prev.deps || deps.length !== prev.deps.length || deps.some((item, at) => !Object.is(item, prev.deps[at]))
        if (!changed) return
        if (prev?.cleanup) prev.cleanup()
        const record = { deps, fn, cleanup: null }
        slots[index] = record
        pending.push(record)
      },
    },
  }
}

class FormDataMock {
  constructor() { this.rows = [] }
  append(key, value) { this.rows.push([key, String(value)]) }
  get(key) { const row = this.rows.find(item => item[0] === key); return row && row[1] }
}

function listen() {
  const handlers = new Map()
  return {
    addEventListener(type, fn) {
      const list = handlers.get(type) || new Set()
      list.add(fn)
      handlers.set(type, list)
    },
    removeEventListener(type, fn) { handlers.get(type)?.delete(fn) },
    dispatchEvent(event) {
      for (const fn of handlers.get(event.type) || []) fn(event)
      return true
    },
    setTimeout,
    clearTimeout,
  }
}

test('saving the first-run dialog makes the import page ready without a reload', async () => {
  const notReady = report({ analysis: check(false, 'not_configured', 'settings_ai') })
  const ready = report()
  const probes = []
  const imports = []
  const hooks = createHooks()
  const window = listen()
  const settingsReturn = loadTs(path.join(__dirname, '../src/features/studio/settingsReturn.ts'), { __globals: { window } })
  const file = path.join(__dirname, '../src/features/studio/CreativeImport.tsx')
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 },
  }).outputText
  const exports = {}
  const mocks = {
    'react-i18next': { useTranslation() {} },
    '../../i18n': { t: text => text, getLocale: () => 'zh' },
    react: hooks.react,
    antd: { Select: 'select' },
    'react-router-dom': { useNavigate: () => () => {} },
    'react/jsx-runtime': { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }), Fragment: 'fragment' },
    '../../ui': { Btn: 'button', Segmented: 'segmented', Dialog: 'dialog', StatusDot: 'status' },
    './PlatformPicker': { default: 'platform-picker' },
    './api': {
      studioApi: {
        readiness: async () => { const value = probes.length ? ready : notReady; probes.push(value); return value },
        readinessProbe: async () => ready,
        import: async body => { imports.push(body); return { project_id: 'project-1' } },
      },
      errorText: text => text,
      errorCode: () => '',
    },
    '../../analytics/studio': { trackQuickOutputPlatforms() {}, trackAsrReadiness() {}, trackOneClickStarted() {}, trackOneClickUndone() {}, trackAutoChoiceOverridden() {} },
    '../../analytics/workflow': { telemetryId: () => 't-importflow-aaaaaaaa' },
    '../../analytics/flags': { useFlag: () => false, flagEnabled: () => false, flagValue: () => 'button', flagAssigned: () => false, featureSnapshot: () => ({}) },
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
    '../../services/api': { speechApi: {} },
    './importReadiness': loadTs(path.join(__dirname, '../src/features/studio/importReadiness.ts')),
    './TranscriptionGatePrompt': { default: 'transcription-gate' },
    './transcriptionRecovery': { isRecoveryCode: () => false, probeConfig: () => ({}) },
    './useTranscriptionRecovery': { useTranscriptionRecovery: () => [{ phase: 'idle', percent: null }, { open() {}, close() {}, install: async () => {}, retry: async () => {} }] },
    './settingsReturn': settingsReturn,
    './studio.css': {},
    './quick-output.css': {},
    '../settings/OutputCaptionsSetting': { OutputCaptionsSwitch: () => null },
  }
  runInSandbox(code, {
    exports, window, Event, URL, URLSearchParams, FormData: FormDataMock, setTimeout, clearTimeout, console,
    require: id => { assert.ok(id in mocks, id); return mocks[id] },
  })

  const draw = () => { hooks.begin(); return nodes(exports.default({ onImported: async () => {} })) }
  const ticks = async () => { for (let i = 0; i < 6; i++) await Promise.resolve() }
  let tree = draw()
  hooks.flush()
  await ticks()
  tree = draw()
  assert.equal(probes.length, 1)
  assert.ok(tree.some(node => node.type === 'status' && String(node.props?.label || '').includes('分析模型还没配好')))
  tree.find(node => node.type === 'textarea').props.onChange({ target: { value: 'https://youtube.com/watch?v=video' } })
  tree = draw()
  await button(tree, '生成成片').props.onClick()
  assert.equal(imports.length, 0)
  tree = draw()
  assert.equal(tree.find(node => node.props?.className === 'studio-error')?.props?.children, '请先连接 AI 服务，再导入视频。')

  const providers = loadTs('providers.ts', { '../../i18n': { t: text => text } })
  let settings = { saved: false, connections: [], analysis: null }
  const store = {
    settings,
    busy: {},
    keyHints: {},
    saving: false,
    error: '',
    chooseProvider(_role, provider) {
      settings = { ...settings, connections: [{ id: 's', name: provider, provider, base_url: '', api_key: 'sk-test', has_key: true, image_api: 'auto', image_base_url: '' }], analysis: { connection_id: 's', model: 'm', capability: 'auto' } }
      store.settings = settings
    },
    editConnection() {},
    save: async () => {
      settings = { ...settings, saved: true }
      store.settings = settings
      settingsReturn.notifySettingsSaved(window)
      return { ok: true }
    },
  }
  const slots = []
  let cursor = 0
  const FirstRun = loadTs('FirstRunSetup.tsx', {
    react: {
      useState(value) {
        const index = cursor++
        if (!(index in slots)) slots[index] = value
        return [slots[index], next => { slots[index] = typeof next === 'function' ? next(slots[index]) : next }]
      },
      useRef(value) {
        const index = cursor++
        if (!(index in slots)) slots[index] = { current: value }
        return slots[index]
      },
      useEffect() {},
    },
    'react-i18next': { useTranslation() {} },
    'react-router-dom': { useNavigate: () => () => {} },
    antd: { ConfigProvider: ({ children }) => children },
    '../../analytics/experience': { trackExperience() {} },
    '../../analytics/events': { trackSponsorLinkOpened() {} },
    '../../analytics/workflow': { telemetryId: () => 't-aaaaaaaaaaaa' },
    '../../i18n': { t: text => text },
    '../../ui': {
      Btn: ({ children, onClick }) => React.createElement('button', { onClick }, children),
      Dialog: ({ children, title, footer, description }) => React.createElement('dialog', { title, description }, children, footer),
      Icon: { Check: () => React.createElement('i', null, 'check') },
      StatusDot: 'status',
    },
    '../../utils/externalLinks': { openExternalLink() {} },
    './useModelSettings': { useModelSettings: () => store },
    './providers': providers,
    './ProviderFields': { default: () => React.createElement('div', { className: 'fields' }) },
    './modelSettingsLogic': {
      needsSetup: () => true,
      mainConnection: value => value.connections[0],
      connectionReady: () => true,
    },
    './firstRunGuidance': loadTs('firstRunGuidance.ts'),
  }).default
  const setup = () => { cursor = 0; return flatten(FirstRun({})) }
  setup().filter(node => node?.type === 'button').at(-1).props.onClick()
  const save = setup().filter(node => node?.type === 'button').at(-1)
  assert.equal(save.props.children, '连接并保存')
  save.props.onClick()
  await ticks()

  tree = draw()
  assert.equal(probes.length, 2)
  assert.equal(tree.some(node => String(node.props?.label || '').includes('分析模型还没配好')), false)
  assert.equal(tree.some(node => node.props?.className === 'studio-readiness'), false)
  await button(tree, '生成成片').props.onClick()
  assert.equal(imports.length, 1)
  tree = draw()
  assert.equal(tree.some(node => node.props?.className === 'studio-error'), false)
})

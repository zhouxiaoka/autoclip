const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const ts = require('typescript')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const { runInSandbox } = require('./vm-sandbox.cjs')
const { loadTs } = require('./load-ts.cjs')

const ROOT = path.resolve(__dirname, '..')
const REPO = path.resolve(ROOT, '..')
const translate = (key, values) => values
  ? String(key).replace(/\{\{\s*(\w+)\s*\}\}/g, (_, name) => values[name] == null ? '' : String(values[name]))
  : key

function renderStudioWith(workspace, project = {}, connectionCount = 1) {
  const buttons = []
  const empty = () => null
  const requireModule = (name) => {
    if (name === 'react' || name === 'react/jsx-runtime') return require(name)
    if (name === 'react-i18next') return { useTranslation() {} }
    if (name === 'react-router-dom') return { useNavigate: () => () => {}, useLocation: () => ({ search: '' }) }
    if (name === '../../i18n') return { t: translate, getLocale: () => 'zh' }
    if (name === '../../utils/externalLinks') return { openExternalLink() {} }
    if (name === '../../ui') return {
      Btn: (props) => { buttons.push(props); return React.createElement('button', { 'data-variant': props.variant || '' }, props.children) },
      Section: ({ children }) => React.createElement('section', null, children),
      Dialog: empty,
      fmtDuration: String,
    }
    if (name === './useWorkspace') return { useWorkspace: () => ({ workspace, loaded: true, loading: false, refresh() {} }) }
    if (name === './api') return { studioApi: { source: () => '/test.mp4', retry: async () => ({}) }, errorText: String }
    if (name === './failureAction' || name === './failurePresentation' || name === './settingsReturn' || name === './studioProgress' || name === './importReadiness' || name === './browserCookieRecovery') {
      return loadTs(path.resolve(ROOT, 'src/features/studio/' + name.slice(2) + '.ts'))
    }
    if (name === '../../utils/llmFailure') return loadTs(path.resolve(ROOT, 'src/utils/llmFailure.ts'))
    if (name === '../../utils/timelineFailure') return loadTs(path.resolve(ROOT, 'src/utils/timelineFailure.ts'))
    if (name === './switchModelOptions') return { listSwitchModelOptions: () => [], usableConnectionCount: () => connectionCount, analysisProviderId: () => null }
    if (name === './DiagnosePanel' || name === './SwitchModelDialog' || name === './ExportHistory' || name === './DraftResultCard' || name === './OutputVariantCard') {
      return { __esModule: true, default: empty }
    }
    if (name === './platformLabel') return { platformLabel: String }
    if (name === '../../analytics/flags') return { flagEnabled: () => false, flagAssigned: () => false }
    if (name === '../../analytics/studio') return { trackLegacyEntry() {} }
    if (name === '../../analytics/observer') return { workflow: { emit() {}, adoptOpenAttempt() {} } }
    if (name === './legacyEntrypoints') return { legacyEntrypointsHidden: () => true }
    if (name === './platformMemory') return { dismissMorePlatformBanner() {}, hasSuccessHistory: () => false, morePlatformBannerSeen: () => true, stashReuseImport() {}, suggestAnotherPlatform: () => '' }
    if (name === './noticeRuntime') return { clearCompletionBadge() {}, subscribeCompletionNotice: () => () => {} }
    if (name === './completionNotice') return { noticeCopy: (value) => value }
    if (name === './overrides') return { followOutputLeave() {} }
    if (name === './etaModel') return { recordSuccess() {} }
    if (name === '../settings/modelSettingsApi') return { modelSettingsApi: { get: async () => null } }
    if (name === '../settings/modelSettingsLogic') return { forSave: (value) => value }
    if (name === '../settings/modelDefaults') return { syncFollowingCover: (_left, right) => right }
    if (name === '../diagnostics/FailureHint') return { __esModule: true, default: empty }
    if (name === '../diagnostics/failureHintPolicy') return { nextLiveFailure: (prev) => ({ previous: prev, failed: false }) }
    if (name === './studio.css' || name === './quick-output.css') return {}
    return { default: empty }
  }
  const source = fs.readFileSync(path.join(ROOT, 'src/features/studio/StudioResults.tsx'), 'utf8')
  const exportsObject = {}
  runInSandbox(ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
  }).outputText, { exports: exportsObject, require: requireModule, URLSearchParams, console: { log() {}, error() {}, warn() {} } })
  const html = renderToStaticMarkup(React.createElement(exportsObject.default, {
    project: { id: 'p1', status: 'failed', settings: { smart_import: {} }, clips: [], collections: [], ...project },
    onCreateCollection() {}, onReload() {},
  }))
  return { html, buttons }
}

test('StudioResults renders billing transparency copy and sponsor top-up button for insufficient_quota', () => {
  const { html, buttons } = renderStudioWith({
    analysis: {
      status: 'failed', error: '余额不足', error_code: 'insufficient_quota',
      upstream_error_type: 'insufficient_quota', provider: 'apimart',
      failure_stage: 'analyze', billable_calls_before_failure: 0, run_id: 'r1',
    },
    generation: { auto_start: true, status: 'failed', error_code: 'insufficient_quota', provider: 'apimart' },
    drafts: [], jobs: [], output_variants: [], attempts: [], events: [],
  })
  assert.match(html, /class="studio-billing"/)
  const labels = buttons.map(b => b.children)
  assert.ok(labels.includes('核对余额并测试连接'), `expected quota check button, got ${labels}`)
  assert.ok(labels.some(label => /去.*充值/.test(String(label))), `expected top-up button, got ${labels}`)
})

test('StudioResults wires R3 checkpoint resume label + fresh restart and X1 repeat-failure diagnose CTA', () => {
  const resumed = renderStudioWith({
    analysis: { status: 'failed', error: '模型响应超时', error_code: 'timeout', failure_stage: 'analyze', run_id: 'r1' },
    generation: { auto_start: true, status: 'failed', error_code: 'timeout' },
    resume_point: { point: 'analyze', label: '从分析继续' },
    drafts: [], jobs: [], output_variants: [], attempts: [], events: [],
  })
  const resumeLabels = resumed.buttons.map(b => b.children)
  assert.ok(resumeLabels.includes('从分析继续'), `expected checkpoint label, got ${resumeLabels}`)
  assert.ok(resumeLabels.includes('从头重做'), `expected fresh retry button, got ${resumeLabels}`)

  const repeated = renderStudioWith({
    analysis: { status: 'failed', error: '模型响应超时', error_code: 'timeout', failure_stage: 'analyze', run_id: 'r2' },
    generation: { auto_start: true, status: 'failed', error_code: 'timeout', repeat_failure: { count: 2, same_code: true } },
    drafts: [], jobs: [], output_variants: [], attempts: [], events: [],
  })
  const ctas = repeated.buttons.filter(b => b.variant === 'cta').map(b => b.children)
  assert.deepEqual(ctas, ['看看哪里不对'])
})

test('QuitGuard runningCount includes active detail-page workspace sources and deduplicates by project id', () => {
  const quitGuard = loadTs(path.join(ROOT, 'src/features/studio/quitGuard.tsx'), {
    'react': require('react'),
    'react-i18next': { useTranslation() {} },
    '../../analytics/posthog': { captureBusinessEvent() {} },
    '../../analytics/workflow': { safeStudioProperties: (v) => v },
    '../../utils/desktopMode': { isDesktopMode: async () => false },
    '../../store/useProjectStore': { useProjectStore: Object.assign(() => [], { getState: () => ({ projects: [] }) }) },
    '../../ui': { Btn: () => null, Dialog: () => null },
    '../../i18n': { t: translate },
    './keepAwake': loadTs(path.join(ROOT, 'src/features/studio/keepAwake.ts')),
  })
  // Detail page retry/export active via keepAwake source even when global projects list says completed
  const active = new Map([['workspace:p1', true], ['statusbar:p2', true]])
  assert.equal(quitGuard.runningCount([{ id: 'p1', status: 'completed' }], active), 2)
  // Deduplicates when project p1 is active in both projects list and workspace source
  assert.equal(quitGuard.runningCount([{ id: 'p1', status: 'processing' }], new Map([['workspace:p1', true]])), 1)
})

test('BackendCrashBanner invokes registered restart_backend_service command, is wired in App, translated in 8 locales, and Rust backend_manager emits backend-crashed + reaps EOF child', () => {
  const bannerPath = path.join(ROOT, 'src/desktop/BackendCrashBanner.tsx')
  assert.ok(fs.existsSync(bannerPath), 'BackendCrashBanner.tsx must exist')
  const banner = fs.readFileSync(bannerPath, 'utf8')
  assert.match(banner, /backend-crashed/)

  // Exact Tauri command cross-check: every invoke('...') in BackendCrashBanner must be registered in lib.rs and defined in commands.rs.
  const invoked = [...banner.matchAll(/invoke\(\s*['"]([^'"]+)['"]\s*\)/g)].map(m => m[1])
  assert.deepEqual(invoked, ['restart_backend_service'])
  const libRs = fs.readFileSync(path.join(REPO, 'src-tauri/src/lib.rs'), 'utf8')
  const handlerMatch = libRs.match(/tauri::generate_handler!\[([\s\S]*?)\]/)
  assert.ok(handlerMatch, 'tauri::generate_handler![] must exist in lib.rs')
  const registered = new Set(handlerMatch[1].split(',').map(s => s.trim().split('::').pop()).filter(Boolean))
  const commandsRs = fs.readFileSync(path.join(REPO, 'src-tauri/src/commands.rs'), 'utf8')
  for (const cmd of invoked) {
    assert.ok(registered.has(cmd), `command ${cmd} is not registered in src-tauri/src/lib.rs generate_handler![]`)
    assert.match(commandsRs, new RegExp(`pub\\s+(?:async\\s+)?fn\\s+${cmd}\\b`), `command ${cmd} not defined in src-tauri/src/commands.rs`)
  }

  const app = fs.readFileSync(path.join(ROOT, 'src/App.tsx'), 'utf8')
  assert.match(app, /BackendCrashBanner/)

  const key = '本地后台服务多次意外退出，已暂停自动重启。请点击重启服务恢复使用。'
  const localesDir = path.join(ROOT, 'src/i18n/locales')
  const files = fs.readdirSync(localesDir).filter(f => f.endsWith('.json'))
  assert.equal(files.length, 13)
  for (const file of files) {
    const data = JSON.parse(fs.readFileSync(path.join(localesDir, file), 'utf8'))
    assert.ok(data[key], `${file} missing translation for crash banner`)
    if (file !== 'zh.json') assert.notEqual(data[key], key, `${file} must translate crash banner`)
  }

  const rust = fs.readFileSync(path.join(REPO, 'src-tauri/src/backend_manager.rs'), 'utf8')
  assert.match(rust, /BACKEND_CRASHED_EVENT/)
  assert.match(rust, /"backend-crashed"/)
  assert.match(rust, /wait_for_early_exit/)
})

const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const ts = require('typescript')
const { loadTs } = require('./load-ts.cjs')
const { runInSandbox } = require('./vm-sandbox.cjs')

const ROOT = path.resolve(__dirname, '..')
const SRC_ROOT = path.resolve(ROOT, 'src')
const translate = (key, values) => values
  ? String(key).replace(/\{\{\s*(\w+)\s*\}\}/g, (_, name) => values[name] == null ? '' : String(values[name]))
  : key

function renderStudioWith(workspace, project = {}, connectionCount = 1) {
  const buttons = []
  const empty = () => null
  const requireModule = name => {
    if (name === 'react' || name === 'react/jsx-runtime') return require(name)
    if (name === 'react-i18next') return { useTranslation() {} }
    if (name === 'react-router-dom') return { useNavigate: () => () => {}, useLocation: () => ({ search: '' }) }
    if (name === '../../i18n') return { t: translate, getLocale: () => 'zh' }
    if (name === '../../utils/externalLinks') return { openExternalLink() {} }
    if (name === '../../ui') return {
      Btn: props => { buttons.push(props); return React.createElement('button', { 'data-variant': props.variant || '' }, props.children) },
      Section: ({ children }) => React.createElement('section', null, children),
      Dialog: empty,
      fmtDuration: String,
    }
    if (name === './useWorkspace') return { useWorkspace: () => ({ workspace, loaded: true, loading: false, refresh() {} }) }
    if (name === './api') return { studioApi: { source: () => '/test.mp4', retry: async () => ({}) }, errorText: String }
    if (name === './failureAction' || name === './failurePresentation' || name === './settingsReturn' || name === './studioProgress' || name === './importReadiness' || name === './browserCookieRecovery') {
      return loadTs(path.resolve(SRC_ROOT, 'features/studio/' + name.slice(2) + '.ts'))
    }
    if (name === '../../utils/llmFailure') return loadTs(path.resolve(SRC_ROOT, 'utils/llmFailure.ts'))
    if (name === '../../utils/timelineFailure') return loadTs(path.resolve(SRC_ROOT, 'utils/timelineFailure.ts'))
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
    if (name === './completionNotice') return { noticeCopy: value => value }
    if (name === './overrides') return { followOutputLeave() {} }
    if (name === './etaModel') return { recordSuccess() {} }
    if (name === '../settings/modelSettingsApi') return { modelSettingsApi: { get: async () => null } }
    if (name === '../settings/modelSettingsLogic') return { forSave: value => value }
    if (name === '../settings/modelDefaults') return { syncFollowingCover: (_left, right) => right }
    if (name === '../diagnostics/FailureHint') return { __esModule: true, default: empty }
    if (name === '../diagnostics/failureHintPolicy') return { nextLiveFailure: prev => ({ previous: prev, failed: false }) }
    if (name === './studio.css' || name === './quick-output.css') return {}
    return { default: empty }
  }
  const source = fs.readFileSync(path.join(SRC_ROOT, 'features/studio/StudioResults.tsx'), 'utf8')
  const exportsObject = {}
  runInSandbox(ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
  }).outputText, { exports: exportsObject, require: requireModule, URLSearchParams, console: { log() {}, error() {}, warn() {} } })
  const html = renderToStaticMarkup(React.createElement(exportsObject.default, {
    project: { id: 'p1', name: 'Demo', status: 'error', clips: [], collections: [], ...project },
  }))
  return { html, buttons: buttons.map(b => String(b.children ?? '')) }
}

test('Golden Journey 1: empty setup -> recommended DeepSeek/DashScope first -> saveable without no_model; clear key & remove connection', () => {
  const providers = loadTs('providers.ts', { '../../i18n': { t: translate } })
  const logic = loadTs('modelSettingsLogic.ts', { '../../i18n': { t: translate } })
  const rec = Array.from(providers.recommendedSetupProviders())
  assert.deepEqual(rec.slice(0, 3), ['deepseek', 'dashscope', 'apimart'])

  const blank = {
    version: 1, saved: false, connections: [],
    analysis: null, vision: null, cover: null,
    transcription: { provider: 'whisper_local', model: 'base', model_source: 'preset' },
    cover_enabled: false, allow_send_frame: true, analysis_mode: 'auto', allow_visual_screening: true,
    chunk_size: 5000, min_score_threshold: 0.7, max_clips_per_collection: 5,
  }
  assert.equal(logic.needsSetup(blank), true)
  const withDs = {
    ...blank,
    saved: true,
    connections: [{ id: 'ds-1', name: 'DeepSeek', provider: 'deepseek', base_url: 'https://api.deepseek.com', api_key: 'sk-1234567890', has_key: true, api_key_masked: 'sk-…890', image_api: 'auto', image_base_url: '' }],
    analysis: { connection_id: 'ds-1', model: 'deepseek-flash', capability: 'text', model_source: 'user' },
  }
  assert.equal(logic.needsSetup(withDs), false)
  assert.equal(logic.saveIssue(withDs), null)

  const cleared = logic.clearConnectionKey(withDs, 'ds-1')
  assert.equal(cleared.connections[0].api_key, '')
  assert.equal(cleared.connections[0].has_key, false)
  assert.equal(cleared.connections[0].api_key_masked, '')

  const removed = logic.removeConnection(withDs, 'ds-1')
  assert.equal(removed.connections.length, 0)
  assert.equal(removed.analysis, null)
  assert.equal(removed.cover_enabled, false)
})

test('Golden Journey 2: Bilibili share text URL extraction + source_blocked errorCode + HashRouter browser-cookies focus', () => {
  const paste = loadTs('pasteStart.ts', {}, path.join(SRC_ROOT, 'features/studio'))
  const errMod = loadTs('errorText.ts', {}, path.join(SRC_ROOT, 'features/studio'))
  const extracted = paste.extractImportUrl('【深度访谈】https://b23.tv/abc123 快来围观')
  assert.equal(extracted, 'https://b23.tv/abc123')
  assert.equal(errMod.errorCode({ response: { data: { detail: { error_code: 'source_blocked' } } } }), 'source_blocked')

  const recovery = loadTs('browserCookieRecovery.ts', {}, path.join(SRC_ROOT, 'features/studio'))
  assert.equal(recovery.cookieAssistFromLocation('', '#/?focus=browser-cookies'), true)
  const importSrc = fs.readFileSync(path.join(SRC_ROOT, 'features/studio/CreativeImport.tsx'), 'utf8')
  assert.match(importSrc, /cookieAssistFromLocation/)
})

test('Golden Journey 3: Whisper download progress advancing past 10 minutes never triggers false timeout', () => {
  const clock = loadTs('recoveryClock.ts', {}, path.join(SRC_ROOT, 'features/studio'))
  let state = clock.startClock(0)
  let outcome = 'continue'
  // 15 minutes of steady progress every 5s must never trip the 10-minute stall timeout.
  for (let t = 5_000; t <= 15 * 60_000; t += 5_000) {
    const step = clock.observe(state, { now: t, answered: true, progressed: true, pollMs: 5_000, readTimeoutMs: 10_000 })
    state = step.clock
    outcome = step.outcome
    assert.equal(outcome, 'continue')
  }
  // Once truly stalled with zero progress for 10+ minutes, timeout trips cleanly.
  for (let t = 15 * 60_000 + 5_000; t <= 26 * 60_000; t += 5_000) {
    const step = clock.observe(state, { now: t, answered: true, progressed: false, pollMs: 5_000, readTimeoutMs: 10_000 })
    state = step.clock
    outcome = step.outcome
    if (outcome === 'timeout') break
  }
  assert.equal(outcome, 'timeout')
})

test('Golden Journey 4: StudioResults renders actionable recovery buttons across all critical failure states', () => {
  const base = { project_id: 'p1', events: [], drafts: [], jobs: [], output_variants: [], analysis: null, generation: null }

  // Case 1: insufficient_quota shows recharge + diagnose
  const quota = renderStudioWith({
    ...base,
    analysis: { status: 'failed', error_code: 'insufficient_quota', provider: 'dashscope', billable_calls_before_failure: 0 },
  })
  assert.ok(quota.buttons.some(label => /充值|余额/.test(label)), `expected recharge/balance CTA, got ${quota.buttons}`)
  assert.ok(quota.buttons.some(label => /看看哪里不对/.test(label)))

  // Case 2: model_not_found with alternate provider offers switch_model; bad_endpoint routes to settings
  const missingModel = renderStudioWith({
    ...base,
    analysis: { status: 'failed', error_code: 'model_not_found', provider: 'dashscope' },
  }, {}, 2)
  assert.ok(missingModel.buttons.some(label => /换模型|切换|模型/.test(label)), `expected switch_model action, got ${missingModel.buttons}`)
  const badEndpoint = renderStudioWith({
    ...base,
    analysis: { status: 'failed', error_code: 'bad_endpoint', provider: 'compatible' },
  }, {}, 1)
  assert.ok(badEndpoint.buttons.some(label => /去设置|设置/.test(label)), `expected settings action, got ${badEndpoint.buttons}`)

  // Case 3: generation.status === 'failed' with preserved completed variant still shows failure summary & recovery
  const genFail = renderStudioWith({
    ...base,
    output_variants: [{ id: 'v1', status: 'completed', render_job_id: 'j1', strategy_id: 'douyin', branding: { outro_enabled: false } }],
    jobs: [{ job_id: 'j1', status: 'completed' }],
    generation: { status: 'failed', error_code: 'render_failed', completed_variant_count: 1 },
  })
  assert.ok(genFail.html.includes('ac-failure-summary'), 'generation failure summary must render even with preserved outputs')
  assert.ok(genFail.buttons.some(label => /查看|重试|继续/.test(label)), `expected view/retry recovery button, got ${genFail.buttons}`)
})

test('Stage 2 UI contracts: ProviderDetail subtraction, DefaultModels dedupe, masked key, and StudioDownloadLink reveal', () => {
  const detailSrc = fs.readFileSync(path.join(SRC_ROOT, 'features/settings/ProviderDetail.tsx'), 'utf8')
  assert.match(detailSrc, /测试并启用/)
  assert.match(detailSrc, /更多操作/)
  assert.match(detailSrc, /清除已保存密钥/)
  assert.match(detailSrc, /删除此服务商/)

  const fieldsSrc = fs.readFileSync(path.join(SRC_ROOT, 'features/settings/ProviderFields.tsx'), 'utf8')
  assert.match(fieldsSrc, /api_key_masked/)

  const modelsSrc = fs.readFileSync(path.join(SRC_ROOT, 'features/settings/DefaultModels.tsx'), 'utf8')
  assert.match(modelsSrc, /showSmartChoices/)
  assert.match(modelsSrc, /高级：显示智能回退选项/)

  const dlSrc = fs.readFileSync(path.join(SRC_ROOT, 'features/studio/StudioDownloadLink.tsx'), 'utf8')
  assert.match(dlSrc, /revealInFolder/)
  assert.match(dlSrc, /打开所在文件夹/)
})

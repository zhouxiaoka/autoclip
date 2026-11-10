const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const ts = require('typescript')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const { runInSandbox } = require('./vm-sandbox.cjs')

const translate = (key, values) => values
  ? String(key).replace(/\{\{\s*(\w+)\s*\}\}/g, (_, name) => values[name] == null ? '' : String(values[name]))
  : key
const TIMEOUT = '模型响应超时，请检查服务和网络后重试；本地模型请确认服务仍在运行。'
const RATE = '提供商限制了请求频率或额度，请检查配额并稍后重试。'

function renderCard(project, connectionCount) {
  const buttons = []
  const stubs = {
    '../i18n': { t: translate },
    'react-i18next': { useTranslation: () => ({}) },
    'react-router-dom': { useNavigate: () => () => {} },
    '../services/api': { projectApi: {} },
    '../features/studio/api': { studioApi: { retry: async () => ({}) } },
    '../utils/externalLinks': { openExternalLink() {} },
    './UnifiedStatusBar': { UnifiedStatusBar: () => null },
    './FeedbackDialog': { __esModule: true, default: () => null },
    '../features/studio/DiagnosePanel': { __esModule: true, default: () => null },
    '../features/studio/SwitchModelDialog': { __esModule: true, default: () => null },
    '../stores/useSimpleProgressStore': { useSimpleProgressStore: (select) => select({ getProgress: () => null }) },
    '../ui': {
      Btn: ({ children, variant }) => { buttons.push({ children, variant }); return React.createElement('button', {}, children) },
      Dialog: () => null,
      StatusDot: ({ label }) => React.createElement('span', {}, label),
      Icon: { Play: () => null, Refresh: () => null, Trash: () => null },
    },
  }
  function load(file) {
    const module = { exports: {} }
    const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, esModuleInterop: true },
    }).outputText
    runInSandbox(code, {
      module, exports: module.exports, console: { log() {}, error() {}, warn() {} },
      require: (id) => {
        if (id in stubs) return stubs[id]
        if (id === '@event-catalog' || id === '@failure-messages' || id === '@provider-presets' || id === '@provider-quality') {
          const rel = id === '@event-catalog' ? '../../backend/core/event_catalog.json'
            : id === '@failure-messages' ? '../../backend/core/failure_messages.json'
            : id === '@provider-presets' ? '../../backend/presets/provider_presets.json'
            : '../../backend/presets/provider_quality.json'
          const data = JSON.parse(fs.readFileSync(path.join(__dirname, rel), 'utf8'))
          return { default: data, __esModule: true }
        }
        if (id.startsWith('.')) {
          const base = path.resolve(path.dirname(file), id)
          const candidate = [`${base}.ts`, `${base}.tsx`, `${base}.js`, base].find(item => fs.existsSync(item) && fs.statSync(item).isFile())
          if (!candidate) throw new Error('cannot resolve ' + id)
          return load(candidate)
        }
        return require(id)
      },
    })
    return module.exports
  }
  const Card = load(path.join(__dirname, '../src/components/ProjectCard.tsx')).default
  const html = renderToStaticMarkup(React.createElement(Card, { project, connectionCount, onDelete() {} }))
  return { html, buttons }
}

function renderStudio(workspace, project, calls = [], retry, connectionCount = 1) {
  const buttons = []
  const empty = () => null
  const requireModule = (name) => {
    if (name === 'react' || name === 'react/jsx-runtime') return require(name)
    if (name === 'react-i18next') return { useTranslation() {} }
    if (name === 'react-router-dom') return { useNavigate: () => () => {}, useLocation: () => ({ search: '' }) }
    if (name === '../../i18n') return { t: translate, getLocale: () => 'zh' }
    if (name === '../../ui') return {
      Btn: (props) => { buttons.push(props); return React.createElement('button', null, props.children) },
      Section: ({ children }) => React.createElement('section', null, children),
      Dialog: empty,
      fmtDuration: String,
    }
    if (name === './useWorkspace') return { useWorkspace: () => ({ workspace, loaded: true, loading: false, refresh() {} }) }
    if (name === './api') return { studioApi: { source: () => '/test.mp4', retry: retry || (async (...args) => { calls.push(args); return {} }) }, errorText: String }
    if (name === './failureAction' || name === './failurePresentation' || name === './settingsReturn' || name === './studioProgress' || name === './importReadiness' || name === './browserCookieRecovery') {
      return require('./load-ts.cjs').loadTs(path.resolve(__dirname, '../src/features/studio/' + name.slice(2) + '.ts'))
    }
    if (name === '../../utils/llmFailure') return require('./load-ts.cjs').loadTs(path.resolve(__dirname, '../src/utils/llmFailure.ts'))
    if (name === '../../utils/timelineFailure') return require('./load-ts.cjs').loadTs(path.resolve(__dirname, '../src/utils/timelineFailure.ts'))
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
    if (name === './studio.css' || name === './quick-output.css') return {}
    return { default: empty }
  }
  const source = fs.readFileSync(path.join(__dirname, '../src/features/studio/StudioResults.tsx'), 'utf8')
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

function labels(buttons) {
  return buttons.map(button => button.children)
}

function pair(workspace, project, connectionCount = 1) {
  const card = renderCard({
    id: 'p1', name: 'Example', status: 'failed', created_at: '2026-09-30',
    error_message: project.error_message, error_code: project.error_code,
    processing_config: project.processing_config, total_clips: project.total_clips,
    settings: { smart_import: {} },
  }, connectionCount)
  const detail = renderStudio(workspace, project, [], undefined, connectionCount)
  return { card, detail }
}

function cta(buttons) {
  return buttons.filter(button => button.variant === 'cta').map(button => button.children)
}

test('the same stage conflict renders 制作 on the list and the detail', () => {
  const error = '渲染失败'
  const { card, detail } = pair({
    analysis: { status: 'failed', error, error_code: 'provider_error', failure_stage: 'screening', phase: 'production', run_id: 'run-1' },
    generation: { auto_start: true, status: 'failed', error, error_code: 'provider_error', failure_stage: 'render' },
    drafts: [], jobs: [], output_variants: [], attempts: [], events: [],
  }, {
    error_message: error, error_code: 'provider_error',
    processing_config: { failure_stage: 'render', studio_generation_status: 'failed', preserved_result_count: 0 },
  })
  for (const html of [card.html, detail.html]) {
    assert.match(html, /制作：渲染失败/)
    assert.doesNotMatch(html, /筛选：/)
  }
  assert.ok(labels(card.buttons).includes('重试'))
  assert.ok(labels(detail.buttons).includes('重试'))
})

test('a collection alone, or a completed export alone, is a kept result on both surfaces', () => {
  const base = {
    analysis: { status: 'failed', error: '后来失败', error_code: 'provider_error', failure_stage: 'render', run_id: 'run-1' },
    generation: { auto_start: true, status: 'failed', error: '后来失败', error_code: 'provider_error', failure_stage: 'render' },
    drafts: [], output_variants: [], attempts: [], events: [],
  }
  const collection = pair({ ...base, jobs: [] }, {
    error_message: '后来失败', error_code: 'provider_error', collections: [{ id: 'c1' }],
    processing_config: { failure_stage: 'render', preserved_result_count: 1, studio_generation_status: 'failed' },
  })
  const job = pair({ ...base, jobs: [{ job_id: 'j1', status: 'completed' }] }, {
    error_message: '后来失败', error_code: 'provider_error',
    processing_config: { failure_stage: 'render', preserved_result_count: 1, studio_generation_status: 'failed' },
  })
  for (const side of [collection.card, collection.detail, job.card, job.detail]) {
    assert.match(side.html, /已保留 1 条成片/)
    assert.ok(labels(side.buttons).includes('查看已有结果'))
    assert.equal(labels(side.buttons).includes('重试'), false)
  }
})

test('a same-run receipt secondary quota is the primary on both, and another run is ignored', () => {
  const matched = pair({
    analysis: { status: 'failed', error: TIMEOUT, error_code: 'timeout', failure_stage: 'analyze', run_id: 'run-1', phase: 'production' },
    generation: { auto_start: true, status: 'failed', error: '没有自动生成的成片，可选择备选片段继续生成', error_code: 'validation' },
    drafts: [], jobs: [], output_variants: [], events: [],
    attempts: [{ sequence: 1, state: 'failed', run_id: 'run-1', causes: [
      { code: 'timeout', stage: 'analyze', upstream: 'timeout' },
      { code: 'insufficient_quota', stage: 'analyze', upstream: 'insufficient_quota' },
    ] }],
  }, {
    error_message: TIMEOUT, error_code: 'timeout',
    processing_config: {
      failure_stage: 'analyze', upstream_error_type: 'timeout', preserved_result_count: 0,
      secondary_error_codes: ['insufficient_quota'],
      secondary_upstream_error_types: ['insufficient_quota'],
      secondary_failure_stages: ['analyze'],
      studio_generation_status: 'failed',
    },
  })
  for (const side of [matched.card, matched.detail]) {
    assert.ok(labels(side.buttons).includes('核对余额并测试连接'))
    assert.doesNotMatch(side.html, /建议再加一个服务商/)
  }
  const other = pair({
    analysis: { status: 'failed', error: RATE, error_code: 'rate_limited', failure_stage: 'screening', upstream_error_type: 'rate_limited', run_id: 'run-1' },
    generation: { auto_start: true, status: 'failed', error: RATE, error_code: 'rate_limited', failure_stage: 'render', upstream_error_type: 'rate_limited' },
    drafts: [], jobs: [], output_variants: [], events: [],
    attempts: [{ sequence: 1, state: 'failed', run_id: 'other-run', causes: [
      { code: 'invalid_key', stage: 'analyze', upstream: 'invalid_key' },
    ] }],
  }, {
    error_message: RATE, error_code: 'rate_limited',
    processing_config: { failure_stage: 'render', upstream_error_type: 'rate_limited', preserved_result_count: 0, studio_generation_status: 'failed' },
  })
  for (const side of [other.card, other.detail]) {
    assert.match(side.html, /制作：/)
    assert.doesNotMatch(side.html, /筛选：/)
    assert.doesNotMatch(side.html, /API Key 无效/)
    assert.ok(labels(side.buttons).includes('重试'))
    assert.equal(labels(side.buttons).includes('去设置'), false)
  }
})

test('a chosen connection failure without a stage does not borrow the analysis download stage', () => {
  const error = '无法连接模型服务。请检查 API 地址和网络；如果是本地模型，请先启动服务再重试。'
  const workspace = {
    analysis: { status: 'failed', error, error_code: 'connection', failure_stage: 'download', run_id: 'run-1' },
    generation: { auto_start: true, status: 'failed', error, error_code: 'connection' },
    drafts: [], jobs: [], output_variants: [], events: [], attempts: [],
  }
  const project = {
    error_message: error, error_code: 'connection',
    processing_config: { studio_generation_status: 'failed', preserved_result_count: 0 },
  }
  const expected = { 0: '重试', 1: '重试', 2: '换模型重试' }
  for (const count of [0, 1, 2]) {
    const { card, detail } = pair(workspace, project, count)
    assert.deepEqual(cta(card.buttons), [expected[count]], 'list ' + count)
    assert.deepEqual(cta(detail.buttons), [expected[count]], 'detail ' + count)
    assert.equal(card.html.includes('下载：'), false, 'list ' + count)
    assert.equal(detail.html.includes('下载：'), false, 'detail ' + count)
  }
  const receiptWorkspace = {
    ...workspace,
    attempts: [{ sequence: 1, state: 'failed', run_id: 'run-1', causes: [{ code: 'connection', upstream: 'connection' }] }],
  }
  const withReceipt = pair(receiptWorkspace, project, 2)
  assert.deepEqual(cta(withReceipt.card.buttons), ['换模型重试'])
  assert.deepEqual(cta(withReceipt.detail.buttons), ['换模型重试'])
  assert.equal(withReceipt.card.html.includes('下载：'), false)
  assert.equal(withReceipt.detail.html.includes('下载：'), false)
  const wrongRun = pair({
    ...workspace,
    attempts: [{ sequence: 1, state: 'failed', run_id: 'other-run', causes: [{ code: 'connection', stage: 'download', upstream: 'connection' }] }],
  }, project, 2)
  assert.deepEqual(cta(wrongRun.card.buttons), ['换模型重试'])
  assert.deepEqual(cta(wrongRun.detail.buttons), ['换模型重试'])
  assert.equal(wrongRun.detail.html.includes('下载：'), false)
  const download = '下载视频时网络超时或中断。请检查网络后重试，或换一个视频链接。'
  const explicit = pair({
    analysis: { status: 'failed', error: download, error_code: 'connection', failure_stage: 'screening', run_id: 'run-1' },
    generation: { auto_start: true, status: 'failed', error: download, error_code: 'connection', failure_stage: 'download' },
    drafts: [], jobs: [], output_variants: [], events: [], attempts: [],
  }, {
    error_message: download, error_code: 'connection',
    processing_config: { failure_stage: 'download', studio_generation_status: 'failed', preserved_result_count: 0 },
  }, 2)
  assert.match(explicit.card.html, /下载：/)
  assert.match(explicit.detail.html, /下载：/)
  assert.deepEqual(cta(explicit.card.buttons), ['重试'])
  assert.deepEqual(cta(explicit.detail.buttons), ['重试'])
})

test('detail retry clicks in the same turn share one request', async () => {
  const calls = []
  let release
  const pending = new Promise(resolve => { release = resolve })
  const detail = renderStudio({
    analysis: { status: 'failed', error: '中断', error_code: 'service_restarted', failure_stage: 'render' },
    generation: { auto_start: true, status: 'failed', error: '中断', error_code: 'service_restarted', failure_stage: 'render' },
    drafts: [], jobs: [], output_variants: [], attempts: [], events: [],
  }, {}, calls, async (...args) => { calls.push(args); await pending })
  const retry = detail.buttons.find(button => button.children === '重试制作')
  const first = retry.onClick()
  const second = retry.onClick()
  release()
  await first
  await second
  assert.equal(calls.length, 1)
})

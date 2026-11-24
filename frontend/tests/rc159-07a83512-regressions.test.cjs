const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const ts = require('typescript')
const { loadTs } = require('./load-ts.cjs')
const { runInSandbox } = require('./vm-sandbox.cjs')

const read = rel => fs.readFileSync(path.join(__dirname, '..', rel), 'utf8')

test('ExportCover shows reference-frame opt-out notice even when design_mode is local crop_grade_text_only', () => {
  const mod = loadTs(path.join(__dirname, '../src/features/studio/ExportCover.tsx'), {
    react: {},
    antd: { message: {} },
    '../../i18n': { t: s => s },
    '../../publish/coverApi': { coverApi: {} },
    '../../services/api': { default: { defaults: { baseURL: '' } } },
    '../../ui': { Btn: () => null, Dialog: () => null },
    './api': { exportCoverSlot: () => 'douyin', studioApi: {} },
    './nativeDownload': { isDesktopDownload: () => false, saveLocalFile: async () => {} },
  })
  // Mac case: model enabled & configured, allow_send_frame=false, crop_grade_text_only -> view.warning is null
  assert.equal(
    mod.coverWarningMessage(null, { enabled: true, configured: true, allow_send_frame: false }),
    '已关闭上传参考帧，当前使用本地排版封面',
  )
  // Opt-in enabled -> no warning
  assert.equal(
    mod.coverWarningMessage(null, { enabled: true, configured: true, allow_send_frame: true }),
    '',
  )
  // Cover disabled -> no warning
  assert.equal(
    mod.coverWarningMessage(null, { enabled: false, configured: true, allow_send_frame: false }),
    '',
  )
  // Real failure still wins over opt-out config
  assert.equal(
    mod.coverWarningMessage('image_service_unavailable', { enabled: true, configured: true, allow_send_frame: false }),
    '生图失败，已改成本地排版或截帧',
  )
  const src = read('src/features/studio/ExportCover.tsx')
  assert.match(src, /setWarning\(coverWarningMessage\(view\?\.warning, cfg\)\)/)
})

function renderStudioResultsForRemake(project) {
  const ROOT = path.resolve(__dirname)
  const empty = () => null
  const navigated = []
  const stashed = []
  const buttons = []
  const setRemakingCalls = []
  const workspace = {
    drafts: [{ id: 'd1', revision: 1, title: 'T1', aspect: 'portrait', scenes: [] }],
    jobs: [{ job_id: 'j1', draft_id: 'd1', revision: 1, status: 'completed', created_at: '2026-11-22T00:00:00Z' }],
    events: [],
    output_variants: [{ id: 'v1', strategy_id: 'douyin', draft_id: 'd1', draft_revision: 1, render_job_id: 'j1', status: 'completed', branding: { outro_enabled: true } }],
    generation: { auto_start: true, status: 'completed', requested_platforms: ['douyin'] },
    analysis: { status: 'completed', phase: 'rendering' },
  }
  const origUseState = React.useState
  let stateIndex = 0
  const patchedReact = {
    ...React,
    useState(init) {
      const idx = stateIndex++
      const [val, setVal] = origUseState.call(React, init)
      if (idx === 0) {
        return [val, next => { setRemakingCalls.push(next); return setVal(next) }]
      }
      return [val, setVal]
    },
  }
  const moduleRequire = name => {
    if (name === 'react') return patchedReact
    if (name === 'react/jsx-runtime') return require(name)
    if (name === 'react-i18next') return { useTranslation() {} }
    if (name === 'react-router-dom') return { useNavigate: () => to => navigated.push(to), useLocation: () => ({ search: '' }) }
    if (name === '../../i18n') return { t: v => v, getLocale: () => 'zh-CN' }
    if (name === '../../ui') {
      return {
        Btn: p => {
          buttons.push(p)
          return React.createElement('button', null, p.children)
        },
        Section: ({ right, children }) => React.createElement('section', null, right, children),
        Dialog: empty,
        fmtDuration: String,
      }
    }
    if (name === './useWorkspace') return { useWorkspace: () => ({ workspace, loaded: true, loading: false, refresh() {} }) }
    if (name === './api') return { studioApi: { source: () => '/s' }, errorText: String }
    if (name === './OutputVariantCard') return { default: empty }
    if (name === './DraftResultCard') return { default: empty }
    if (name === './ExportHistory') return { default: empty }
    if (name === './PlanEditDialog') return { default: empty }
    if (name === './PlanSummary') return { default: empty }
    if (name === './DiagnosePanel') return { default: empty }
    if (name === './SwitchModelDialog') return { default: empty }
    if (name === '../diagnostics/FailureHint') return { default: empty }
    if (name === '../diagnostics/failureHintPolicy') return { nextLiveFailure: p => ({ previous: p, failed: null }) }
    if (name === '../../utils/externalLinks') return { openExternalLink: async () => {} }
    if (name === '../../utils/llmFailure') return loadTs(path.resolve(ROOT, '../src/utils/llmFailure.ts'))
    if (name === '../../utils/timelineFailure') return loadTs(path.resolve(ROOT, '../src/utils/timelineFailure.ts'))
    if (name === './importReadiness') return loadTs(path.resolve(ROOT, '../src/features/studio/importReadiness.ts'))
    if (name === './browserCookieRecovery') return loadTs(path.resolve(ROOT, '../src/features/studio/browserCookieRecovery.ts'))
    if (name === './settingsReturn') return loadTs(path.resolve(ROOT, '../src/features/studio/settingsReturn.ts'))
    if (name === './failureAction') return loadTs(path.resolve(ROOT, '../src/features/studio/failureAction.ts'))
    if (name === './failurePresentation') return loadTs(path.resolve(ROOT, '../src/features/studio/failurePresentation.ts'))
    if (name === './studioProgress') return loadTs(path.resolve(ROOT, '../src/features/studio/studioProgress.ts'))
    if (name === './switchModelOptions') return { listSwitchModelOptions: () => [], usableConnectionCount: () => 1 }
    if (name === './platformLabel') return { platformLabel: String }
    if (name === '../../analytics/flags') return { flagEnabled: () => false, flagAssigned: () => false }
    if (name === '../../analytics/studio') return { trackLegacyEntry() {} }
    if (name === './legacyEntrypoints') return { legacyEntrypointsHidden: () => false }
    if (name === './platformMemory') {
      return {
        dismissMorePlatformBanner() {},
        morePlatformBannerSeen: () => false,
        stashReuseImport: payload => stashed.push(payload),
        suggestAnotherPlatform: () => 'xiaohongshu',
      }
    }
    if (name === './overrides') return { followOutputLeave: () => () => {} }
    if (name === './completionNotice') return { noticeCopy: () => '' }
    if (name === './etaModel') return { recordSuccess() {} }
    if (name === '../settings/modelSettingsApi') return { modelSettingsApi: { get: async () => ({ connections: [], analysis: {} }) } }
    if (name === '../settings/modelSettingsLogic') return { forSave: x => x }
    if (name === '../settings/modelDefaults') return { syncFollowingCover: x => x }
    if (name === '../../analytics/observer') return { workflow: { adoptOpenAttempt() {} } }
    if (name === './noticeRuntime') return { clearCompletionBadge() {}, subscribeCompletionNotice: () => () => {} }
    if (name.endsWith('.css')) return {}
    return {}
  }
  const out = {}
  const src = read('src/features/studio/StudioResults.tsx')
  runInSandbox(
    ts.transpileModule(src, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX } }).outputText,
    { exports: out, require: moduleRequire, URLSearchParams },
  )
  renderToStaticMarkup(React.createElement(out.default, { project, onCreateCollection() {}, onReload() {} }))
  return { buttons, navigated, stashed, setRemakingCalls }
}

test('StudioResults opens in-place remake dialog for both local-file and link projects with unified 重做 copy', () => {
  // Local-file project: opens in-place PlanEditDialog, NEVER jumps to '/'
  const local = renderStudioResultsForRemake({
    id: 'proj-local',
    name: 'qa684-20s',
    status: 'completed',
    source_url: null,
    source_file: 'qa684-20s.mp4',
    settings: { smart_import: { goal: 'content' } },
  })
  const localBtn = local.buttons.find(b => b.children === '重做')
  assert.ok(localBtn, 'local completed automatic project should expose 重做')
  localBtn.onClick()
  assert.equal(local.setRemakingCalls.length, 1)
  assert.deepEqual(local.navigated, [])
  assert.deepEqual(local.stashed, [])

  // URL-imported project: ALSO stays in-place and opens the unified remake dialog
  const link = renderStudioResultsForRemake({
    id: 'proj-url',
    name: 'yt-clip',
    status: 'completed',
    source_url: 'https://www.youtube.com/watch?v=abc123',
    settings: { smart_import: { goal: 'content' } },
  })
  const linkBtn = link.buttons.find(b => b.children === '重做')
  assert.ok(linkBtn, 'URL completed automatic project should expose 重做')
  linkBtn.onClick()
  assert.equal(link.setRemakingCalls.length, 1)
  assert.deepEqual(link.navigated, [])
  assert.deepEqual(link.stashed, [])

  // Header remake button respects running analysis lock (#627)
  const resultsSrc = read('src/features/studio/StudioResults.tsx')
  assert.match(
    resultsSrc,
    /disabled=\{loading \|\| workspace\.analysis\?\.status === 'running'\} onClick=\{\(\) => openRemake\([^\n]+\)\}>\{t\('重做'\)\}/,
  )
})

test('ExportHistory displays matched variant post title consistently with result card and falls back to job title', () => {
  const root = path.resolve(__dirname, '../src/features/studio')
  const exportsObj = {}
  const mocks = {
    'react/jsx-runtime': require('react/jsx-runtime'),
    'react-i18next': { useTranslation: () => ({ t: s => s }) },
    '../../i18n': { t: s => s, getLocale: () => 'zh' },
    '../../ui': { Dialog: p => React.createElement('section', null, p.children), ProgressLine: () => null },
    'react-router-dom': { Link: p => React.createElement('a', { href: p.to }, p.children) },
    './outputVariantPublish': loadTs(path.join(root, 'outputVariantPublish.ts')),
    './StudioDownloadLink': { default: () => null },
  }
  runInSandbox(
    ts.transpileModule(read('src/features/studio/ExportHistory.tsx'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
    }).outputText,
    { exports: exportsObj, require: id => mocks[id] },
  )
  const ExportHistory = exportsObj.default
  const jobs = [
    { job_id: 'j1', draft_id: 'd1', revision: 1, title: '过去12个月不佳，主要是我的错', status: 'completed', created_at: '2026-11-22T08:00:00Z' },
    { job_id: 'j2', draft_id: 'd1', revision: 2, title: '模糊背景第二版', status: 'completed', created_at: '2026-11-22T09:00:00Z' },
  ]
  const variants = [
    { id: 'v1', strategy_id: 'douyin', draft_id: 'd1', draft_revision: 1, render_job_id: 'j1', status: 'completed', post: { title: '过去12个月不是最好的，主要是我的错', description: '', tags: [] } },
  ]
  const html = renderToStaticMarkup(React.createElement(ExportHistory, { projectId: 'p1', jobs, variants, open: true, onClose() {} }))
  assert.ok(html.includes('<b>过去12个月不是最好的，主要是我的错</b>'), 'variant-linked job should show post.title')
  assert.ok(!html.includes('<b>过去12个月不佳，主要是我的错</b>'), 'stale draft title should not diverge from card')
  assert.ok(html.includes('variant=v1'), 'variant-linked publish link should carry variant id')
  assert.ok(html.includes('<b>模糊背景第二版</b>'), 'standalone export keeps its own job.title')

  const resultsSrc = read('src/features/studio/StudioResults.tsx')
  assert.match(resultsSrc, /<ExportHistory projectId=\{project\.id\} jobs=\{workspace\.jobs\} variants=\{workspace\.output_variants\}/)
})

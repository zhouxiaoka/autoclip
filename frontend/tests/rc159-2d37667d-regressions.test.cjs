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

function renderStudioResults(workspace, projectOverrides = {}) {
  const ROOT = path.resolve(__dirname)
  const empty = () => null
  const buttons = []
  const variantCards = []
  const draftCards = []
  let sectionCount = null
  const project = {
    id: 'proj-local',
    name: 'qa684-20s',
    status: 'completed',
    source_url: null,
    source_file: 'qa684-20s.mp4',
    settings: { smart_import: { goal: 'content' } },
    ...projectOverrides,
  }
  const moduleRequire = name => {
    if (name === 'react') return React
    if (name === 'react/jsx-runtime') return require(name)
    if (name === 'react-i18next') return { useTranslation() {} }
    if (name === 'react-router-dom') return { useNavigate: () => () => {}, useLocation: () => ({ search: '' }) }
    if (name === '../../i18n') return { t: v => v, getLocale: () => 'zh-CN' }
    if (name === '../../ui') {
      return {
        Btn: p => {
          buttons.push(p)
          return React.createElement('button', null, p.children)
        },
        Section: ({ count, right, children }) => {
          sectionCount = count
          return React.createElement('section', { 'data-count': String(count) }, right, children)
        },
        Dialog: empty,
        fmtDuration: String,
      }
    }
    if (name === './useWorkspace') return { useWorkspace: () => ({ workspace, loaded: true, loading: false, refresh() {} }) }
    if (name === './api') return { studioApi: { source: () => '/s' }, errorText: String }
    if (name === './OutputVariantCard') {
      return {
        default: props => {
          variantCards.push(props)
          return React.createElement('div', { 'data-card': `variant:${props.variant.id}` })
        },
      }
    }
    if (name === './DraftResultCard') {
      return {
        default: props => {
          draftCards.push(props)
          return React.createElement('div', { 'data-card': `draft:${props.draft.id}` })
        },
      }
    }
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
        morePlatformBannerSeen: () => true,
        stashReuseImport() {},
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
  const html = renderToStaticMarkup(React.createElement(out.default, { project, onCreateCollection() {}, onReload() {} }))
  return { html, buttons, variantCards, draftCards, sectionCount }
}

test('submitting remake keeps existing OutputVariantCard intact instead of flipping the page to DraftResultCard', () => {
  const baseVariant = {
    id: 'v1',
    strategy_id: 'douyin',
    draft_id: 'd1',
    draft_revision: 1,
    render_job_id: 'j1',
    status: 'completed',
    post: { title: '过去12个月不是最好的，主要是我的错', description: '', tags: [] },
    branding: { outro_enabled: true },
  }
  const baseDraft = { id: 'd1', revision: 1, title: '过去12个月不佳，主要是我的错', aspect: 'portrait', scenes: [] }
  const baseJob = { job_id: 'j1', draft_id: 'd1', revision: 1, status: 'completed', created_at: '2026-11-22T00:00:00Z' }

  // 1. Before remake: automatic completed state
  const before = renderStudioResults({
    drafts: [baseDraft],
    jobs: [baseJob],
    events: [],
    output_variants: [baseVariant],
    generation: { auto_start: true, status: 'completed', requested_platforms: ['douyin'] },
    analysis: { status: 'completed', phase: 'rendering' },
  })
  assert.deepEqual(before.variantCards.map(c => c.variant.id), ['v1'])
  assert.deepEqual(before.draftCards.map(c => c.draft.id), [])
  assert.equal(before.sectionCount, 1)
  assert.ok(before.buttons.some(b => b.children === '重做'), 'header remake button should use concise 重做')
  assert.ok(!before.buttons.some(b => b.children === '用同一素材再做一个'), 'header should not use verbose 用同一素材再做一个')

  // 2. Immediately after submitting remake (auto_start flips to false, no new draft yet):
  // MUST keep rendering v1 as OutputVariantCard, NOT flip it into DraftResultCard!
  const afterSubmit = renderStudioResults({
    drafts: [baseDraft],
    jobs: [baseJob],
    events: [],
    output_variants: [baseVariant],
    generation: { auto_start: false, status: 'screening', requested_platforms: ['douyin'] },
    analysis: { status: 'running', phase: 'screening' },
  })
  assert.deepEqual(afterSubmit.variantCards.map(c => c.variant.id), ['v1'])
  assert.deepEqual(afterSubmit.draftCards.map(c => c.draft.id), [])
  assert.equal(afterSubmit.sectionCount, 1)
  assert.ok(afterSubmit.buttons.some(b => b.children === '重做'), 'header button stays 重做 after submitting remake')

  // 3. After remake creates a new standalone draft d2:
  // Original v1 stays OutputVariantCard; new d2 appends as DraftResultCard (no duplicate d1).
  const afterNewDraft = renderStudioResults({
    drafts: [baseDraft, { id: 'd2', revision: 1, title: '新方案草稿', aspect: 'portrait', scenes: [] }],
    jobs: [baseJob],
    events: [],
    output_variants: [baseVariant],
    generation: { auto_start: false, status: 'completed', requested_platforms: ['douyin'] },
    analysis: { status: 'completed', phase: 'production' },
  })
  assert.deepEqual(afterNewDraft.variantCards.map(c => c.variant.id), ['v1'])
  assert.deepEqual(afterNewDraft.draftCards.map(c => c.draft.id), ['d2'])
  assert.equal(afterNewDraft.sectionCount, 2)
})

test('StudioDownloadLink reveal button uses dedicated full-row class so card actions stay 2-up without squeezing', () => {
  const dlSrc = read('src/features/studio/StudioDownloadLink.tsx')
  assert.match(dlSrc, /className="studio-link studio-reveal-link"/)
  assert.match(dlSrc, /data-testid="reveal-in-folder-btn"/)

  const css = read('src/features/studio/quick-output.css')
  assert.match(css, /\.studio-output-card \.ac-card-actions > \.studio-reveal-link\s*\{[\s\S]*grid-column:\s*1 \/ -1/)
})

test('ExportCover consistently shows reference-frame opt-out notice even when view.warning is needs_source_validation', () => {
  const coverSrc = read('src/features/studio/ExportCover.tsx')
  assert.match(coverSrc, /export function coverStatusMessages\(/)
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
  const optOutCfg = { enabled: true, configured: true, allow_send_frame: false }
  const msgs = (warning, cfg) => Array.from(mod.coverStatusMessages(warning, cfg))
  // View Cover surface with needs_source_validation AND opt-out enabled -> MUST include opt-out notice without hiding source-frame status
  assert.deepEqual(msgs('needs_source_validation', optOutCfg), [
    '当前是截帧封面',
    '已关闭上传参考帧，当前使用本地排版封面',
  ])
  // Exported dialog / crop_grade_text_only with opt-out enabled -> single opt-out notice, no duplicate
  assert.deepEqual(msgs(null, optOutCfg), ['已关闭上传参考帧，当前使用本地排版封面'])
  assert.deepEqual(msgs('frame_sending_disabled', optOutCfg), ['已关闭上传参考帧，当前使用本地排版封面'])
  // Without opt-out config -> only source-frame notice
  assert.deepEqual(msgs('needs_source_validation', { enabled: true, configured: true, allow_send_frame: true }), [
    '当前是截帧封面',
  ])
  // Real failure -> never show opt-out notice alongside failure
  assert.deepEqual(msgs('image_service_unavailable', optOutCfg), [
    '生图失败，已改成本地排版或截帧',
  ])
})

test('ExportCover sends visible confirmed title and exposes allow_reference_once for both variant and standalone covers', () => {
  const coverSrc = read('src/features/studio/ExportCover.tsx')
  assert.match(coverSrc, /export function resolvedCoverTitle\(/)
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
  // Unedited input on existing cover -> confirms savedTitle so backend treats it as locked instead of needs_source_validation
  assert.equal(mod.resolvedCoverTitle(null, '奥特曼复盘：我们产品做得太多了', 'fallback'), '奥特曼复盘：我们产品做得太多了')
  // Unedited input before first cover exists (savedTitle empty, placeholder=job.title) -> confirms job.title
  assert.equal(mod.resolvedCoverTitle(null, '', '奥特曼复盘：我们产品做得太多了'), '奥特曼复盘：我们产品做得太多了')
  // Explicitly edited input -> sends trimmed value
  assert.equal(mod.resolvedCoverTitle('  自定义封面标题  ', 'old', 'job'), '自定义封面标题')
  // Explicitly cleared input -> undefined (does not override with stale title)
  assert.equal(mod.resolvedCoverTitle('', 'old', 'job'), undefined)

  // Both variant and standalone covers must be able to opt-in once when global allow_send_frame is false
  assert.doesNotMatch(coverSrc, /!variant\s*&&\s*askReference/)
  assert.match(coverSrc, /askReference\s*&&\s*design\.mode === 'editorial_edit'/)
  assert.match(coverSrc, /redesignVariantCover\(projectId,\s*variant\.id,\s*\{\s*design,\s*title,\s*allow_reference_once:\s*referenceOnce\s*\}\)/)
})

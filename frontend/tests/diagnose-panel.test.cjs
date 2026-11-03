const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const fs = require('node:fs')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const ts = require('typescript')
const { runInSandbox } = require('./vm-sandbox.cjs')
const { loadTs } = require('./load-ts.cjs')

const navigated = []
const actions = []
const opened = []

function loadPanel() {
  const file = path.resolve(__dirname, '../src/features/studio/DiagnosePanel.tsx')
  const js = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
    fileName: file,
  }).outputText
  const exportsObject = {}
  runInSandbox(js, {
    exports: exportsObject,
    module: { exports: exportsObject },
    require: (id) => {
      if (id === 'react' || id === 'react/jsx-runtime') return require(id)
      if (id === 'react-router-dom') return { useNavigate: () => to => navigated.push(to) }
      if (id === '../../i18n') return { t: value => value }
      if (id === '../../ui') return {
        Btn: props => React.createElement('button', { onClick: props.onClick, 'data-variant': props.variant || '' }, props.children),
        Dialog: ({ open, title, description, footer, children }) => open ? React.createElement('section', null, React.createElement('h3', null, title), React.createElement('p', null, description), children, footer) : null,
        StatusDot: ({ label, tone }) => React.createElement('span', { 'data-tone': tone }, label),
      }
      if (id === '../../analytics/studio') return {
        trackDiagnoseOpened(code, suggestion) { opened.push({ code, suggestion }) },
        trackDiagnoseAction(action) { actions.push(action) },
      }
      if (id === './api') return { studioApi: { readiness: async () => null } }
      if (id === './failureAction') return loadTs(path.resolve(__dirname, '../src/features/studio/failureAction.ts'))
      if (id === './openExample') return { openExample: async navigate => { await navigate('/project/sample') } }
      throw new Error(id)
    },
  })
  return exportsObject
}

test('X1 diagnose panel shows four readiness rows, the failure, one suggestion and the sample', () => {
  const panel = loadPanel()
  const rows = panel.readinessRows({
    analysis_mode: 'auto',
    ready: false,
    checks: {
      analysis: { ok: true, code: 'ok', repair: 'none' },
      transcription: { ok: false, code: 'whisper_not_installed', repair: 'install_whisper' },
      visual: { ok: true, code: 'ok', repair: 'none' },
    },
  })
  assert.equal(rows.map(row => `${row.key}:${row.status}`).join('|'), 'analysis:已就绪|transcription:还没准备好|visual:已就绪|ffmpeg:还在确认')
  const settings = []
  const html = renderToStaticMarkup(React.createElement(panel.default, {
    open: true,
    onClose() {},
    info: { error_code: 'timeout', failure_stage: 'analyze', error: '模型响应超时，请检查服务和网络后重试；本地模型请确认服务仍在运行。' },
    onSettings: destination => settings.push(destination),
    readiness: { analysis_mode: 'auto', ready: false, checks: { analysis: { ok: false, code: 'not_configured', repair: 'settings_ai' } } },
  }))
  assert.match(html, /看看哪里不对/)
  assert.match(html, /分析模型 · 还没准备好/)
  assert.match(html, /转写 · 还在确认/)
  assert.match(html, /画面理解 · 还在确认/)
  assert.match(html, /视频处理 · 还在确认/)
  assert.match(html, /分析：/)
  assert.match(html, /换模型重试/)
  assert.match(html, /用示例视频试一次/)
  assert.match(html, /同一类错误已经连续出现/)
  const source = fs.readFileSync(path.resolve(__dirname, '../src/features/studio/DiagnosePanel.tsx'), 'utf8')
  assert.match(source, /openExample/)
  assert.match(source, /trackDiagnoseOpened/)
  assert.match(source, /trackDiagnoseAction/)
  assert.equal(settings.length, 0)
})

test('X1 diagnose telemetry keeps error_code and the suggestion id', () => {
  const catalog = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../docs/analytics/event_catalog.json'), 'utf8'))
  const catalogApi = loadTs(path.resolve(__dirname, '../src/analytics/eventCatalog.ts'))
  const workflow = loadTs(path.resolve(__dirname, '../src/analytics/workflow.ts'))
  const events = []
  const studio = loadTs(path.resolve(__dirname, '../src/analytics/studio.ts'), {
    './posthog': { captureBusinessEvent: (event, props) => { events.push({ event, props }); return true } },
    './observer': { workflow: { generation: () => 1, active: () => true, context: () => ({}) } },
    './workflow': workflow,
    './flags': { flagAssigned: () => false },
  })
  studio.trackDiagnoseOpened('timeout', 'switch_model')
  studio.trackDiagnoseAction('example')
  studio.trackDiagnoseOpened('not_a_code', 'nope')
  assert.equal(events[0].event, 'diagnose_opened')
  assert.equal(events[0].props.error_code, 'timeout')
  assert.equal(events[0].props.suggestion, 'switch_model')
  assert.equal(catalogApi.validateEvent(events[0].event, events[0].props, catalog).join(';'), '')
  assert.equal(events[1].event, 'diagnose_action')
  assert.equal(events[1].props.action, 'example')
  assert.equal(catalogApi.validateEvent(events[1].event, events[1].props, catalog).join(';'), '')
  assert.equal(events[2].props.error_code, 'unknown')
  assert.equal(events[2].props.suggestion, 'none')
})

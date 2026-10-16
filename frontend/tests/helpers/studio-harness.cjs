// Shared harness: real tracker + real studio api + real StudioResults (used by tests and the DuckDB flow script).
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), ts = require('typescript')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const { loadTs } = require('../load-ts.cjs')
const ROOT = path.resolve(__dirname, '..')

function setup() {
  const workflow = loadTs(path.resolve(ROOT, '../src/analytics/workflow.ts'))
  const events = []
  const tracker = new workflow.WorkflowTracker({ getItem: () => null, setItem() {}, removeItem() {} },
    () => true, (event, props) => { events.push({ event, props }); return true })
  const posts = []
  const api = loadTs(path.resolve(ROOT, '../src/features/studio/api.ts'), {
    '../../analytics/posthog': { captureBusinessEvent() {} },
    '../../analytics/workflow': workflow,
    '../../analytics/studio': {
      observeStudioOperation: async (_n, action, accepted = () => {}, props = {}) => { const r = await action(); accepted(r, { ...props }); return r },
      studioImportProperties: () => ({}), studioGoals: () => ({}), observeStudioWorkspace: () => {},
    },
    '../../analytics/observer': { workflow: tracker },
    '../../services/api': { default: { defaults: { baseURL: '' }, post: async (url) => { posts.push(url); return { id: url.split('/').at(-2), status: 'rendering', render_job_id: 'job-2' } }, put: async () => ({}), get: async () => ({}) }, __esModule: true },
    './noticeRuntime': { noteWorkspaceCompletion() {} },
    './subtitleState': { effectiveSubtitles: x => x },
  })
  return { tracker, events, posts, studioApi: api.studioApi }
}

function renderResults(workspace, studioApi, cards) {
  const empty = () => null
  const moduleRequire = (name) => {
    if (name === 'react' || name === 'react/jsx-runtime') return require(name)
    if (name === 'react-i18next') return { useTranslation() {} }
    if (name === 'react-router-dom') return { useNavigate: () => () => {}, useLocation: () => ({ search: '' }) }
    if (name === '../../i18n') return { t: v => v }
    if (name === '../../ui') return { Btn: p => React.createElement('button', null, p.children), Section: ({ children }) => React.createElement('section', null, children), Dialog: empty, fmtDuration: String }
    if (name === './useWorkspace') return { useWorkspace: () => ({ workspace, loaded: true, loading: false, refresh() {} }) }
    if (name === './api') return { studioApi, errorText: String }
    if (name === './OutputVariantCard') return { default: props => { cards.push(props); return null } }
    if (name === '../../utils/llmFailure') return loadTs(path.resolve(ROOT, '../src/utils/llmFailure.ts'))
    if (name === './settingsReturn') return loadTs(path.resolve(ROOT, '../src/features/studio/settingsReturn.ts'))
    if (name === './failureAction') return loadTs(path.resolve(ROOT, '../src/features/studio/failureAction.ts'))
    if (name === './platformLabel') return { platformLabel: String }
    if (name === '../../analytics/flags') return { flagEnabled: () => false, flagAssigned: () => false }
    if (name === '../../analytics/studio') return { trackLegacyEntry() {} }
    if (name === './legacyEntrypoints') return { legacyEntrypointsHidden: () => false }
    return { default: empty }
  }
  const exportsObject = {}
  const source = fs.readFileSync(path.join(ROOT, '../src/features/studio/StudioResults.tsx'), 'utf8')
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX } }).outputText, { exports: exportsObject, require: moduleRequire, console, URLSearchParams })
  renderToStaticMarkup(React.createElement(exportsObject.default, { project: { id: 'p1', status: 'completed', settings: { smart_import: {} }, clips: [], collections: [] }, onCreateCollection() {}, onReload() {} }))
}


module.exports = { setup, renderResults }

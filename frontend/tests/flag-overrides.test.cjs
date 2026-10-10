const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

const jsx = (type, props) => ({ type, props })

function transpile(file) {
  return ts.transpileModule(fs.readFileSync(file, 'utf8').replaceAll('import.meta.env', '__env'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
  }).outputText
}

function loadPanel(dev) {
  const file = path.join(__dirname, '../src/features/settings/FlagOverrides.tsx')
  const exports = {}
  vm.runInNewContext(transpile(file), {
    exports, module: { exports }, console,
    __env: { DEV: dev },
    require: (id) => {
      if (id === 'react') return { useSyncExternalStore: (_subscribe, get) => get() }
      if (id === 'react/jsx-runtime') return { jsx, jsxs: jsx }
      if (id === '../../i18n') return { t: value => value }
      if (id === '../../ui') return { Row: 'Row', Section: 'Section' }
      if (id === '../../analytics/flags') return {
        FLAG_DEFAULTS: { remember_platforms: false },
        FLAG_NAMES: ['remember_platforms'],
        FLAG_SPEC: { remember_platforms: { kind: 'boolean' } },
        flagOverride: () => null,
        setFlagOverride() {},
        subscribeFlags: () => () => {},
      }
      throw new Error(`Unexpected dependency: ${id}`)
    },
  }, { filename: file })
  return exports
}

function walk(node, visit) {
  if (!node || typeof node !== 'object') return false
  if (visit(node)) return true
  const children = node.props?.children
  const list = Array.isArray(children) ? children.flat(8) : [children]
  return list.some(child => walk(child, visit))
}

function containsTitle(node, title) {
  return walk(node, item => {
    if (typeof item.type === 'function') return containsTitle(item.type(item.props), title)
    return item.props?.title === title
  })
}

function loadAppSection(dev) {
  const panel = loadPanel(dev)
  const file = path.join(__dirname, '../src/pages/SettingsPage.tsx')
  const exports = {}
  vm.runInNewContext(transpile(file) + '\nexports.testAppSection = AppSection;', {
    exports, console,
    __env: { DEV: dev },
    require: (name) => {
      if (name === '../features/settings/FlagOverrides') return panel
      if (name === 'react') return { useEffect() {}, useState: value => [value, () => {}], useRef: value => ({ current: value }), useMemo: value => value }
      if (name === 'react-i18next') return { useTranslation: () => ({ t: value => value }) }
      if (name === 'react/jsx-runtime') return { jsx, jsxs: jsx }
      if (name === '../i18n') return { t: value => value }
      if (name === '../ui') return { Section: 'Section', Row: 'Row', Switch: 'Switch', Btn: 'Btn', Segmented: 'Segmented', Icon: {} }
      if (name === '../context/ThemeContext') return { useTheme: () => ({ theme: 'light', setTheme() {} }) }
      if (name === '../desktop/UpdatePrompt') return { useAppUpdate: () => ({ phase: 'idle' }) }
      if (name === '../desktop/sentry') return { isCrashReportsEnabled: () => false, setCrashReportsEnabled() {} }
      if (name === '../analytics/posthog') return { isAnalyticsEnabled: () => false, setAnalyticsEnabled() {} }
      return { default: () => null }
    },
  }, { filename: file })
  return { app: exports.testAppSection({ analyticsOn: false, onAnalyticsChange() {} }), panel }
}

test('a production build hides the experiment section', () => {
  const panel = loadPanel(false)
  assert.equal(panel.flagOverridesVisible(), false)
  assert.equal(panel.default(), null)
  const app = loadAppSection(false)
  assert.equal(walk(app.app, item => item.type === app.panel.default), false)
  assert.equal(containsTitle(app.app, '实验功能'), false)
})

test('a dev build shows the experiment section', () => {
  const panel = loadPanel(true)
  assert.equal(panel.flagOverridesVisible(), true)
  const tree = panel.default()
  assert.equal(tree.type, 'Section')
  assert.equal(tree.props.title, '实验功能')
  const app = loadAppSection(true)
  assert.equal(walk(app.app, item => item.type === app.panel.default), true)
  assert.equal(containsTitle(app.app, '实验功能'), true)
})

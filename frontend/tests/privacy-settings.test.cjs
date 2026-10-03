const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), ts = require('typescript')

const flush = () => new Promise(resolve => setImmediate(resolve))
function loadAppSection(initial = true, saveMode = 'success') {
  let enabled = initial, resolveRead, resolveSave
  const read = new Promise(resolve => { resolveRead = resolve })
  const save = new Promise(resolve => { resolveSave = resolve })
  const effects = [], saved = [], applied = [], warnings = []
  const jsx = (type, props) => ({ type, props })
  const modules = {
    react: { useEffect: fn => effects.push(fn), useState: value => [value, () => {}], useRef: value => ({ current: value }) },
    'react/jsx-runtime': { jsx, jsxs: jsx },
    'react-i18next': { useTranslation() {} },
    '../i18n': { t: value => value },
    '../ui': { Section: 'Section', Row: 'Row', Switch: 'Switch', Btn: 'Btn', Segmented: 'Segmented', Icon: {} },
    antd: { Switch: 'Switch', message: { warning: text => warnings.push(text) } },
    '../utils/desktopMode': { isDesktopMode: async () => false },
    '../desktop/updater': { getAppVersion: async () => '1.5.4' },
    '../desktop/UpdatePrompt': { useAppUpdate: () => ({ phase: 'idle' }) },
    '../context/ThemeContext': { useTheme: () => ({ theme: 'light', setTheme() {} }) },
    '../desktop/sentry': { isCrashReportsEnabled: () => enabled, setCrashReportsEnabled: value => { enabled = value; applied.push(value) } },
    '../services/api': { settingsApi: { getPrivacy: () => read, updatePrivacy: async value => {
      saved.push(value.crash_reports)
      if (saveMode === 'failure') throw new Error('Controlled persistence failure')
      if (saveMode === 'pending') await save
      return value
    } } },
  }
  const output = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/pages/SettingsPage.tsx'), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
  }).outputText
  const exports = {}
  // Expose the actual private component only in the test VM; no product export or copied logic.
  vm.runInNewContext(output + '\nexports.testAppSection = AppSection;', {
    exports, require: name => modules[name] || { default: () => null }, console,
  })
  const tree = exports.testAppSection({ analyticsOn: false, onAnalyticsChange() {} })
  function find(node) {
    if (!node || typeof node !== 'object') return
    if (node.type === 'Row' && node.props.label === '崩溃报告') return node.props.children.props.onChange
    const children = node.props?.children
    for (const child of Array.isArray(children) ? children.flat(5) : [children]) { const found = find(child); if (found) return found }
  }
  const toggle = find(tree)
  assert.equal(typeof toggle, 'function')
  const cleanup = effects[0]()
  return { toggle, resolveRead, resolveSave, saved, applied, warnings, enabled: () => enabled, unmount: () => cleanup?.(), changeElsewhere: value => { enabled = value } }
}

test('privacy initialization applies the saved backend choice when there is no new user choice', async () => {
  const ui = loadAppSection(true); await flush()
  ui.resolveRead({ crash_reports: false }); await flush()
  assert.equal(ui.enabled(), false)
  assert.deepEqual(ui.applied, [false])
})

test('a stale initial privacy read cannot re-enable reports after the actual OFF handler saved', async () => {
  const ui = loadAppSection(true); await flush()
  await ui.toggle(false)
  assert.deepEqual(ui.saved, [false]); assert.equal(ui.enabled(), false)
  ui.resolveRead({ crash_reports: true }); await flush()
  assert.equal(ui.enabled(), false)
  assert.deepEqual(ui.applied, [false])
})

test('a stale initial privacy read cannot undo the actual ON handler', async () => {
  const ui = loadAppSection(false); await flush()
  await ui.toggle(true)
  ui.resolveRead({ crash_reports: false }); await flush()
  assert.equal(ui.enabled(), true)
  assert.deepEqual(ui.saved, [true])
})

test('a previous settings page cannot overwrite a later privacy choice after unmount', async () => {
  const ui = loadAppSection(true); await flush()
  ui.unmount(); ui.changeElsewhere(false)
  ui.resolveRead({ crash_reports: true }); await flush()
  assert.equal(ui.enabled(), false)
  assert.deepEqual(ui.applied, [])
})


test('failed backend persistence warns without allowing an old snapshot to undo the immediate OFF choice', async () => {
  const ui = loadAppSection(true, 'failure'); await flush()
  await ui.toggle(false)
  assert.equal(ui.warnings.length, 1)
  ui.resolveRead({ crash_reports: true }); await flush()
  assert.equal(ui.enabled(), false)
  assert.deepEqual(ui.applied, [false])
})

test('the new OFF choice takes priority before its backend save has completed', async () => {
  const ui = loadAppSection(true, 'pending'); await flush()
  const saving = ui.toggle(false)
  ui.resolveRead({ crash_reports: true }); await flush()
  assert.equal(ui.enabled(), false)
  assert.deepEqual(ui.applied, [false])
  ui.resolveSave(); await saving
  assert.deepEqual(ui.saved, [false])
  assert.deepEqual(ui.warnings, [])
})

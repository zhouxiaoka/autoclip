const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

function load() {
  const file = path.join(__dirname, '../src/features/studio/TemplatePicker.tsx')
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 },
  }).outputText
  const styleFile = path.join(__dirname, '../src/features/studio/editingStyle.ts')
  const styleExports = {}
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(styleFile, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText, { exports: styleExports })
  const exports = {}
  const events = []
  vm.runInNewContext(code, {
    exports,
    require: id => {
      if (id === '../../i18n') return { t: text => text }
      if (id === '../../analytics/studio') return {
        trackTemplateOverride: props => events.push(props),
        trackTemplatePickerShown: () => {},
      }
      if (id === '../../analytics/workflow') return { telemetryId: () => 't-abc123def456' }
      if (id === './editingStyle') return styleExports
      if (id === './EditingStylePicker') return { default: () => null }
      if (id === 'react') return { useEffect() {}, useRef: value => ({ current: value }) }
      if (id === 'react/jsx-runtime') return {
        jsx: (type, props) => ({ type, props }),
        jsxs: (type, props) => ({ type, props }),
        Fragment: 'fragment',
      }
      throw new Error(id)
    },
  })
  return { exports, events }
}

function nodes(value) {
  return !value || typeof value !== 'object' ? [] : Array.isArray(value) ? value.flatMap(nodes) : [value, ...nodes(value.props?.children)]
}

test('the import default is editorial and a change is an override event', () => {
  const { exports, events } = load()
  const fields = value => JSON.parse(JSON.stringify(value))
  assert.equal(exports.chosenTemplate(undefined), 'editorial')
  assert.deepEqual(fields(exports.templateImportFields(false, 'street')), {})
  assert.deepEqual(fields(exports.templateImportFields(true, undefined)), { html_template: 'editorial' })
  assert.deepEqual(fields(exports.templateImportFields(true, 'classic')), { html_template: 'classic' })
  const chosen = []
  const tree = exports.default({ value: undefined, onChange: next => chosen.push(next) })
  const buttons = nodes(tree).filter(node => node.type === 'button')
  assert.equal(buttons[0].props['aria-pressed'], true)
  buttons[1].props.onClick()
  assert.deepEqual(chosen, ['street'])
  assert.equal(events[0].from_template, 'editorial')
  assert.equal(events[0].to_template, 'street')
  assert.equal(events[0].stage, 'pre_import')
  assert.equal(events[0].flow_id, 't-abc123def456')
  assert.equal(events[0].input, 'mouse')
  assert.deepEqual(fields(exports.templateImportFields(true, 'street', 'editorial')), { html_template: 'street', recommended_template: 'editorial' })
})

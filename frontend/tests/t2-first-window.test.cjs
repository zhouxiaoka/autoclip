const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('path')
const { runInSandbox } = require('./vm-sandbox.cjs')
const ts = require('typescript')

const readiness = (() => {
  const file = path.join(__dirname, '../src/features/studio/importReadiness.ts')
  const exports = {}
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText
  runInSandbox(code, { exports, require: () => ({}) })
  return exports
})()

function loadUrlPreview() {
  const file = path.join(__dirname, '../src/features/studio/UrlPreview.tsx')
  const exports = {}
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText
  runInSandbox(code, {
    exports,
    require: (name) => {
      if (name === '../../i18n') return { t: (s) => s }
      if (name === '../../ui') return { Btn: Object.assign(function Btn() { return null }, { displayName: 'Btn' }) }
      if (name === 'react/jsx-runtime') {
        return {
          jsx: (t, p) => ({ t: typeof t === 'function' ? (t.displayName || t.name || 'fn') : t, p }),
          jsxs: (t, p) => ({ t: typeof t === 'function' ? (t.displayName || t.name || 'fn') : t, p }),
          Fragment: 'fragment',
        }
      }
      if (name === './etaModel') return { estimate: () => ({ etaMin: 2, optimistic: false, initialMin: 2, errorRatio: null }) }
      if (name === './planningCopy') return { VISUAL_SOURCE_TOO_LONG_MESSAGE: 'x' }
      if (name === './importReadiness') return readiness
      if (name === './types') return { FIRST_WINDOW_END_SEC: 1800 }
      return {}
    },
  })
  return exports
}

function walk(node, visit) {
  if (!node || typeof node !== 'object') return
  visit(node)
  const kids = node.p && node.p.children
  if (Array.isArray(kids)) kids.forEach((k) => walk(k, visit))
  else if (kids) walk(kids, visit)
}

const preview = loadUrlPreview()

test('T2: shouldSuggestFirstWindow gates on history and duration', () => {
  assert.equal(preview.shouldSuggestFirstWindow(false, 1801), true)
  assert.equal(preview.shouldSuggestFirstWindow(false, 1800), false)
  assert.equal(preview.shouldSuggestFirstWindow(true, 3600), false)
  assert.equal(preview.shouldSuggestFirstWindow(false, null), false)
})

test('T2: UrlPreview dual buttons call overrides', () => {
  let partial = 0
  let full = 0
  const tree = preview.default({
    preview: {
      title: 'long talk',
      duration: 3600,
      preview_route: 'local_transcription',
    },
    suggestFirstWindow: true,
    onConfirmFirstWindow: () => { partial += 1 },
    onConfirmFull: () => { full += 1 },
  })
  const buttons = []
  walk(tree, (node) => {
    if (node.t === 'Btn') buttons.push(node.p)
  })
  const labels = buttons.map((b) => b.children)
  assert.ok(labels.includes('只处理前 30 分钟'), labels)
  assert.ok(labels.includes('处理全片'), labels)
  const tip = []
  walk(tree, (node) => {
    if (node.p && node.p['data-testid'] === 't2-first-window-prompt') tip.push(node)
  })
  assert.equal(tip.length, 1)
  buttons.find((b) => b.children === '只处理前 30 分钟').onClick()
  buttons.find((b) => b.children === '处理全片').onClick()
  assert.equal(partial, 1)
  assert.equal(full, 1)
})

test('T2: ImportOptions type documents source_window', () => {
  const types = fs.readFileSync(path.join(__dirname, '../src/features/studio/types.ts'), 'utf8')
  assert.match(types, /source_window\?/)
  assert.match(types, /FIRST_WINDOW_END_SEC = 1800/)
})

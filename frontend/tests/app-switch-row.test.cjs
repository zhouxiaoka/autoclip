// The settings switch stays neutral until the saved value has loaded.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const ts = require('typescript')
const React = require('react')
const { runInSandbox } = require('./vm-sandbox.cjs')

const h = React.createElement
const { act } = React
const seen = []

function Switch(props) {
  seen.push(props.checked)
  return h('button', {
    type: 'button', role: 'switch', 'aria-label': props['aria-label'],
    'aria-checked': props.checked ? 'true' : 'false',
  })
}

function Row({ label, children }) {
  return h('div', null, h('b', null, label), children)
}

function loadRow() {
  const abs = path.resolve(__dirname, '../src/features/settings/AppSwitchRow.tsx')
  const { outputText } = ts.transpileModule(fs.readFileSync(abs, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
    fileName: abs,
  })
  const exports = {}
  const req = (id) => {
    if (id === 'react' || id === 'react/jsx-runtime') return require(id)
    if (id === 'antd') return { Switch, message: { error() {} } }
    if (id === '../../i18n') return { t: value => value }
    if (id === '../../ui') return { Row, Btn: ({ children }) => h('button', null, children) }
    throw new Error('unexpected import ' + id)
  }
  runInSandbox(outputText, { exports, require: req, console })
  return exports.default
}

const AppSwitchRow = loadRow()

function deferred() {
  let resolve
  const promise = new Promise(done => { resolve = done })
  return { promise, resolve }
}

let window
function installGlobals(values) {
  const saved = Object.keys(values).map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)])
  for (const [key, value] of Object.entries(values)) {
    Object.defineProperty(globalThis, key, { value, writable: true, configurable: true, enumerable: true })
  }
  return () => {
    for (const [key, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor)
      else delete globalThis[key]
    }
  }
}

async function openDom() {
  const Window = (await import('happy-dom')).Window
  window = new Window({ url: 'http://localhost/' })
  return installGlobals({ window, document: window.document, navigator: window.navigator, HTMLElement: window.HTMLElement, IS_REACT_ACT_ENVIRONMENT: true })
}

function closeDom(restore) {
  try { window.happyDOM.abort?.(); window.close() } finally { restore(); window = undefined }
}

async function flush() {
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)) })
}

async function mount(read) {
  const { createRoot } = require('react-dom/client')
  const host = document.createElement('div')
  document.body.appendChild(host)
  const root = createRoot(host)
  await act(async () => { root.render(h(AppSwitchRow, { label: '字幕', hint: '', read, write: async value => value })) })
  return {
    host,
    unmount: async () => {
      await act(async () => { root.unmount() })
      host.remove()
    },
  }
}

test('the switch is not checked until the saved value loads', async () => {
  const restore = await openDom()
  try {
    seen.length = 0
    const pending = deferred()
    const view = await mount(() => pending.promise)
    await flush()
    assert.equal(view.host.querySelector('[role="switch"]'), null)
    assert.deepEqual(seen, [])
    await act(async () => { pending.resolve(false) })
    await flush()
    const off = view.host.querySelector('[role="switch"]')
    assert.equal(off.getAttribute('aria-checked'), 'false')
    assert.deepEqual(seen, [false])
    await view.unmount()

    seen.length = 0
    const next = deferred()
    const again = await mount(() => next.promise)
    await flush()
    assert.equal(again.host.querySelector('[role="switch"]'), null)
    await act(async () => { next.resolve(true) })
    await flush()
    assert.equal(again.host.querySelector('[role="switch"]').getAttribute('aria-checked'), 'true')
    assert.deepEqual(seen, [true])
    await again.unmount()
  } finally {
    closeDom(restore)
  }
})

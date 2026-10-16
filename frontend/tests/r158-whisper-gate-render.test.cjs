// R18 #78: render the Whisper gate prompt in a DOM (happy-dom) and click its buttons, instead of grepping source.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { Window } = require('happy-dom')
const React = require('react')
const { loadTs } = require('./load-ts.cjs')

const window = new Window({ url: 'http://localhost/' })
globalThis.window = window
globalThis.document = window.document
globalThis.navigator = window.navigator
globalThis.HTMLElement = window.HTMLElement
globalThis.IS_REACT_ACT_ENVIRONMENT = true
const { createRoot } = require('react-dom/client')
const { act } = require('react')

const Btn = ({ children, onClick, disabled }) => React.createElement('button', { type: 'button', onClick, disabled }, children)
const dir = path.resolve(__dirname, '../src/features/studio')
const mod = loadTs(path.join(dir, 'TranscriptionGatePrompt.tsx'), {
  '../../i18n': { t: s => s },
  '../../ui': { Btn },
}, dir)
const Prompt = mod.default

function render(props) {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const root = createRoot(host)
  act(() => root.render(React.createElement(Prompt, props)))
  const button = label => [...host.querySelectorAll('button')].find(b => b.textContent === label)
  return { host, button, unmount: () => act(() => root.unmount()) }
}

test('install prompt: 一键安装 runs the existing install_whisper repair; 改用云端转写 only navigates on click', () => {
  const repairs = []; const navs = []
  const view = render({ kind: mod.LOCAL_TRANSCRIPTION_GATE, check: { ok: false, code: 'whisper_not_installed', repair: 'install_whisper' },
    busy: false, repairing: false, repair: item => { repairs.push(item) }, navigate: to => navs.push(to) })
  assert.equal(view.host.querySelector('[role=alertdialog]').getAttribute('aria-label'), '需要先安装本地转写')
  assert.deepEqual(navs, [])  // rendering alone never leaves the page or switches provider
  act(() => view.button('一键安装').click())
  assert.equal(repairs.length, 1)
  assert.equal(repairs[0].key, 'transcription')
  assert.equal(repairs[0].repair, 'install_whisper')
  assert.equal(repairs[0].code, 'whisper_not_installed')
  assert.deepEqual(navs, [])
  act(() => view.button('改用云端转写').click())
  assert.deepEqual(navs, ['/settings?section=speech&provider=cloud'])
  assert.equal(repairs.length, 1)
  view.unmount()
})

test('install prompt buttons are disabled while busy or installing', () => {
  const repairs = []; const navs = []
  const view = render({ kind: mod.LOCAL_TRANSCRIPTION_GATE, check: null, busy: false, repairing: true,
    repair: item => { repairs.push(item) }, navigate: to => navs.push(to) })
  assert.equal(view.button('一键安装').disabled, true)
  assert.equal(view.button('改用云端转写').disabled, true)
  act(() => { view.button('一键安装').click(); view.button('改用云端转写').click() })
  assert.deepEqual(repairs, []); assert.deepEqual(navs, [])
  view.unmount()
})

test('installing prompt shows the wait message and no action buttons', () => {
  const view = render({ kind: mod.LOCAL_TRANSCRIPTION_INSTALLING, busy: false, repairing: false, repair: () => {}, navigate: () => {} })
  assert.equal(view.host.querySelector('[role=alertdialog]').getAttribute('aria-label'), '等待安装完成')
  assert.match(view.host.textContent, /本地 Whisper 正在安装，装好后再开始。/)
  assert.equal(view.host.querySelectorAll('button').length, 0)
  view.unmount()
})

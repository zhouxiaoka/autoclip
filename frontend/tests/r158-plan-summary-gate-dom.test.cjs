// R23 #211 / #232: render the real PlanSummary (real React + happy-dom, real importReadiness, real errorText,
// real TranscriptionGatePrompt). A coded gate 422 on confirm must open the install prompt chosen by code,
// and the waiting states (installing / model downloading) must show the wait prompt, never "install".
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')
const { Window } = require('happy-dom')

const window = new Window({ url: 'http://localhost/' })
globalThis.window = window
globalThis.document = window.document
globalThis.navigator = window.navigator
globalThis.HTMLElement = window.HTMLElement
globalThis.IS_REACT_ACT_ENVIRONMENT = true
const React = require('react')
const { createRoot } = require('react-dom/client')
const { act } = React

// happy-dom swallows listener exceptions (#234); collect them so a crash in a click handler fails the test here.
const swallowed = []
window.addEventListener('error', e => swallowed.push(e.error || e.message))

const dir = path.resolve(__dirname, '../src/features/studio')
function load(file, mocks) {
  const abs = path.join(dir, file)
  const { outputText } = ts.transpileModule(fs.readFileSync(abs, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX }, fileName: abs })
  const exports = {}
  const req = id => {
    if (id in mocks) return mocks[id]
    if (id === 'react' || id === 'react/jsx-runtime') return require(id)
    if (id.startsWith('./')) return load(id.slice(2) + (fs.existsSync(path.join(dir, id.slice(2) + '.tsx')) ? '.tsx' : '.ts'), mocks)
    throw new Error('unexpected import ' + id)
  }
  vm.runInNewContext(outputText, { exports, require: req, window, console, URL, HTMLElement: window.HTMLElement, Promise, setTimeout, clearTimeout })
  return exports
}

const h = React.createElement
const Btn = ({ children, onClick, disabled, loading }) => h('button', { type: 'button', onClick, disabled: !!(disabled || loading) }, children)
const axios422 = detail => Object.assign(new Error('Request failed with status code 422'), { response: { status: 422, data: { detail } } })

async function mount(confirmPlan) {
  const installs = []; const navs = []
  const realErrorText = load('errorText.ts', {})
  const mocks = {
    'react-i18next': { useTranslation() {} },
    '../../i18n': { t: (s, v) => v ? s.replace(/\{\{(\w+)\}\}/g, (_, k) => v[k]) : s },
    'react-router-dom': { useNavigate: () => to => navs.push(to) },
    '../../ui': { Btn, Dialog: () => null, Row: ({ children }) => h('div', null, children), Segmented: () => null, fmtDuration: String },
    './types': { defaultImportOptions: {}, goalLabels: { content: '内容切片', highlight: '高光', promo: '推广' }, languages: [] },
    './ImportPreferences': { default: () => null },
    './api': { studioApi: { capabilities: async () => ({ visual_analysis: false, visual_model: '' }), confirmPlan }, ...realErrorText },
    '../../services/api': { speechApi: { installRuntime: async () => { installs.push('runtime'); return {} }, downloadModel: async m => { installs.push(m); return {} } } },
  }
  const PlanSummary = load('PlanSummary.tsx', mocks).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const root = createRoot(host)
  const plan = { id: 'plan1', mode: 'ai', reason: 'r', confidence: 0.9, content_type: 'talk', recommended_analysis: 'subtitle',
    suggested_goals: ['content'], preferences: { goal: 'content', aspect: 'original', language: 'source', duration: 30 }, overrides: {} }
  await act(async () => { root.render(h(PlanSummary, { projectId: 'p1', plan, status: 'awaiting_confirmation', onChanged() {}, onStarted() {} })) })
  await act(async () => {})
  const button = label => [...host.querySelectorAll('button')].find(b => b.textContent === label)
  const confirm = async () => { await act(async () => { button('确认并开始制作').click() }); await act(async () => {}) }
  return { host, button, confirm, installs, navs, unmount: () => act(() => root.unmount()) }
}
const dialog = host => host.querySelector('[role=alertdialog]')

test('R23 #211: confirm refused with whisper_not_installed opens the install prompt; 一键安装 runs the install', async () => {
  swallowed.length = 0
  const view = await mount(async () => { throw axios422({ code: 'whisper_not_installed', message: '需要先安装本地转写：……' }) })
  await view.confirm()
  assert.ok(dialog(view.host), 'the install prompt must open, not only the error text')
  assert.equal(dialog(view.host).getAttribute('aria-label'), '需要先安装本地转写')
  assert.equal(view.host.querySelector('.studio-error'), null)
  await act(async () => { view.button('一键安装').click() })
  await act(async () => {})
  assert.deepEqual(view.installs, ['runtime'])
  assert.equal(dialog(view.host), null, 'prompt closes once the install started; the user confirms again')
  await act(async () => { view.button('确认并开始制作').click() })
  await act(async () => {})
  assert.equal(dialog(view.host).getAttribute('aria-label'), '需要先安装本地转写')
  await act(async () => { view.button('改用云端转写').click() })
  assert.deepEqual(view.navs, ['/settings?section=speech&provider=cloud'])
  assert.deepEqual(swallowed, [])
  view.unmount()
})

for (const code of ['whisper_installing', 'whisper_model_downloading']) {
  test(`R23 #232: confirm refused with ${code} shows the wait prompt, never the install prompt`, async () => {
    swallowed.length = 0
    const view = await mount(async () => { throw axios422({ code, message: '等待……' }) })
    await view.confirm()
    assert.equal(dialog(view.host).getAttribute('aria-label'), '等待安装完成')
    assert.equal(view.button('一键安装'), undefined)
    assert.deepEqual(swallowed, [])
    view.unmount()
  })
}

test('R23 #211: an uncoded failure keeps the plain error text and opens no prompt', async () => {
  swallowed.length = 0
  const view = await mount(async () => { throw axios422('视觉模型不可用，请配置后重新确认；原素材已保留') })
  await view.confirm()
  assert.equal(dialog(view.host), null)
  assert.match(view.host.querySelector('.studio-error').textContent, /视觉模型不可用/)
  assert.deepEqual(swallowed, [])
  view.unmount()
})

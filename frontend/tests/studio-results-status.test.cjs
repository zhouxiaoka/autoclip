const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), ts = require('typescript')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')

function render(automatic, phase, status = 'running', buttons = [], calls = [], errorCode, navs = [], error = 'failure') {
  const workspace = {
    analysis: { status, phase, message: 'screening', error, error_code: errorCode },
    generation: automatic ? { auto_start: true, status: status === 'failed' ? 'failed' : 'screening' } : null,
    drafts: [], jobs: [], events: [], output_variants: [],
  }
  const exportsObject = {}
  const children = ({ children }) => React.createElement('div', null, children)
  const empty = () => null
  const moduleRequire = (name) => {
    if (name === 'react' || name === 'react/jsx-runtime') return require(name)
    if (name === 'react-i18next') return { useTranslation() {} }
    if (name === 'react-router-dom') return { useNavigate: () => to => navs.push(to) }
    if (name === '../../i18n') return { t: value => value }
    if (name === '../../ui') return { Btn: props => { buttons.push(props); return React.createElement('button', null, props.children) },
      Section: ({ children, description, right }) => React.createElement('section', null, description, right, children),
      Dialog: empty, fmtDuration: String }
    if (name === './useWorkspace') return { useWorkspace: () => ({ workspace, loaded: true, loading: false, refresh() {} }) }
    if (name === './api') return { studioApi: { source: () => '/test.mp4', analyze: async (...args) => calls.push(args) }, errorText: String }
    if (name === '../../utils/llmFailure') return require('./load-ts.cjs').loadTs(path.resolve(__dirname, '../src/utils/llmFailure.ts'))
    if (name === './importReadiness') return require('./load-ts.cjs').loadTs(path.resolve(__dirname, '../src/features/studio/importReadiness.ts'))
    if (name === './platformLabel') return { platformLabel: String }
    if (name === '../../analytics/flags') return { flagEnabled: () => false, flagAssigned: () => false }
    if (name === '../../analytics/studio') return { trackLegacyEntry() {} }
    if (name === './legacyEntrypoints') return { legacyEntrypointsHidden: () => false }
    return { default: empty }
  }
  const source = fs.readFileSync(path.join(__dirname, '../src/features/studio/StudioResults.tsx'), 'utf8')
  vm.runInNewContext(ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
  }).outputText, { exports: exportsObject, require: moduleRequire })
  return renderToStaticMarkup(React.createElement(exportsObject.default, {
    project: { id: 'test', status: 'processing', settings: { smart_import: {} }, clips: [], collections: [] },
    onCreateCollection() {}, onReload() {},
  }))
}

test('automatic screening never asks for a manual confirmation', () => {
  assert.doesNotMatch(render(true, 'screening'), /识别完成后，请确认要制作的类型/)
})
test('manual screening keeps its confirmation guidance', () => {
  assert.match(render(false, 'screening'), /识别完成后，请确认要制作的类型/)
})
test('failed automatic generation does not claim AI is still producing', () => {
  assert.doesNotMatch(render(true, 'screening', 'failed'), /AI 正在按所选平台制作成片/)
})

test('failed automatic output exposes a retry that reuses the project and automatic route', async () => {
  const buttons = [], calls = []
  render(true, 'production', 'failed', buttons, calls)
  const retry = buttons.find(button => button.children === '重试')
  assert.ok(retry, 'failed automatic output must have a retry entry')
  await retry.onClick()
  assert.deepEqual(calls, [['test', true]])
})
test('active automatic output never offers a second analysis submission', () => {
  const buttons = []
  render(true, 'production', 'running', buttons)
  assert.equal(buttons.some(button => button.children === '重试'), false)
})


test('invalid API key renders the new copy instead of missing-key guidance', () => {
  const html = render(true, 'production', 'failed', [], [], 'llm_auth_invalid')
  assert.match(html, /API Key 无效或已过期，请检查后重试/)
  assert.doesNotMatch(html, /需要你自己的 API Key|自备/)
})

test('R22 #212: a whisper_not_installed failure offers the transcription settings entry, not only model settings', () => {
  for (const code of ['whisper_not_installed', 'whisper_install_failed']) {
    const buttons = [], navs = []
    render(true, 'screening', 'failed', buttons, [], code, navs)
    const entry = buttons.find(button => button.children === '打开转写设置')
    assert.ok(entry, `${code}: the failure page must link to transcription settings`)
    assert.equal(buttons.some(button => button.children === '模型设置'), false)
    entry.onClick()
    assert.deepEqual(navs, ['/settings?section=speech'])
  }
  const buttons = [], navs = []
  render(true, 'screening', 'failed', buttons, [], 'llm_not_configured', navs)
  buttons.find(button => button.children === '模型设置').onClick()
  assert.deepEqual(navs, ['/settings?section=ai'])
})

test('R24 #231: an unreadable source is shown at once as a source problem: no spinner, no retry, no settings, pick another file', () => {
  const UNREADABLE = '无法读取这个视频的时长，文件可能已损坏、格式不受支持，或路径里有特殊字符。请换一个文件，或先用其他软件转成 MP4 后重新导入。'
  for (const automatic of [true, false]) {
    const buttons = [], navs = []
    const html = render(automatic, 'screening', 'failed', buttons, [], 'source_unreadable', navs, UNREADABLE)
    assert.match(html, /这个素材无法使用/)
    assert.ok(html.includes(UNREADABLE), 'the unreadable message itself is on the page')
    assert.doesNotMatch(html, /class="spin"|这次制作未完成/)
    assert.equal(buttons.some(b => b.children === '重试'), false, 'retrying the same file cannot help')
    assert.equal(buttons.some(b => b.children === '模型设置' || b.children === '打开转写设置'), false)
    buttons.find(b => b.children === '换一个视频').onClick()
    assert.deepEqual(navs, ['/'])
  }
})

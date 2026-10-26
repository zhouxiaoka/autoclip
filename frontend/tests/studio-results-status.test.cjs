const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path'), ts = require('typescript')
const { runInSandbox } = require('./vm-sandbox.cjs')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')

function render(automatic, phase, status = 'running', buttons = [], calls = [], errorCode, failureStage, error = 'failure', message = 'screening') {
  const workspace = {
    analysis: { status, phase, message, error, error_code: errorCode, failure_stage: failureStage },
    generation: generationOverride.value || (automatic ? { auto_start: true, status: status === 'failed' ? 'failed' : 'screening' } : null),
    drafts: [], jobs: [], events: [], output_variants: [], attempts: attemptsOverride.value || undefined,
  }
  const exportsObject = {}
  const children = ({ children }) => React.createElement('div', null, children)
  const empty = () => null
  const moduleRequire = (name) => {
    if (name === 'react' || name === 'react/jsx-runtime') return require(name)
    if (name === 'react-i18next') return { useTranslation() {} }
    if (name === 'react-router-dom') return { useNavigate: () => to => navigations.push(to), useLocation: () => ({ search: routeSearch.value }) }
    if (name === './settingsReturn') return require('./load-ts.cjs').loadTs(path.resolve(__dirname, '../src/features/studio/settingsReturn.ts'))
    if (name === './failureAction') return require('./load-ts.cjs').loadTs(path.resolve(__dirname, '../src/features/studio/failureAction.ts'))
    if (name === './studioProgress') return require('./load-ts.cjs').loadTs(path.resolve(__dirname, '../src/features/studio/studioProgress.ts'))
    if (name === '../../i18n') return { t: value => value }
    if (name === '../../ui') return { Btn: props => { buttons.push(props); return React.createElement('button', null, props.children) },
      Section: ({ children, description, right }) => React.createElement('section', null, description, right, children),
      Dialog: empty, fmtDuration: String }
    if (name === './useWorkspace') return { useWorkspace: () => ({ workspace, loaded: true, loading: false, refresh() {} }) }
    if (name === './api') return { studioApi: { source: () => '/test.mp4', analyze: async (...args) => calls.push(args), retry: async (...args) => calls.push(['retry', ...args]) }, errorText: String }
    if (name === '../../utils/llmFailure') return require('./load-ts.cjs').loadTs(path.resolve(__dirname, '../src/utils/llmFailure.ts'))
    if (name === './importReadiness') return require('./load-ts.cjs').loadTs(path.resolve(__dirname, '../src/features/studio/importReadiness.ts'))
    if (name === './platformLabel') return { platformLabel: String }
    if (name === '../../analytics/flags') return { flagEnabled: () => false, flagAssigned: () => false }
    if (name === '../../analytics/studio') return { trackLegacyEntry() {} }
    if (name === './legacyEntrypoints') return { legacyEntrypointsHidden: () => false }
    if (name === './FailureActions') return loadTsx('../src/features/studio/FailureActions.tsx', moduleRequire)
    return { default: empty }
  }
  const source = fs.readFileSync(path.join(__dirname, '../src/features/studio/StudioResults.tsx'), 'utf8')
  runInSandbox(ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
  }).outputText, { exports: exportsObject, require: moduleRequire, URLSearchParams })
  return renderToStaticMarkup(React.createElement(exportsObject.default, {
    project: { id: 'test', status: 'processing', settings: { smart_import: {} }, clips: [], collections: [] },
    onCreateCollection() {}, onReload() {},
  }))
}

function loadTsx(rel, moduleRequire, globals = {}) {
  const exportsObject = {}
  const src = fs.readFileSync(path.join(__dirname, rel), 'utf8')
  runInSandbox(ts.transpileModule(src, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX } }).outputText,
    { exports: exportsObject, require: moduleRequire, URLSearchParams, ...globals })
  return exportsObject
}

const navigations = []
const generationOverride = { value: null }
const attemptsOverride = { value: null }
const routeSearch = { value: '' }

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
  assert.deepEqual(calls, [['retry', 'test']])  // #419: the one backend retry command
})
test('active automatic output never offers a second analysis submission', () => {
  const buttons = []
  render(true, 'production', 'running', buttons)
  assert.equal(buttons.some(button => button.children === '重试'), false)
})


test('invalid API key renders the new copy instead of missing-key guidance', () => {
  const html = render(true, 'production', 'failed', [], [], 'llm_auth_invalid')
  assert.match(html, /API Key 无效或已过期，请到设置里更新后再试/)
  assert.doesNotMatch(html, /需要你自己的 API Key|自备/)
})

test('R22 #212: a whisper_not_installed failure offers the transcription settings entry, not only model settings', () => {
  for (const code of ['whisper_not_installed', 'whisper_install_failed']) {
    const buttons = []
    navigations.length = 0
    render(true, 'screening', 'failed', buttons, [], code)
    const entry = buttons.find(button => button.children === '打开转写设置')
    assert.ok(entry, `${code}: the failure page must link to transcription settings`)
    assert.equal(buttons.some(button => button.children === '模型设置'), false)
    entry.onClick()
    assert.deepEqual(navigations, ['/settings?section=speech'])
  }
  const buttons = []
  navigations.length = 0
  render(true, 'screening', 'failed', buttons, [], 'llm_not_configured')
  buttons.find(button => button.children === '模型设置').onClick()
  assert.deepEqual(navigations, ['/settings?section=ai'])
})

test('R24 #231: an unreadable source is shown at once as a source problem: no spinner, no retry, no settings, pick another file', () => {
  const UNREADABLE = '无法读取这个视频的时长。找不到源文件（可能已被移动或删除），也可能是文件已损坏、格式不受支持，或路径里有特殊字符。请换一个文件，或先用其他软件转成 MP4 后重新导入。'
  for (const automatic of [true, false]) {
    const buttons = []
    navigations.length = 0
    const html = render(automatic, 'screening', 'failed', buttons, [], 'source_unreadable', undefined, UNREADABLE)
    assert.match(html, /这个素材无法使用/)
    assert.ok(html.includes(UNREADABLE), 'the unreadable message itself is on the page')
    assert.doesNotMatch(html, /class="spin"|这次制作未完成/)
    assert.equal(buttons.some(b => b.children === '重试'), false, 'retrying the same file cannot help')
    assert.equal(buttons.some(b => b.children === '模型设置' || b.children === '打开转写设置'), false)
    buttons.find(b => b.children === '换一个视频').onClick()
    assert.deepEqual(navigations, ['/'])
  }
})

for (const [code, automatic] of [['llm_auth_invalid', true], ['insufficient_quota', true], ['llm_not_configured', false], ['invalid_key', true]]) {
  test(`1.5.7 user-cause failure ${code} shows 「去设置」 with reason, no direct retry`, () => {
    const buttons = []
    const html = render(automatic, 'production', 'failed', buttons, [], code)
    assert.equal(buttons.some(b => b.children === '重试'), false)
    const go = buttons.find(b => b.children === '去设置')
    assert.ok(go)
    assert.match(html, /请|余额|模型/)
    navigations.length = 0
    go.onClick()
    assert.deepEqual(navigations, ['/settings?section=analysis&return_project=test'])
  })
}
for (const code of ['service_restarted', 'timeout', 'provider_error', 'model_not_found']) {
  test(`1.5.7 non-user failure ${code} keeps Retry and no 「去设置」`, () => {
    const buttons = []
    render(true, 'production', 'failed', buttons, [], code)
    assert.ok(buttons.some(b => b.children === '重试'))
    assert.equal(buttons.some(b => b.children === '去设置'), false)
  })
}

for (const [stage, destination] of [['subtitle', '/settings?section=speech'], ['analyze', '/settings?section=analysis'], ['screening', '/settings?section=analysis'], [undefined, '/settings?section=analysis']]) {
  test(`1.5.7 「去设置」 for a user-cause failure at stage ${stage} opens ${destination}`, () => {
    const buttons = []
    render(true, 'production', 'failed', buttons, [], 'invalid_key', stage)
    navigations.length = 0
    buttons.find(b => b.children === '去设置').onClick()
    assert.deepEqual(navigations, [destination + '&return_project=test'])
  })
}

test('1.5.7 settings page resolves both 「去设置」 targets to their own rows (no fallback to the top)', () => {
  const page = fs.readFileSync(path.join(__dirname, '../src/pages/SettingsPage.tsx'), 'utf8')
  const aliases = page.slice(page.indexOf('const SECTION_ALIASES'), page.indexOf('}\n', page.indexOf('const SECTION_ALIASES')))
  assert.match(aliases, /analysis: \{ section: 'ai', anchor: 'ai-defaults-analysis' \}/)
  assert.match(aliases, /speech: \{ section: 'ai', anchor: 'ai-defaults-transcription' \}/)
  const fa = require('./load-ts.cjs').loadTs(path.resolve(__dirname, '../src/features/studio/failureAction.ts'))
  for (const dest of [fa.SETTINGS_DESTINATION, fa.TRANSCRIPTION_SETTINGS_DESTINATION]) {
    const section = new URLSearchParams(dest.split('?')[1]).get('section')
    assert.ok(new RegExp(`\\n\\s+${section}: \\{ section: 'ai', anchor: '`).test(aliases), dest)
  }
})

test('1.5.7 manual failed run hides Retry once a collection exists (R18 82)', () => {
  const src = fs.readFileSync(path.join(__dirname, '../src/features/studio/StudioResults.tsx'), 'utf8')
  assert.ok(src.includes('project.collections?.length || workspace.jobs?.some'))
})
for (const [code, stage, destination] of [['authentication', 'subtitle', '/settings?section=speech'], ['provider_error', 'subtitle', null]]) {
  test(`1.5.7 cloud ASR ${code} at ${stage} -> ${destination || 'Retry'} (R18 80)`, () => {
    const buttons = []
    render(true, 'production', 'failed', buttons, [], code, stage)
    const go = buttons.find(b => b.children === '去设置')
    if (!destination) { assert.equal(go, undefined); assert.ok(buttons.some(b => b.children === '重试')); return }
    navigations.length = 0; go.onClick(); assert.deepEqual(navigations, [destination + '&return_project=test'])
  })
}
test('R19 #106 manual mode: transcription 401 (authentication @ subtitle) -> 「去设置」 opens speech', () => {
  const buttons = []
  render(false, 'production', 'failed', buttons, [], 'authentication', 'subtitle')
  assert.equal(buttons.some(b => b.children === '重试'), false)
  navigations.length = 0
  buttons.find(b => b.children === '去设置').onClick()
  assert.deepEqual(navigations, ['/settings?section=speech&return_project=test'])
})

// after an auth failure the user fixes the key; there must be a way to continue the same project.
test('R20 #125 auth failure: 「继续制作」 sits beside 「去设置」 and reuses the retry API (retry=true)', async () => {
  routeSearch.value = ''
  const buttons = [], calls = []
  render(true, 'production', 'failed', buttons, calls, 'invalid_key', 'subtitle')
  assert.equal(buttons.find(b => b.variant === 'cta').children, '去设置')
  const cont = buttons.find(b => b.children === '继续制作')
  assert.ok(cont, 'auth failure must offer 继续制作')
  await cont.onClick()
  assert.deepEqual(calls, [['retry', 'test']])  // #419: backend retry command -> receipt with retry_of + new attempt_id
})
test('R20 #125 back from a successful settings save (?continue=1): 「继续制作」 is the primary action', async () => {
  routeSearch.value = '?continue=1'
  const buttons = [], calls = []
  render(false, 'production', 'failed', buttons, calls, 'authentication', 'subtitle')
  routeSearch.value = ''
  assert.equal(buttons.find(b => b.variant === 'cta').children, '继续制作')
  assert.ok(buttons.some(b => b.children === '去设置'))
  assert.equal(buttons.some(b => b.children === '重试'), false)
  await buttons.find(b => b.children === '继续制作').onClick()
  assert.deepEqual(calls, [['retry', 'test']])
})
test('R20 #125 settings save returns to the project only when opened from one and the id is safe', () => {
  const r = require('./load-ts.cjs').loadTs(path.resolve(__dirname, '../src/features/studio/settingsReturn.ts'))
  assert.equal(r.settingsReturnUrl('/settings?section=speech', 'p-1'), '/settings?section=speech&return_project=p-1')
  assert.equal(r.returnAfterSave('?section=speech&return_project=p-1'), '/project/p-1?continue=1')
  assert.equal(r.returnAfterSave('?section=speech'), null)
  assert.equal(r.returnAfterSave('?return_project=..%2F..%2Fx'), null)
  const fired = []
  r.notifySettingsSaved({ dispatchEvent: e => { fired.push(e.type); return true } })
  assert.deepEqual(fired, [r.SETTINGS_SAVED_EVENT])
})
test('R22 #173: the real listener returns to the project on the one save notification', () => {
  const r = require('./load-ts.cjs').loadTs(path.resolve(__dirname, '../src/features/studio/settingsReturn.ts'))
  const listeners = {}, navigated = []
  const win = { addEventListener: (n, f) => { listeners[n] = f }, removeEventListener: (n) => { delete listeners[n] }, dispatchEvent: e => { listeners[e.type]?.(e); return true } }
  const effects = []
  const mod = loadTsx('../src/features/studio/SettingsReturnListener.tsx', name => {
    if (name === 'react') return { useEffect: f => effects.push(f) }
    if (name === 'react-router-dom') return { useLocation: () => ({ pathname: '/settings', search: '?section=speech&return_project=p-1' }), useNavigate: () => to => navigated.push(to) }
    if (name === './settingsReturn') return r
    throw new Error(name)
  }, { window: win })
  mod.default(); effects.forEach(f => f())
  r.notifySettingsSaved(win)                        // the function production calls after a validated save
  assert.deepEqual(navigated, ['/project/p-1?continue=1'])
  const hook = fs.readFileSync(path.join(__dirname, '../src/features/settings/useModelSettings.ts'), 'utf8')
  assert.ok(hook.includes('if (!failed && !visionFailed) notifySettingsSaved()'))
  assert.equal(/dispatchEvent|function notifySaved/.test(hook), false, 'no second notification implementation')
  const app = fs.readFileSync(path.join(__dirname, '../src/App.tsx'), 'utf8')
  assert.ok(app.includes('<SettingsReturnListener />'))
})
test('R22 code health: failure state computed once, each button at most once', () => {
  const fa = loadTsx('../src/features/studio/FailureActions.tsx', name => name === './failureAction' ? require('./load-ts.cjs').loadTs(path.resolve(__dirname, '../src/features/studio/failureAction.ts')) : name === '../../utils/llmFailure' ? require('./load-ts.cjs').loadTs(path.resolve(__dirname, '../src/utils/llmFailure.ts')) : name === 'react/jsx-runtime' ? require(name) : {})
  const keys = p => JSON.parse(JSON.stringify(p.buttons.map(b => `${b.key}${b.cta ? '*' : ''}`)))
  assert.deepEqual(keys(fa.failurePlan({ error_code: 'authentication' }, true, false)), ['settings*', 'continue'])
  assert.deepEqual(keys(fa.failurePlan({ error_code: 'authentication' }, true, true)), ['continue*', 'settings'])
  assert.deepEqual(keys(fa.failurePlan({ error_code: 'authentication' }, false, true)), ['settings*'])
  assert.deepEqual(keys(fa.failurePlan({ error_code: 'timeout' }, true, false)), ['retry'])
  assert.deepEqual(keys(fa.failurePlan({ error_code: 'timeout' }, false, false)), [])
  assert.equal(fa.failurePlan({ error_code: 'provider_error', upstream_error_type: 'permission_denied' }, true, false).message, '当前令牌没有该模型的权限，请到服务商控制台勾选模型或更换分组。')
})

// the results-page line for "this re-run finished, N earlier failures" shows only when the round completed
// and settle's not_redone_failed_count > 0; otherwise the original wording.
test('R29 #444 the re-run line shows only for a completed round with earlier failures left', () => {
  const NEW = /本次重跑已完成，之前还有/, DONE = /已按所选平台生成可发布成片/
  const at = generation => { generationOverride.value = { auto_start: true, ...generation }; try { return render(true, 'rendering', 'completed') } finally { generationOverride.value = null } }
  const withN = at({ status: 'completed', not_redone_failed_count: 2 })
  assert.match(withN, NEW); assert.doesNotMatch(withN, DONE)
  const zero = at({ status: 'completed', not_redone_failed_count: 0 })
  assert.doesNotMatch(zero, NEW); assert.match(zero, DONE)
  assert.doesNotMatch(at({ status: 'partial', not_redone_failed_count: 2 }), NEW)
})

test('running production shows a stage progress bar, not only spinner text', () => {
  const html = render(true, 'production', 'running')
  assert.match(html, /role="progressbar"/)
  assert.match(html, /内容分析/)
  assert.match(html, /\d+%/)
  assert.match(html, /模型步骤最多约 20 分钟/)
  assert.match(html, /进度为估算，以阶段为准/)
  assert.doesNotMatch(html, /class="spin"/)
})

test('download, transcription and export progress omit the 20-minute model cap', () => {
  const download = render(true, 'screening', 'running')
  assert.match(download, /素材准备/)
  assert.doesNotMatch(download, /模型步骤最多约 20 分钟/)
  assert.match(download, /进度为估算，以阶段为准/)
  const transcribe = render(true, 'production', 'running', [], [], undefined, undefined, 'failure', '正在生成字幕')
  assert.match(transcribe, /字幕处理/)
  assert.doesNotMatch(transcribe, /模型步骤最多约 20 分钟/)
  const exporting = render(true, 'rendering', 'running')
  assert.match(exporting, /视频导出/)
  assert.doesNotMatch(exporting, /模型步骤最多约 20 分钟/)
})

test('a bare 错误 names the step, and a billable call adds the billing sentence', () => {
  const sentence = '模型响应超时，请检查服务和网络后重试；本地模型请确认服务仍在运行。'
  const guidance = '这次请求可能已经由服务商计费。重试前请先核对余额，并在设置里测试连接。'
  generationOverride.value = { auto_start: true, status: 'failed', billable_calls_before_failure: 2 }
  try {
    const html = render(true, 'production', 'failed', [], [], 'timeout', 'analyze', '错误')
    assert.match(html, new RegExp('分析：' + sentence))
    assert.match(html, new RegExp(guidance.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
    assert.doesNotMatch(html, /<span class="studio-error">错误<\/span>/)
  } finally {
    generationOverride.value = null
  }
  const quiet = render(true, 'production', 'failed', [], [], 'timeout', 'analyze', '错误')
  assert.match(quiet, new RegExp('分析：' + sentence))
  assert.doesNotMatch(quiet, /可能已经由服务商计费/)
})

test('1.5.7 results page has no control that appends platforms', () => {
  const html = render(true, 'rendering', 'completed')
  assert.doesNotMatch(html, /追加平台/)
})

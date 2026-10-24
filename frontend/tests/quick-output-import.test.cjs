const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path'),ts=require('typescript')
const { runInSandbox } = require('./vm-sandbox.cjs')
class FormDataMock { constructor(){this.rows=[]} append(key,value){this.rows.push([key,String(value)])} get(key){const row=this.rows.find(item=>item[0]===key);return row&&row[1]} entries(){return this.rows.values()} }

function loadReadiness(){
 const exports={}
 const source=fs.readFileSync(path.join(__dirname,'../src/features/studio/importReadiness.ts'),'utf8')
 runInSandbox(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,{exports,require(){throw new Error('importReadiness')}})
 return exports
}
function load(mocks){
 const exports={}
 const source=fs.readFileSync(path.join(__dirname,'../src/features/studio/CreativeImport.tsx'),'utf8')
 runInSandbox(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2020}}).outputText,{FormData:FormDataMock,exports,require:id=>{assert.ok(id in mocks,id);return mocks[id]}})
 return exports.default
}
function nodes(value){return !value||typeof value!=='object'?[]:Array.isArray(value)?value.flatMap(nodes):[value,...nodes(value.props?.children)]}

test('quick import submits platform targets, branding and auto-starts to results',async()=>{
 const calls=[],navigations=[];let index=0
 const ready={analysis_mode:'auto',ready:true,checks:{analysis:{ok:true,code:'configured',repair:'none'},transcription:{ok:true,code:'whisper_installed',repair:'none'},visual:{ok:true,code:'optional',repair:'none'},ffmpeg:{ok:true,code:'available',repair:'none'}}}
 const states=[['link',()=>{}],['https://youtube.com/watch?v=video',()=>{}],[null,()=>{}],[null,()=>{}],[{goal:'auto',language:'source',aspect:null,duration:null,instruction:''},()=>{}],['',()=>{}],[['douyin'],()=>{}],[false,()=>{}],[false,()=>{}],['',()=>{}],[ready,()=>{}],[true,()=>{}],[false,()=>{}],[false,()=>{}],[null,()=>{}],[{open:false,durationSec:null},()=>{}]]
 const component=load({
  'react-i18next':{useTranslation:()=>{}},'../../i18n':{t:x=>x},
  react:{useState:()=>states[index++],useEffect:()=>{},useRef:current=>({current})},antd:{Select:'select'},'react-router-dom':{useNavigate:()=>path=>navigations.push(path)},
  'react/jsx-runtime':{jsx:(type,props)=>({type,props}),jsxs:(type,props)=>({type,props}),Fragment:'fragment'},
  '../../ui':{Btn:'button',Segmented:'segmented',Dialog:'dialog',StatusDot:'status'},'./PlatformPicker':{default:'platform-picker'},
  './api':{studioApi:{import:async body=>{calls.push(body);return {project_id:'project-1'}},readiness:async()=>ready},errorText:String},'../../analytics/studio':{trackQuickOutputPlatforms(){},trackAsrReadiness(){},trackOneClickStarted(){},trackOneClickUndone(){},trackAutoChoiceOverridden(){}},'../../analytics/workflow':{telemetryId:()=>'t-importflow-aaaaaaaa'},'../../analytics/experience':{trackExperience(){}},
  '../../analytics/flags':{useFlag:()=>false,flagEnabled:()=>false,flagValue:()=>'button',flagAssigned:()=>false,featureSnapshot:()=>({pkg_templates_v1:false})},
  './TemplatePicker':{default:'template-picker',templateImportFields:()=>({})},
  './StyleProbeLine':{default:'style-probe'},
  './editingStyleSession':{readStyle:()=>({key:'',status:'idle',result:null,latencyMs:0})},
  './platformLabel':{platformLabel:id=>id},'./platformMemory':{readRememberedPlatforms:()=>null,resolvePlatforms:()=>({platforms:['douyin'],source:'user'}),samePlatforms:()=>true,writeRememberedPlatforms(){}},
  './pasteStart':{claimBackgroundWhisperInstall:()=>false,importUrlKind:()=>null,isVideoFile:()=>false,shouldAutoStart:()=>false,shouldBackgroundInstallWhisper:()=>false,UNDO_MS:3000},
  './importPreferencesStore':{readImportPreferences:()=>null},
  './types':{defaultImportOptions:{goal:'auto',language:'source',aspect:null,duration:null,instruction:''}},
  './ImportPreferences':{default:'preferences'},'../../services/api':{speechApi:{installRuntime:async()=>({started:true,message:''})}},
  './importReadiness':loadReadiness(),'./settingsReturn':{SETTINGS_SAVED_EVENT:'autoclip:model-settings-saved'},'./TranscriptionGatePrompt':{default:'transcription-gate'},'./transcriptionRecovery':{isRecoveryCode:c=>['whisper_not_installed','whisper_install_failed','whisper_model_missing','whisper_model_failed','whisper_installing','whisper_model_downloading'].includes(c)},'./useTranscriptionRecovery':{useTranscriptionRecovery:()=>[{phase:'idle',percent:null},{open:(c)=>{(globalThis.__recoveryOpened||(globalThis.__recoveryOpened=[])).push(c)},close(){},install:async()=>{},retry:async()=>{}}]},'./studio.css':{},'./quick-output.css':{},
  '../settings/OutputCaptionsSetting':{OutputCaptionsSwitch:()=>null},
 })
 const tree=nodes(component({onImported:async()=>{}}))
 await tree.find(node=>node.type==='button'&&node.props?.variant==='cta').props.onClick()
 assert.equal(calls.length,1)
 assert.deepEqual([...calls[0].entries()].filter(([key])=>key==='platforms'),[['platforms','douyin']])
 assert.equal(calls[0].get('auto_start'),'true')
 assert.equal(calls[0].get('portrait_style'),'auto')
 assert.equal(calls[0].get('brand_outro_enabled'),undefined, 'the backend uses the saved application setting')
 assert.deepEqual(navigations,['/project/project-1'])
})

test('quick import source no longer tells users to confirm a plan',()=>{
 const source=fs.readFileSync(path.join(__dirname,'../src/features/studio/CreativeImport.tsx'),'utf8')
 assert.match(source,/直接生成可发布成片/)
 assert.match(source,/PlatformPicker/)
 assert.doesNotMatch(source,/navigate\(`\/import\/\$\{result\.project_id\}`\)/)
})

const NOTICE = 'YouTube 横屏至少需要一条 3 分钟或更长的片段。如果素材做不出这样一条，这个版本会被跳过，其他平台仍会生成。'
const NOTICE_ONLY = 'YouTube 横屏至少需要一条 3 分钟或更长的片段。如果素材做不出这样一条，这个版本会被跳过。'
const TOO_SHORT = '这段素材不足 3 分钟，做不了 YouTube 横屏。'
const SKIP_OTHERS = 'YouTube 横屏会跳过，其他平台照常生成。'
const PICK_ANOTHER = '请再选一个其他平台。'

test('youtube landscape does not start until the rule is confirmed', async () => {
  const React = require('react')
  const { act } = React
  const h = React.createElement
  const { Window } = await import('happy-dom')
  const window = new Window({ url: 'http://localhost/' })
  const restore = installDom(window)
  const calls = []
  try {
    const view = await mountImport(window, React, h, calls)
    await flush(act)
    const box = view.host.querySelector('textarea')
    setValue(window, box, 'https://youtube.com/watch?v=abcdefghijk')
    await act(async () => { box.dispatchEvent(new window.Event('input', { bubbles: true })) })
    await act(async () => { buttonIncluding(view.host, 'YouTube 视频').click() })
    await flush(act)
    assert.equal(view.host.querySelector('[role="note"]').textContent, NOTICE)
    await act(async () => { buttonText(view.host, '生成成片').click() })
    await flush(act)
    assert.equal(calls.length, 0)
    const dialog = document.querySelector('[role="dialog"]')
    assert.equal(dialog.querySelector('p').textContent, NOTICE)
    await act(async () => { buttonText(document.body, '取消').click() })
    await flush(act)
    assert.equal(calls.length, 0)
    assert.equal(document.querySelector('[role="dialog"]'), null)
    await act(async () => { buttonText(view.host, '生成成片').click() })
    await flush(act)
    await act(async () => { buttonText(document.body, '确认并开始').click() })
    await flush(act)
    assert.equal(calls.length, 1)
    assert.ok([...calls[0].entries()].some(([key, value]) => key === 'platforms' && value === 'youtube_long'))
    await view.unmount()
  } finally {
    try { window.happyDOM.abort?.(); window.close() } finally { restore() }
  }
})

test('a known short file with only youtube landscape cannot start', async () => {
  const React = require('react')
  const { act } = React
  const h = React.createElement
  const { Window } = await import('happy-dom')
  const window = new Window({ url: 'http://localhost/' })
  const restore = installDom(window)
  const calls = []
  stubVideoDuration(window, 90)
  try {
    const view = await mountImport(window, React, h, calls)
    await flush(act)
    await act(async () => { buttonText(view.host, '文件导入').click() })
    await act(async () => { buttonIncluding(view.host, 'YouTube 视频').click() })
    await act(async () => { buttonIncluding(view.host, '抖音').click() })
    await chooseFile(window, act, view)
    assert.equal(view.host.querySelector('[role="note"]').textContent, TOO_SHORT)
    await act(async () => { buttonText(view.host, '生成成片').click() })
    await flush(act)
    assert.equal(calls.length, 0)
    const dialog = document.querySelector('[role="dialog"]')
    assert.ok(dialog.textContent.includes(TOO_SHORT))
    assert.ok(dialog.textContent.includes(PICK_ANOTHER))
    assert.equal(buttonText(dialog, '确认并开始'), undefined)
    assert.ok(buttonText(dialog, '知道了'))
    await act(async () => { buttonText(dialog, '知道了').click() })
    await flush(act)
    assert.equal(calls.length, 0)
    assert.equal(document.querySelector('[role="dialog"]'), null)
    await act(async () => { buttonText(view.host, '生成成片').click() })
    await flush(act)
    assert.equal(calls.length, 0)
    assert.equal(buttonText(document.body, '确认并开始'), undefined)
    await view.unmount()
  } finally {
    try { window.happyDOM.abort?.(); window.close() } finally { restore() }
  }
})

test('a known short file with another platform still confirms and starts', async () => {
  const React = require('react')
  const { act } = React
  const h = React.createElement
  const { Window } = await import('happy-dom')
  const window = new Window({ url: 'http://localhost/' })
  const restore = installDom(window)
  const calls = []
  stubVideoDuration(window, 90)
  try {
    const view = await mountImport(window, React, h, calls)
    await flush(act)
    await act(async () => { buttonText(view.host, '文件导入').click() })
    await act(async () => { buttonIncluding(view.host, 'YouTube 视频').click() })
    await chooseFile(window, act, view)
    assert.equal(view.host.querySelector('[role="note"]').textContent, `${TOO_SHORT} ${SKIP_OTHERS}`)
    await act(async () => { buttonText(view.host, '生成成片').click() })
    await flush(act)
    assert.equal(calls.length, 0)
    const dialog = document.querySelector('[role="dialog"]')
    assert.ok(dialog.textContent.includes(TOO_SHORT))
    assert.ok(dialog.textContent.includes(SKIP_OTHERS))
    assert.equal(dialog.textContent.includes('其他平台仍会生成'), false)
    assert.equal(dialog.textContent.includes(PICK_ANOTHER), false)
    assert.ok(buttonText(dialog, '确认并开始'))
    await act(async () => { buttonText(dialog, '确认并开始').click() })
    await flush(act)
    assert.equal(calls.length, 1)
    const platforms = [...calls[0].entries()].filter(([key]) => key === 'platforms').map(([, value]) => value)
    assert.deepEqual(platforms.sort(), ['douyin', 'youtube_long'])
    await view.unmount()
  } finally {
    try { window.happyDOM.abort?.(); window.close() } finally { restore() }
  }
})

test('a long enough file with only youtube landscape does not mention other platforms', async () => {
  const React = require('react')
  const { act } = React
  const h = React.createElement
  const { Window } = await import('happy-dom')
  const window = new Window({ url: 'http://localhost/' })
  const restore = installDom(window)
  const calls = []
  stubVideoDuration(window, 200)
  try {
    const view = await mountImport(window, React, h, calls)
    await flush(act)
    await act(async () => { buttonText(view.host, '文件导入').click() })
    await act(async () => { buttonIncluding(view.host, 'YouTube 视频').click() })
    await act(async () => { buttonIncluding(view.host, '抖音').click() })
    await chooseFile(window, act, view)
    assert.equal(view.host.querySelector('[role="note"]').textContent, NOTICE_ONLY)
    assert.equal(view.host.textContent.includes('其他平台仍会生成'), false)
    await act(async () => { buttonText(view.host, '生成成片').click() })
    await flush(act)
    assert.equal(calls.length, 0)
    const dialog = document.querySelector('[role="dialog"]')
    assert.equal(dialog.querySelector('p').textContent, NOTICE_ONLY)
    assert.equal(dialog.textContent.includes('其他平台仍会生成'), false)
    assert.ok(buttonText(dialog, '确认并开始'))
    await view.unmount()
  } finally {
    try { window.happyDOM.abort?.(); window.close() } finally { restore() }
  }
})

test('a long enough file with another platform still says the others will generate', async () => {
  const React = require('react')
  const { act } = React
  const h = React.createElement
  const { Window } = await import('happy-dom')
  const window = new Window({ url: 'http://localhost/' })
  const restore = installDom(window)
  const calls = []
  stubVideoDuration(window, 200)
  try {
    const view = await mountImport(window, React, h, calls)
    await flush(act)
    await act(async () => { buttonText(view.host, '文件导入').click() })
    await act(async () => { buttonIncluding(view.host, 'YouTube 视频').click() })
    await chooseFile(window, act, view)
    assert.equal(view.host.querySelector('[role="note"]').textContent, NOTICE)
    await act(async () => { buttonText(view.host, '生成成片').click() })
    await flush(act)
    const dialog = document.querySelector('[role="dialog"]')
    assert.ok(dialog.textContent.includes('其他平台仍会生成'))
    assert.equal(dialog.textContent.includes(SKIP_OTHERS), false)
    await view.unmount()
  } finally {
    try { window.happyDOM.abort?.(); window.close() } finally { restore() }
  }
})

test('confirm keeps the paste trigger that opened the gate', async () => {
  const React = require('react')
  const { act } = React
  const h = React.createElement
  const { Window } = await import('happy-dom')
  const window = new Window({ url: 'http://localhost/' })
  const restore = installDom(window)
  const calls = []
  try {
    const view = await mountImport(window, React, h, calls, { flagValue: key => key === 'one_click_paste_start' ? 'autostart' : 'button' })
    const realTimeout = window.setTimeout.bind(window)
    window.setTimeout = (fn, ms, ...args) => realTimeout(fn, ms === 3000 ? 0 : ms, ...args)
    await flush(act)
    await act(async () => { buttonIncluding(view.host, 'YouTube 视频').click() })
    const box = view.host.querySelector('textarea')
    const event = new window.Event('paste', { bubbles: true, cancelable: true })
    Object.defineProperty(event, 'clipboardData', { value: { getData: () => 'https://youtube.com/watch?v=abcdefghijk' } })
    await act(async () => { box.dispatchEvent(event) })
    await flush(act)
    await flush(act)
    assert.equal(calls.length, 0)
    assert.ok(document.querySelector('[role="dialog"]'))
    await act(async () => { buttonText(document.body, '确认并开始').click() })
    await flush(act)
    assert.equal(calls.length, 1)
    assert.equal(view.started[0].trigger, 'paste')
    await view.unmount()
  } finally {
    try { window.happyDOM.abort?.(); window.close() } finally { restore() }
  }
})

function installDom(window) {
  const saved = ['window', 'document', 'navigator', 'HTMLElement', 'FormData', 'File', 'URL'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)])
  Object.defineProperty(globalThis, 'window', { value: window, writable: true, configurable: true })
  Object.defineProperty(globalThis, 'document', { value: window.document, writable: true, configurable: true })
  Object.defineProperty(globalThis, 'navigator', { value: window.navigator, writable: true, configurable: true })
  Object.defineProperty(globalThis, 'HTMLElement', { value: window.HTMLElement, writable: true, configurable: true })
  Object.defineProperty(globalThis, 'FormData', { value: window.FormData, writable: true, configurable: true })
  Object.defineProperty(globalThis, 'File', { value: window.File, writable: true, configurable: true })
  Object.defineProperty(globalThis, 'URL', { value: window.URL, writable: true, configurable: true })
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  return () => {
    for (const [key, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor)
      else delete globalThis[key]
    }
  }
}

function setValue(window, node, value) {
  const proto = node instanceof window.HTMLTextAreaElement ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype
  Object.getOwnPropertyDescriptor(proto, 'value').set.call(node, value)
}

function buttonText(root, label) {
  return [...root.querySelectorAll('button')].find(node => node.textContent === label)
}

function buttonIncluding(root, label) {
  return [...root.querySelectorAll('button')].find(node => node.textContent.includes(label))
}

function stubVideoDuration(window, seconds) {
  const orig = window.document.createElement.bind(window.document)
  window.document.createElement = (tag, options) => {
    const el = orig(tag, options)
    if (tag === 'video') {
      let src = ''
      Object.defineProperty(el, 'src', {
        configurable: true,
        get: () => src,
        set(value) {
          src = String(value)
          Object.defineProperty(el, 'duration', { value: seconds })
          queueMicrotask(() => { if (typeof el.onloadedmetadata === 'function') el.onloadedmetadata() })
        },
      })
    }
    return el
  }
  window.URL.createObjectURL = () => 'blob:short'
  window.URL.revokeObjectURL = () => {}
}

async function chooseFile(window, act, view) {
  const input = view.host.querySelector('input[aria-label="视频文件"]')
  assert.ok(input)
  const file = new window.File(['x'], 'short.mp4', { type: 'video/mp4' })
  Object.defineProperty(input, 'files', { configurable: true, value: [file] })
  await act(async () => { input.dispatchEvent(new window.Event('change', { bubbles: true })) })
  await flush(act)
}

async function flush(act) {
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)) })
}

async function mountImport(window, React, h, calls, options = {}) {
  const { createRoot } = require('react-dom/client')
  const ts = require('typescript')
  const studioDir = path.resolve(__dirname, '../src/features/studio')
  const ready = { analysis_mode: 'auto', ready: true, checks: { analysis: { ok: true, code: 'ok', repair: 'none' }, transcription: { ok: true, code: 'ok', repair: 'none' }, visual: { ok: true, code: 'ok', repair: 'none' }, ffmpeg: { ok: true, code: 'ok', repair: 'none' } } }
  const started = []
  const mocks = {
    'react-i18next': { useTranslation() {} },
    '../../i18n': { t: value => value, getLocale: () => 'zh-CN' },
    antd: { Select: () => null },
    'react-router-dom': { useNavigate: () => () => {} },
    '../../ui': {
      Btn: ({ children, onClick, variant }) => h('button', { type: 'button', onClick, 'data-variant': variant || '' }, children),
      Segmented: ({ onChange, options }) => h('div', null, (options || []).map(option => h('button', { type: 'button', key: option.value, onClick: () => onChange(option.value) }, option.label))),
      Dialog: ({ open, title, description, footer }) => open ? h('div', { role: 'dialog', 'aria-label': title }, h('h3', null, title), h('p', null, description), footer) : null,
      StatusDot: () => null,
    },
    './api': {
      studioApi: {
        readiness: async () => ready,
        readinessProbe: async () => ready,
        platformStrategies: async () => ({ strategies: [] }),
        import: async body => { calls.push(body); return { project_id: 'p' } },
      },
      errorText: value => String(value),
      errorCode: () => undefined,
    },
    '../../analytics/studio': { trackQuickOutputPlatforms() {}, trackAsrReadiness() {}, trackOneClickStarted(payload) { started.push(payload) }, trackOneClickUndone() {}, trackAutoChoiceOverridden() {} },
    '../../analytics/workflow': { telemetryId: () => 't-long' },
    '../../analytics/flags': { useFlag: () => false, flagEnabled: () => false, flagValue: key => options.flagValue?.(key) ?? 'button', flagAssigned: () => false, featureSnapshot: () => ({}) },
    '../../analytics/experience': { trackExperience() {} },
    './TemplatePicker': { default: () => null, templateImportFields: () => ({}) },
    './StyleProbeLine': { default: () => null },
    './editingStyleSession': { readStyle: () => ({ key: '', result: null }) },
    './types': { defaultImportOptions: { goal: 'auto', language: 'source', aspect: null, duration: null, instruction: '' } },
    './ImportPreferences': { default: () => null },
    '../../services/api': { speechApi: { installRuntime: async () => ({}), downloadModel: async () => ({}), getRuntimeStatus: async () => ({ status: 'installed' }), getModels: async () => [] } },
    './TranscriptionGatePrompt': { default: () => null },
    './transcriptionRecovery': { isRecoveryCode: () => false, probeConfig: () => ({}) },
    './useTranscriptionRecovery': { useTranscriptionRecovery: () => [{ phase: 'idle', percent: null }, { open() {}, close() {}, install: async () => {}, retry: async () => {} }] },
    '../settings/OutputCaptionsSetting': { OutputCaptionsSwitch: () => null },
    './studio.css': {}, './quick-output.css': {},
  }
  function load(file) {
    const abs = path.join(studioDir, file)
    const { outputText } = ts.transpileModule(fs.readFileSync(abs, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
      fileName: abs,
    })
    const exports = {}
    const req = (id) => {
      if (id in mocks) return mocks[id]
      if (id === 'react' || id === 'react/jsx-runtime') return require(id)
      if (id.startsWith('.')) {
        const stem = id.replace(/^\.\//, '')
        const ext = fs.existsSync(path.join(studioDir, stem + '.tsx')) ? '.tsx' : '.ts'
        return load(stem + ext)
      }
      throw new Error('unexpected import ' + id + ' from ' + file)
    }
    runInSandbox(outputText, {
      exports, require: req, console, window, document: window.document, navigator: window.navigator,
      HTMLElement: window.HTMLElement, FormData: window.FormData, URL: window.URL, File: window.File,
      Promise, setTimeout, clearTimeout, queueMicrotask, AbortController,
    })
    return exports
  }
  const CreativeImport = load('CreativeImport.tsx').default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const root = createRoot(host)
  await React.act(async () => { root.render(h(CreativeImport, { onImported: async () => {} })) })
  return { host, started, unmount: async () => { await React.act(async () => { root.unmount() }); host.remove() } }
}

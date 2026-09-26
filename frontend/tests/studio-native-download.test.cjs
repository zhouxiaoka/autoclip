const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), ts = require('typescript')
const file = path.resolve(__dirname, '../src/features/studio/nativeDownload.ts')
function load({ desktop = true, ready = true, result = { size_bytes: 42 }, fail = false, readyResult = true } = {}) {
  const calls = [], exports = {}; let base = ready ? 'http://127.0.0.1:56101/api/v1/' : '/api/v1'
  const config = { isReady: () => ready, getBaseUrl: () => base, waitForReady: async () => { calls.push('ready'); base='http://127.0.0.1:56101/api/v1/'; return readyResult } }
  const mocks = {
    '../../utils/apiConfig': { apiConfigManager: config },
    '@tauri-apps/api/core': { invoke: async (name, args) => { calls.push({ name, ...args }); if(fail) throw Error('disk full'); return result } },
  }
  const code = ts.transpileModule(fs.readFileSync(file,'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText
  vm.runInNewContext(code, { exports, require: id => { assert.ok(mocks[id],id); return mocks[id] }, window: desktop ? { __TAURI_INTERNALS__: {} } : {} })
  return { ...exports, calls }
}
test('native download waits for backend port and saves the selected immutable job only',async()=>{
 const x=load({ready:false});await x.saveStudioExport('project','a'.repeat(32))
 assert.equal(x.calls[0],'ready');assert.equal(x.calls.length,2)
 assert.equal(x.calls[1].name,'save_local_download');assert.equal(x.calls[1].url,`http://127.0.0.1:56101/api/v1/studio/project/exports/${'a'.repeat(32)}/video?download=true`)
})
test('browser runtime does not invoke native commands',async()=>{
 const x=load({desktop:false});assert.equal(x.isDesktopDownload(),false);await assert.rejects(x.saveStudioExport('p','j'));assert.equal(x.calls.length,0)
})
test('empty files and native errors do not report success; user retry may succeed',async()=>{
 for(const result of [{size_bytes:0},{},null,{size_bytes:-1}]){const x=load({result});await assert.rejects(x.saveStudioExport('p','j'),/Empty media/)}
 await assert.rejects(load({fail:true}).saveStudioExport('p','j'),/disk full/)
 await load({result:{sizeBytes:9}}).saveStudioExport('p','j')
})

function link({ desktop = true, save } = {}) {
 const calls = [], exports = {}, refs = []
 const file = path.resolve(__dirname, '../src/features/studio/StudioDownloadLink.tsx')
 const mocks = {
  react: { useRef: value => { const ref={current:value};refs.push(ref);return ref }, useState: value => [value,()=>{}] },
  'react/jsx-runtime': { jsx: (_type,props)=>props },
  'react-i18next': { useTranslation: ()=>({t:key=>key}) },
  antd: { message: { success:()=>calls.push('success'),error:()=>calls.push('error') } },
  '../../analytics/studio': { studioDownloadRequested:()=>calls.push('intent') },
  './api': { studioApi:{video:()=>'/immutable.mp4?download=true'} },
  './nativeDownload': { isDesktopDownload:()=>desktop,saveStudioExport:save|| (async()=>{}) },
 }
 const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX}}).outputText
 vm.runInNewContext(code,{exports,require:id=>{assert.ok(mocks[id],id);return mocks[id]}})
 return {props:exports.default({projectId:'p',jobId:'j'}),calls,refs}
}
test('browser link keeps its download navigation; desktop blocks duplicate clicks while saving',async()=>{
 const web=link({desktop:false});let prevented=0;const event={preventDefault:()=>prevented++}
 await web.props.onClick(event);assert.equal(prevented,0);assert.equal(web.props.href,'/immutable.mp4?download=true');assert.equal(web.props.download,true)
 let finish;let saves=0;const app=link({save:()=>{saves++;return new Promise(resolve=>finish=resolve)}})
 const pending=app.props.onClick(event);await app.props.onClick(event);assert.equal(saves,1);assert.equal(prevented,2);assert.deepEqual(app.calls,['intent'])
 finish();await pending;assert.deepEqual(app.calls,['intent','success'])
})
test('native failure leaves the link retryable without reporting success',async()=>{
 let attempts=0;const app=link({save:async()=>{if(++attempts===1)throw Error('disk full')}})
 await app.props.onClick({preventDefault(){}});assert.deepEqual(app.calls,['intent','error']);assert.equal(app.refs[0].current,false)
 await app.props.onClick({preventDefault(){}});assert.deepEqual(app.calls,['intent','error','intent','success'])
})

test('backend readiness timeout does not invoke a stale or relative native URL',async()=>{
 const x=load({ready:false,readyResult:false});await assert.rejects(x.saveStudioExport('p','j'),/Backend not ready/);assert.deepEqual(x.calls,['ready'])
})

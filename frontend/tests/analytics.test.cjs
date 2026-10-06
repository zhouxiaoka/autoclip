const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

// Compile the actual source in memory. No new runner dependency or network calls.
function load(name, mocks = {}, globals = {}) {
  const file = path.join(__dirname, '../src/analytics', `${name}.ts`)
  const source = fs.readFileSync(file, 'utf8').replaceAll('import.meta.env', '__env')
  const js = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true,
  } }).outputText
  const module = { exports: {} }
  vm.runInNewContext(js, { exports: module.exports, module, Blob, Date, Math, console,
    __env: { DEV: false, VITE_PUBLIC_POSTHOG_KEY: 'test-only-not-a-real-key' },
    require: (id) => {
      if (id in mocks) return mocks[id]
      throw new Error(`Unexpected dependency: ${id}`)
    }, ...globals }, { filename: file })
  return module.exports
}
const core = load('workflow')
function memory() {
  const data = new Map()
  return { getItem: k => data.get(k) ?? null, setItem: (k, v) => data.set(k, v), removeItem: k => data.delete(k) }
}
const NOW = Date.parse('2026-09-21T01:00:00Z')
function setup(storage = memory(), clock = () => NOW) {
  const events = []
  let enabled = true
  let accepted = true
  const capture = (event, props) => { if (!accepted) return false; events.push({ event, props }); return true }
  const tracker = new core.WorkflowTracker(storage, () => enabled, capture, clock)
  return { tracker, events, storage, capture, enable: v => enabled = v, accept: v => accepted = v }
}
const task = overrides => ({ id: 'task-1', task_type: 'video_processing', status: 'completed',
  created_at: '2026-09-21T01:00:00', started_at: '2026-09-21T01:00:01Z',
  completed_at: '2026-09-21T01:00:06Z', ...overrides })

test('quick-output properties accept only bounded platform and branding fields', () => {
  const props = core.safeStudioProperties({
    strategy_id: 'tiktok', material_origin: 'user', generation_reason: 'platform_append',
    platform_count: 2, variant_count: 3, completed_variant_count: 2, brand_outro_enabled: true,
    project_id: 'private-project', filename: 'private.mp4', reason: 'raw user text', url: 'https://private.example',
  })
  assert.equal(props.studio_schema_version, 2)
  assert.equal(props.strategy_id, 'tiktok')
  assert.equal(props.material_origin, 'user')
  assert.equal(props.generation_reason, 'platform_append')
  assert.equal(props.platform_count, 2)
  assert.equal(props.variant_count, 3)
  assert.equal(props.completed_variant_count, 2)
  assert.equal(props.brand_outro_enabled, true)
  assert.equal(JSON.stringify(props).includes('private'), false)
  assert.equal(core.safeStudioProperties({ strategy_id: 'untrusted', generation_reason: 'raw text', platform_count: -1 }).strategy_id, undefined)
})


test('duplicate polling and restart preserve deduplication, actual duration and stable IDs', () => {
  const s = setup(); s.tracker.watch('project', 'p')
  const w = s.tracker.list()[0]
  s.tracker.observeTasks(w, [task()]); s.tracker.observeTasks(w, [task()])
  assert.equal(s.events.length, 3)
  assert.equal(s.events[2].props.duration_ms, 5000)
  const recovered = new core.WorkflowTracker(s.storage, () => true, s.capture, () => NOW)
  recovered.observeTasks(recovered.list()[0], [task()])
  assert.equal(s.events.length, 3)
  assert.equal(new Set(s.events.map(e => e.props.$insert_id)).size, 3)
})
test('historical/non-processing tasks excluded; retries with new task IDs counted', () => {
  const s = setup(); s.tracker.watch('project', 'p'); let w = s.tracker.list()[0]
  s.tracker.observeTasks(w, [task({ created_at: '2026-09-20T01:00:00Z' }), task({ task_type: 'cleanup' })])
  assert.equal(s.events.length, 0)
  s.tracker.observeTasks(w, [task({ status: 'failed' })])
  s.tracker.watch('project', 'p'); w = s.tracker.list()[0]
  s.tracker.observeTasks(w, [task({ id: 'retry-2' })])
  assert.equal(s.events.filter(e => e.event === 'processing_finished').length, 2)
})
test('missing worker timestamps do not invent start or duration; cancellation is distinct', () => {
  const s = setup(); s.tracker.watch('project', 'p')
  s.tracker.observeTasks(s.tracker.list()[0], [task({ status: 'cancelled', started_at: null, completed_at: null })])
  assert.equal(s.events.length, 2)
  assert.equal(s.events[1].props.outcome, 'cancelled')
  assert.equal(s.events[1].props.duration_ms, undefined)
  assert.equal(s.events[1].props.occurred_at, undefined)
})
test('opt-out clears pending watches, invalidates in-flight generation and never replays', () => {
  const s = setup(); s.tracker.watch('project', 'p'); const old = s.tracker.list()[0]
  const generation = s.tracker.generation()
  s.enable(false); assert.equal(s.tracker.list().length, 0)
  s.enable(true); assert.equal(s.tracker.active(generation), false)
  s.tracker.observeTasks(old, [task()]); assert.equal(s.events.length, 0)
  assert.equal(new core.WorkflowTracker(s.storage, () => true, s.capture, () => NOW).list().length, 0)
})
test('failed enqueue is retried; invalid storage and blocked localStorage do not throw', () => {
  const s = setup(); s.tracker.watch('project', 'p'); const w = s.tracker.list()[0]
  s.accept(false); s.tracker.observeTasks(w, [task()]); assert.equal(w.seen.length, 0)
  s.accept(true); s.tracker.observeTasks(w, [task()]); assert.equal(s.events.length, 3)
  const blocked = { getItem() { throw Error('blocked') }, setItem() { throw Error('blocked') }, removeItem() { throw Error('blocked') } }
  const b = setup(blocked); b.tracker.watch('project', 'p'); b.tracker.clear()
  const broken = memory(); broken.setItem(core.WORKFLOW_KEY, '{bad'); assert.equal(setup(broken).tracker.list().length, 0)
})
test('watch retention and capacity bounded', () => {
  const s = setup()
  s.tracker.watch('project', 'old', undefined, NOW - 8 * 86400000)
  for (let i = 0; i < 60; i++) s.tracker.watch('project', `p${i}`)
  assert.equal(s.tracker.list().length, 50)
  assert.equal(s.tracker.list().some(w => w.id === 'old'), false)
})
test('errors and routes contain no original secrets, paths or search parameters', () => {
  assert.equal(core.routeName('/project/private-id?token=secret'), '/project/:id')
  assert.equal(core.routeName('/other/secret'), '/other')
  assert.equal(core.errorCode({response:{status:'private'}}), 'unknown')
  assert.equal(core.errorCode({ message: 'sk-secret /Users/person.mp4', response: { status: 401 } }), 'http_401')
  assert.equal(core.errorCode({ message: 'secret' }), 'unknown')
})
test('persisted opt-out skips SDK initialization and can be enabled later without double init', () => {
  const storage = memory(); storage.setItem('autoclip.analytics.optOut', 'true')
  const calls = []; let config
  const sdk = {
    init(_key, cfg) { calls.push('init'); config = cfg },
    capture() { calls.push('capture'); return {} },
    opt_out_capturing() { calls.push('out') }, opt_in_capturing() { calls.push('in') },
  }
  const ph = load('posthog', { 'posthog-js': sdk, './workflow': core }, { localStorage: storage, window: {} })
  ph.initAnalytics(); ph.initAnalytics(); ph.setAnalyticsEnabled(false)
  assert.equal(ph.captureBusinessEvent('disabled'), false)
  assert.deepEqual(calls, [])
  ph.setAnalyticsEnabled(true)
  assert.equal(config.advanced_disable_flags, true)
  assert.equal(ph.captureBusinessEvent('enabled'), true)
  ph.setAnalyticsEnabled(false)
  assert.equal(ph.captureBusinessEvent('disabled-again'), false)
  ph.setAnalyticsEnabled(true); ph.initAnalytics()
  assert.equal(calls.filter(call => call === 'init').length, 1)
  assert.equal(calls.filter(call => call === 'capture').length, 1)
  assert.equal(storage.getItem('autoclip.analytics.optOut'), 'false')
})
test('opt-out override prevents SDK initialization even when localStorage is unavailable', () => {
  let initialized = 0
  const sdk = { init() { initialized += 1 } }
  const blocked = { getItem() { throw Error('blocked') }, setItem() { throw Error('blocked') } }
  const ph = load('posthog', { 'posthog-js': sdk, './workflow': core }, { localStorage: blocked, window: {} })
  ph.setAnalyticsEnabled(false); ph.initAnalytics()
  assert.equal(initialized, 0)
  assert.equal(ph.captureBusinessEvent('disabled'), false)
})
test('SDK exceptions and unavailable storage cannot break business or override opt-out', () => {
  const captured = []; let config
  const sdk = { init(_key, cfg) { config = cfg }, capture(name, props) { captured.push({ name, props }); return {} },
    opt_out_capturing() {}, opt_in_capturing() {} }
  const blocked = { getItem() { throw Error('blocked') }, setItem() { throw Error('blocked') } }
  const ph = load('posthog', { 'posthog-js': sdk, './workflow': core }, { localStorage: blocked, window: {} })
  ph.initAnalytics(); ph.trackPageview('/project/private?key=secret')
  assert.equal(captured[0].props.route, '/project/:id')
  assert.equal(config.autocapture, false)
  assert.equal(config.disable_session_recording, true)
  ph.setAnalyticsEnabled(false); assert.equal(ph.captureBusinessEvent('test'), false)
  assert.equal(captured.length, 1)
  ph.setAnalyticsEnabled(true); sdk.capture = () => { throw Error('sdk') }
  assert.equal(ph.captureBusinessEvent('test'), false)
})
test('downloads count nonempty bytes, preserve request failure, and stop after consent changes', async () => {
  const s = setup()
  const operations = load('operations', { './posthog': { captureBusinessEvent: s.capture }, './observer': { workflow: s.tracker }, './workflow': core })
  const props = { artifact_type: 'publish_clip' }
  const blob = new Blob(['video'])
  assert.equal(await operations.observeDownload(props, async () => blob), blob)
  assert.equal(s.events.filter(e => e.event === 'media_download_received').length, 1)
  await assert.rejects(operations.observeDownload(props, async () => new Blob([])), /Empty/)
  assert.equal(s.events.filter(e => e.event === 'media_download_received').length, 1)
  const failure = { response: { status: 403 }, message: 'token=secret' }
  await assert.rejects(operations.observeDownload(props, async () => { throw failure }), e => e === failure)
  assert.equal(JSON.stringify(s.events).includes('secret'), false)
  let finish; const pending = operations.observeDownload(props, () => new Promise(r => { finish = r }))
  s.tracker.clear(); finish(blob); await pending
  assert.equal(s.events.filter(e => e.event === 'media_download_received').length, 1)
})

test('actual API entrypoints enroll imports/exports and count every media download path', async () => {
  const s = setup(memory(), () => Date.now())
  const ph = { captureBusinessEvent: s.capture }
  const operations = load('operations', { './posthog': ph, './observer': { workflow: s.tracker }, './workflow': core })
  const blob = new Blob(['video'])
  const transport = {
    defaults: {}, interceptors: { request: { use() {} }, response: { use() {} } },
    async post(url) {
      if (url === '/projects/upload') return { id: 'uploaded' }
      if (url === '/bilibili/download') return { id: 'bilibilitask' }
      if (url === '/youtube/download') return { id: 'youtubetask' }
      if (url.includes('/clips/')) return { ok: true, job_id: 'exportjob' }
      if (url === '/settings/test-api') return { success: false, error: 'secret' }
      return {}
    },
    async get() { return blob },
  }
  const api = load('../services/api', {
    '../i18n': { t: key => key },
    axios: { create: () => transport, get: async () => ({ data: blob, headers: {} }) },
    '../utils/errorHandler': { errorHandler: { handleError() {} } },
    '../utils/apiConfig': { apiConfigManager: { getBaseUrl: () => '/api/v1', addListener() {} } },
    '../analytics/workflow': core, '../analytics/operations': operations, '../analytics/observer': { workflow: s.tracker },
    '../analytics/posthog': ph,
    '../analytics/events': { trackVideoImported() {}, trackClipsExported() {}, trackProcessingFailed() {} },
  }, { FormData, window: { URL: { createObjectURL: () => 'blob:test', revokeObjectURL() {} } },
    document: { createElement: () => ({ click() {} }), body: { appendChild() {}, removeChild() {} } } })
  await api.projectApi.uploadFiles({ video_file: blob, project_name: 'private-name' })
  await api.bilibiliApi.createDownloadTask({ url: 'https://private.invalid/secret' })
  await api.bilibiliApi.createYouTubeDownloadTask({ url: 'https://private.invalid/secret' })
  await api.projectApi.startClipExport('p', 'clip', { preset: 'portrait', subtitles: true })
  await api.projectApi.downloadClip('p', 'clip')
  await api.projectApi.downloadCollection('p', 'collection')
  await api.projectApi.downloadVideo('p', 'clip')
  await api.projectApi.downloadVideo('p', undefined, 'collection')
  await api.projectApi.downloadExport('p', 'exportjob')
  await api.settingsApi.testApiKey('dashscope', 'sk-secret')
  assert.equal(s.events.filter(e => e.event === 'media_download_received').length, 5)
  assert.equal(s.events.find(e => e.event === 'provider_test_finished').props.outcome, 'failed')
  assert.equal(JSON.stringify(s.events).includes('secret'), false)
  assert.equal(s.tracker.list().length, 4)
  const accepted = s.events.filter(e => e.event.endsWith('_accepted'))
  assert.equal(accepted.filter(e => e.event === 'import_accepted').length, 3)
  assert.equal(accepted.filter(e => e.event === 'publish_export_accepted').length, 1)
})

test('Studio phases dedupe locally across restart without sending internal IDs or content', () => {
  const s = setup()
  s.tracker.watch('studio-production', 'secret-plan', 'secret-project')
  const w = s.tracker.list()[0]
  s.tracker.observeStudio(w, {plan:{id:'other-plan'},analysis:{status:'completed'}})
  assert.equal(s.events.length,0)
  const snapshot={plan:{id:'secret-plan'},analysis:{status:'failed',error:'sk-secret /Users/private.mp4'}}
  s.tracker.observeStudio(w,snapshot);s.tracker.observeStudio(w,snapshot)
  const recovered=new core.WorkflowTracker(s.storage,()=>true,s.capture,()=>NOW)
  recovered.observeStudio(recovered.list()[0],snapshot)
  assert.equal(s.events.length,1)
  assert.equal(s.events[0].props.studio_schema_version,2)
  assert.equal(s.events[0].props.outcome,'failed')
  assert.equal(JSON.stringify(s.events).includes('secret'),false)
  s.tracker.watch('studio-export','secret-job','secret-project')
  s.tracker.observeStudio(s.tracker.list()[1],{jobs:[{job_id:'secret-job',status:'completed'}]})
  assert.equal(s.events[1].event,'studio_export_finished')
  s.enable(false);s.tracker.list();s.enable(true)
  s.tracker.observeStudio(w,snapshot)
  assert.equal(s.events.length,2)
})
test('Studio screening distinguishes recommendations, manual fallback and import failure',()=>{
  for (const [snapshot,outcome] of [[{plan:{id:'plan',mode:'ai'},analysis:{status:'awaiting_confirmation'}},'recommended'],[{plan:{id:'plan',mode:'fallback'},analysis:{status:'awaiting_confirmation'}},'fallback'],[{analysis:{status:'failed'}},'failed']]) {
    const s=setup();s.tracker.watch('studio-screen','private-project')
    s.tracker.observeStudio(s.tracker.list()[0],snapshot)
    assert.equal(s.events[0].props.outcome,outcome)
    assert.equal(s.events[0].props.studio_schema_version,2)
  }
})
test('actual Studio API enrolls accepted work and sends aggregate-only telemetry',async()=>{
  const s=setup(memory(),()=>Date.now())
  const aggregate=load('studio',{'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
  const transport={defaults:{},post:async(url)=>url==='/studio/import'?{project_id:'private-project'}:url.endsWith('/export')?{job_id:'private-job'}:{}}
  const file=path.join(__dirname,'../src/features/studio/api.ts')
  const js=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,esModuleInterop:true}}).outputText
  const module={exports:{}}
  vm.runInNewContext(js,{module,exports:module.exports,require:id=>({'../../analytics/workflow':core,'../../analytics/posthog':{captureBusinessEvent:s.capture},'../../services/api':transport,'../../analytics/studio':aggregate,'../../analytics/observer':{workflow:s.tracker}}[id])})
  const api=module.exports.studioApi
  await api.import({filename:'private.mp4',url:'https://private.test/?key=secret'})
  await api.confirmPlan('private-project','private-plan',['highlight'],{language:'source'})
  await api.export('private-project','private-draft',2)
  assert.equal(s.tracker.list().length,3)
  assert.equal(s.events.length,6)
  assert.equal(JSON.stringify(s.events).includes('private'),false)
  assert.equal(JSON.stringify(s.events).includes('secret'),false)
  for(const e of s.events) assert.ok(Object.keys(e.props).every(k=>['operation_id','flow_id','material_origin','auto_frame_retained','has_crop_track','has_manual_adjustment','studio_schema_version','request_duration_ms','source_type','has_subtitle','aspect','portrait_style','platform_count','brand_outro_enabled','goal_content','goal_highlight','goal_promo'].includes(k)))
  s.enable(false)
  await api.import({})
  assert.equal(s.events.length,6)
})
test('Studio aggregate requests retain failures and respect consent changes in flight',async()=>{
  const s=setup();const aggregate=load('studio',{'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
  const failure={response:{status:401},message:'private-key'}
  await assert.rejects(aggregate.observeStudioOperation('studio_export',async()=>{throw failure},()=>{}),e=>e===failure)
  assert.equal(s.events[1].props.error_code,'http_401')
  assert.equal(JSON.stringify(s.events).includes('private-key'),false)
  let finish;let accepted=false
  const pending=aggregate.observeStudioOperation('studio_import',()=>new Promise(r=>{finish=r}),()=>{accepted=true})
  s.tracker.clear();finish({project_id:'secret'});await pending
  assert.equal(accepted,false)
  assert.equal(s.events.length,3)
})

test('Studio allowlist rejects arbitrary values and preserves per-run partial counts',()=>{
 const props=core.safeStudioProperties({source_type:'secret',analysis_mode:'visual',title:'private',duration_ms:-1,goal:'private',requested_goals:['highlight','promo'],succeeded_goals:['highlight'],failed_goals:['promo'],error_code:'http_secret'})
 assert.equal(props.requested_count,2);assert.equal(props.failed_promo,true)
 assert.equal(JSON.stringify(props).includes('secret'),false);assert.equal(JSON.stringify(props).includes('private'),false)
 const s=setup();s.tracker.watch('studio-production','plan','project')
 s.tracker.observeStudio(s.tracker.list()[0],{plan:{id:'plan',confirmed_analysis:'visual'},analysis:{status:'failed',outcome:'partial',requested_goals:['highlight','promo'],succeeded_goals:['highlight'],failed_goals:['promo'],result_count:2,duration_ms:321}})
 const p=s.events[0].props;assert.equal(p.outcome,'partial');assert.equal(p.succeeded_highlight,true);assert.equal(p.failed_count,1);assert.equal(p.duration_ms,321);assert.equal(p.analysis_mode,'visual')
})
test('rescreen ignores an old plan while running and replaces the old local watch',()=>{
 const s=setup();s.tracker.watch('studio-screen','p');const old=s.tracker.list()[0]
 s.tracker.watch('studio-screen','p',undefined,undefined,{},true);const current=s.tracker.list()[0]
 s.tracker.observeStudio(old,{plan:{id:'old',mode:'ai'},analysis:{status:'awaiting_confirmation'}})
 s.tracker.observeStudio(current,{plan:{id:'old',mode:'ai'},analysis:{status:'running'}})
 assert.equal(s.events.length,0)
 s.tracker.observeStudio(current,{plan:{id:'new',mode:'local',local_evidence:{subtitle_status:'available'}},analysis:{status:'awaiting_confirmation'}})
 assert.equal(s.events[0].props.outcome,'recommended');assert.equal(s.events[0].props.recommendation_mode,'local')
 assert.equal(core.routeName('/import/private?token=secret'),'/import/:id')
 assert.equal(core.routeName('/project/private/studio/secret'),'/project/:id/studio/:draftId')
})
test('immutable export repeated acceptance does not recount its completion',()=>{
 const s=setup();s.tracker.watch('studio-export','j','p');const w=s.tracker.list()[0]
 s.tracker.observeStudio(w,{jobs:[{job_id:'j',status:'completed',duration_ms:20}]})
 const insert=s.events[0].props.$insert_id
 s.tracker.watch('studio-export','j','p');s.tracker.observeStudio(s.tracker.list()[0],{jobs:[{job_id:'j',status:'completed'}]})
 assert.equal(s.events.length,1);assert.ok(insert.startsWith('studio-v1:'))
})
test('native download emits saved or failed, and opt-out in flight suppresses results',async()=>{
 const s=setup();const aggregate=load('studio',{'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
 await aggregate.observeStudioDownload(async()=>42)
 assert.equal(s.events[1].event,'studio_download_saved')
 await assert.rejects(aggregate.observeStudioDownload(async()=>{throw Error('private filename')}))
 assert.equal(s.events[3].event,'studio_download_failed');assert.equal(JSON.stringify(s.events).includes('private'),false)
 let finish;const pending=aggregate.observeStudioDownload(()=>new Promise(r=>finish=r));s.tracker.clear();finish();await pending
 assert.equal(s.events.length,5)
})

test('social publishing distinguishes scheduling and inbox acceptance from published content',()=>{
 const s=setup();const aggregate=load('studio',{'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
 assert.equal(aggregate.socialPublishOutcome('scheduled',true,[]),'scheduled')
 assert.equal(aggregate.socialPublishOutcome('submitted',false,[{success:true,fallback_to_inbox:true}]),'inbox')
 assert.equal(aggregate.socialPublishOutcome('completed',false,[]),'unknown')
 assert.equal(aggregate.socialPublishOutcome('completed',false,[{success:true},{success:false}]),'partial')
 assert.equal(aggregate.socialPublishOutcome('completed',false,[{success:false}]),'failed')
 aggregate.socialPublishObserved(s.tracker.generation(),{source_type:'studio',gateway:'bilibili',outcome:'completed',url:'private'})
 assert.equal(s.events[0].props.source_type,'studio');assert.equal(JSON.stringify(s.events).includes('private'),false)
 const gen=s.tracker.generation();s.tracker.clear();aggregate.socialPublishObserved(gen,{outcome:'completed'});assert.equal(s.events.length,1)
})

test('UI workspace snapshots capture fast screening before confirm and never enroll historical projects',async()=>{
 const s=setup();const aggregate=load('studio',{'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
 const snapshot={plan:{id:'plan',mode:'local'},analysis:{status:'awaiting_confirmation'}}
 await aggregate.observeStudioWorkspace('p',async()=>snapshot);assert.equal(s.events.length,0)
 s.tracker.watch('studio-screen','p')
 assert.equal(await aggregate.observeStudioWorkspace('p',async()=>snapshot),snapshot)
 assert.equal(s.events.length,1);assert.equal(s.events[0].props.recommendation_mode,'local')
 await aggregate.observeStudioWorkspace('p',async()=>snapshot);assert.equal(s.events.length,1)
 assert.equal(core.safeStudioProperties(null).studio_schema_version,2)
})

test('late workspace response cannot settle a newer rescreen attempt',async()=>{
 const s=setup();const aggregate=load('studio',{'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
 s.tracker.watch('studio-screen','p');let finish
 const pending=aggregate.observeStudioWorkspace('p',()=>new Promise(r=>finish=r))
 s.tracker.watch('studio-screen','p',undefined,undefined,{},true)
 finish({plan:{id:'old',mode:'ai'},analysis:{status:'awaiting_confirmation'}});await pending
 assert.equal(s.events.length,0)
})

test('readable but full storage cannot override an immediate opt-out', () => {
  const captured=[]
  const ph=load('posthog',{'posthog-js':{init(){},capture(...args){captured.push(args);return {}},opt_out_capturing(){},opt_in_capturing(){}},'./workflow':core},{localStorage:{getItem(){return null},setItem(){throw Error('quota')}},window:{}})
  ph.initAnalytics();ph.setAnalyticsEnabled(false)
  assert.equal(ph.isAnalyticsEnabled(),false);assert.equal(ph.captureBusinessEvent('blocked'),false)
  assert.equal(captured.length,0)
  ph.setAnalyticsEnabled(true);assert.equal(ph.captureBusinessEvent('allowed',{schema_version:999,runtime:'private'}),true)
  assert.equal(captured[0][1].schema_version,2);assert.equal(captured[0][1].runtime,'web')
})

test('sample classification and opaque flow/artifact survive restart and clear on opt-out', () => {
  const s=setup();s.tracker.rememberProject('private-project',core.projectProperties({settings:{example:true,example_version:2,secret:'sk-secret'}}))
  const first=s.tracker.context('private-project','private-job')
  assert.equal(first.material_origin,'sample');assert.equal(first.example_version,2)
  assert.match(first.flow_id,/^t-/);assert.match(first.artifact_id,/^t-/)
  const restored=new core.WorkflowTracker(s.storage,()=>true,s.capture,()=>NOW)
  assert.equal(restored.context('private-project','private-job').artifact_id,first.artifact_id)
  restored.rememberProject('real-project',{material_origin:'user'})
  assert.equal(restored.context('real-project').material_origin,'user')
  assert.notEqual(restored.context('real-project').flow_id,first.flow_id)
  assert.equal(JSON.stringify(first).includes('private'),false)
  restored.clear();assert.equal(restored.context('private-project').material_origin,'unknown')
})

test('immutable receipts recover the right run after a newer plan replaced current state', () => {
  const s=setup();s.tracker.rememberProject('p',{material_origin:'sample'})
  s.tracker.watch('studio-production','old-plan','p',undefined,{},false,'old-run')
  const w=s.tracker.list()[0]
  s.tracker.observeStudio(w,{material_origin:'sample',plan:{id:'new-plan'},analysis:{run_id:'new-run',phase:'screening',status:'running'},analysis_history:[{run_id:'old-run',plan:{id:'old-plan',confirmed_analysis:'subtitle'},analysis:{phase:'production',status:'completed'}}]})
  s.tracker.observeStudio(w,{plan:{id:'new-plan'},analysis:{status:'failed'}})
  assert.equal(s.events.length,1);assert.equal(s.events[0].props.outcome,'completed');assert.equal(s.events[0].props.material_origin,'sample')
  assert.equal(JSON.stringify(s.events).includes('old-run'),false)
  s.tracker.watch('studio-screen','p',undefined,undefined,{},true,'screen-run')
  s.tracker.observeStudio(s.tracker.list()[1],{analysis:{run_id:'production-run',phase:'production',status:'failed'}})
  assert.equal(s.events.length,1)
})

test('experience contract excludes config secrets and results cannot replay across consent changes', () => {
  const s=setup();const x=load('experience',{'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
  const finish=x.beginExperience('provider_connection_test',{provider:'openai',placement:'home_setup',api_key:'sk-secret',model:'private-model',base_url:'https://private'})
  finish('failed',{error:'sk-secret'});finish('completed')
  assert.equal(s.events.length,2);assert.equal(s.events[1].props.outcome,'failed')
  assert.equal(JSON.stringify(s.events).includes('secret'),false);assert.equal(JSON.stringify(s.events).includes('private'),false)
  const late=x.beginExperience('model_discovery',{provider:'openai'});s.tracker.clear();late('completed',{result_count:9})
  assert.equal(s.events.length,3)
})

function settingsHook(s, transport, initial) {
  let cursor=0;const slots=[]
  const react={useState(value){const i=cursor++;if(!(i in slots))slots[i]=value;return [slots[i],next=>{slots[i]=typeof next==='function'?next(slots[i]):next}]},useRef(value){const i=cursor++;if(!(i in slots))slots[i]={current:value};return slots[i]},useEffect(){}}
  const providers={PROVIDERS:{openai:{}},}
  const defaults=load('../features/settings/modelDefaults')
  const logic=load('../features/settings/modelSettingsLogic',{'./providers':providers,'./modelDefaults':defaults})
  const experience=load('experience',{'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
  const hook=load('../features/settings/useModelSettings',{
    react,antd:{message:{success(){},error(){}}},'../../i18n':{t:x=>x},'../studio/api':{errorText:()=> 'redacted'},
    '../../analytics/experience':experience,'./providers':providers,'./modelSettingsApi':{modelSettingsApi:{get:async()=>structuredClone(initial),...transport},bindingCapability:()=> 'text'},
    './modelDefaults':defaults,'./modelSettingsLogic':logic,
  },{window:{setTimeout(){},clearTimeout(){},addEventListener(){},removeEventListener(){}}})
  return ()=>{cursor=0;return hook.useModelSettings('home_setup')}
}
const modelFixture=()=>({version:1,saved:false,connections:[{id:'private-id',provider:'openai',api_key:'sk-secret',has_key:true,base_url:'https://private',name:'private'}],analysis:{connection_id:'private-id',model:'private-model',capability:'text'},vision:null,cover:null,cover_enabled:false,allow_send_frame:false,analysis_mode:'subtitle',allow_visual_screening:false,transcription:{provider:'whisper_local',model:'base'},chunk_size:2000,min_score_threshold:.7,max_clips_per_collection:5})
test('actual unified settings hook records save once and HTTP-200 negative tests as failures',async()=>{
 const s=setup();const render=settingsHook(s,{discover:async()=>({models:[],source:'catalog',preview:true}),save:async value=>({...value,saved:true}),test:async()=>({success:false})},modelFixture())
 await render().load();await Promise.resolve();let m=render();await m.save();m=render();await m.test()
 assert.equal(s.events.filter(e=>e.event==='provider_configuration_save_finished').length,1)
 assert.equal(s.events.find(e=>e.event==='provider_configuration_save_finished').props.mode,'initial')
 assert.equal(s.events.find(e=>e.event==='provider_connection_test_finished').props.outcome,'failed')
 assert.equal(s.events.some(e=>e.event==='api_key_configured'),false)
 assert.equal(JSON.stringify(s.events).includes('sk-secret'),false);assert.equal(JSON.stringify(s.events).includes('private'),false)
})
test('actual discovery ignores stale completions and distinguishes preview from live results',async()=>{
 const s=setup();let pending=[]
 const render=settingsHook(s,{discover:()=>new Promise(resolve=>pending.push(resolve))},modelFixture())
 await render().load();const m=render();const c=m.settings.connections[0]
 const second=m.discover(c,true,'manual')
 pending[0]({models:[],source:'catalog',preview:true});await Promise.resolve()
 pending[1]({models:[{id:'private-model',analysis:true}],source:'live',preview:false});await second
 const results=s.events.filter(e=>e.event==='model_discovery_finished')
 assert.equal(results.length,1);assert.equal(results[0].props.source,'live');assert.equal(results[0].props.trigger,'manual')
})

test('sample render and native save share an artifact without exposing backend IDs',async()=>{
 const s=setup();const aggregate=load('studio',{'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
 s.tracker.rememberProject('private-sample',{material_origin:'sample',example_version:1})
 const ctx=s.tracker.context('private-sample','private-job')
 s.tracker.watch('studio-export','private-job','private-sample',undefined,ctx)
 s.tracker.observeStudio(s.tracker.list()[0],{material_origin:'sample',jobs:[{job_id:'private-job',status:'completed'}]})
 aggregate.studioDownloadRequested('private-sample','private-job')
 assert.equal(s.events.some(e=>e.event==='studio_download_saved'),false)
 await aggregate.observeStudioDownload(async()=>42,'private-sample','private-job')
 for(const event of s.events){assert.equal(event.props.material_origin,'sample');assert.equal(event.props.artifact_id,ctx.artifact_id);assert.equal(event.props.flow_id,ctx.flow_id)}
 assert.equal(JSON.stringify(s.events).includes('private'),false)
})
test('retrying the same plan retains both execution attempts until independently observed',()=>{
 const s=setup()
 s.tracker.watch('studio-production','plan','p',undefined,{},false,'run-first')
 s.tracker.watch('studio-production','plan','p',undefined,{},false,'run-second')
 const state={plan:{id:'plan'},analysis:{status:'completed',phase:'production',run_id:'run-second'},analysis_history:[{run_id:'run-first',plan:{id:'plan'},analysis:{status:'failed',phase:'production'}}]}
 for(const watch of s.tracker.list())s.tracker.observeStudio(watch,state)
 assert.equal(s.events.length,2)
 assert.deepEqual(s.events.map(e=>e.props.outcome),['failed','completed'])
 assert.notEqual(s.events[0].props.attempt_id,s.events[1].props.attempt_id)
})

test('actual auto-frame API distinguishes automatic zero detection from retained edits',async()=>{
 const s=setup();const aggregate=load('studio',{'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
 const api=load('../features/studio/api',{'../../analytics/workflow':core,'../../analytics/posthog':{captureBusinessEvent:s.capture},'../../services/api':{post:async()=>({scenes:[{crop_x:null,fit_shots:2}]})},'../../analytics/studio':aggregate,'../../analytics/observer':{workflow:s.tracker}})
 s.tracker.rememberProject('private-project',{material_origin:'user'})
 await api.studioApi.autoFrame('private-project',{layout:'crop',scenes:[]},'auto')
 const event=s.events.find(e=>e.event==='studio_auto_frame_finished')
 assert.equal(event.props.framing_outcome,'no_detection');assert.equal(event.props.trigger,'auto')
 assert.equal(event.props.fit_count,2);assert.equal(event.props.framed_count,0)
 const draft={layout:'crop',scenes:[{framing_source:'auto',crop_track:[{private:42}]}]}
 assert.equal(api.draftProperties(draft).auto_frame_retained,true)
 draft.scenes[0].framing_adjusted=true
 assert.equal(api.draftProperties(draft).auto_frame_retained,false)
 assert.equal(api.draftProperties(draft).has_manual_adjustment,true)
 assert.equal(JSON.stringify(s.events).includes('private'),false)
})

test('framing installation retries use distinct terminal deduplication keys',()=>{
 const s=setup();const inserts=[]
 for(let i=0;i<2;i++){
  s.tracker.watch('framing-runtime','runtime',undefined,undefined,{},true)
  const watch=s.tracker.list()[0]
  s.tracker.emitOnce(watch,'finished','studio_framing_install_finished',{outcome:i?'completed':'failed'})
  inserts.push(s.events[i].props.$insert_id)
 }
 assert.notEqual(inserts[0],inserts[1])
 assert.equal(s.events[0].props.studio_schema_version,2)
})

test('1.5 API observes cover and retry terminal results across restart without content',async()=>{
 const s=setup()
 const aggregate=load('studio',{'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
 const transport={post:async url=>url.endsWith('/cover/ai')?{job_id:'private-cover',status:'queued'}:{job_id:'private-new-render',status:'queued'},get:async()=>({job_id:'private-cover',status:'completed'}),put:async()=>({title:'private-title',description:'private-description',tags:['private-tag']})}
 const api=load('../features/studio/api',{'../../analytics/workflow':core,'../../analytics/posthog':{captureBusinessEvent:s.capture},'../../services/api':transport,'../../analytics/studio':aggregate,'../../analytics/observer':{workflow:s.tracker}}).studioApi
 s.tracker.rememberProject('private-project',{material_origin:'user'})
 await api.redesignVariantCover('private-project','private-variant')
 await api.variantCoverJob('private-project','private-variant') // terminal before the global poll
 assert.equal(s.events.filter(e=>e.event==='studio_cover_redesign_finished').length,1)
 await api.retryOutputVariant('private-project','private-variant')
 await api.updateVariantPost('private-project','private-variant',{title:'private-title',description:'private-description',tags:['private-tag']})
 const recovered=new core.WorkflowTracker(s.storage,()=>true,s.capture,()=>NOW)
 const snapshot={output_variants:[{id:'private-variant',draft_id:'private-draft',render_job_id:'private-old-render',strategy_id:'douyin',status:'failed',cover_job:{job_id:'private-cover',status:'completed'}}]}
 for(const w of recovered.list())recovered.observeStudio(w,snapshot)
 assert.equal(s.events.filter(e=>e.event==='studio_cover_redesign_finished').length,1)
 assert.equal(s.events.filter(e=>e.event==='studio_variant_finished').length,0) // not this retry
 snapshot.output_variants[0].render_job_id='private-new-render';snapshot.output_variants[0].status='completed'
 snapshot.jobs=[{job_id:'private-new-render',status:'completed',result:{outro_applied:false,warnings:['private error']}}]
 for(const w of recovered.list()){recovered.observeStudio(w,snapshot);recovered.observeStudio(w,snapshot)}
 const finished=s.events.filter(e=>e.event==='studio_variant_finished')
 assert.equal(finished.length,1);assert.equal(finished[0].props.outcome,'completed');assert.equal(finished[0].props.outro_applied,false);assert.equal(finished[0].props.warning_count,1)
 assert.equal(JSON.stringify(s.events).includes('private'),false)
 assert.equal(s.events.filter(e=>e.event==='studio_post_save_accepted').length,1)
})

test('publish kit saving has disk evidence; browser clicks and opt-out never invent success',async()=>{
 const s=setup();const x=load('studio',{'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
 const props={artifact_type:'publish_kit',strategy_id:'douyin'}
 x.studioDownloadRequested('private-project','private-render',props)
 assert.equal(s.events.length,1);assert.equal(s.events[0].props.download_mode,'browser')
 await x.observeStudioDownload(async()=>42,'private-project','private-render',props)
 assert.equal(s.events.at(-1).event,'studio_download_saved');assert.equal(s.events.at(-1).props.artifact_type,'publish_kit')
 await assert.rejects(x.observeStudioDownload(async()=>{throw {code:'ERR_NETWORK',message:'private path'}},'private-project','private-render',props))
 assert.equal(s.events.at(-1).event,'studio_download_failed');assert.equal(s.events.at(-1).props.error_code,'network')
 let finish;const pending=x.observeStudioDownload(()=>new Promise(r=>finish=r),'p','j',props)
 const count=s.events.length;s.tracker.clear();finish(42);await pending
 assert.equal(s.events.length,count);assert.equal(JSON.stringify(s.events).includes('private'),false)
})

test('portrait import and saved outro preference retain explicit enums and confirmed state',()=>{
 const s=setup();const x=load('studio',{'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
 const body=new FormData();body.set('portrait_style','podcast');body.set('name','private name');body.append('platforms','douyin')
 const props=core.safeStudioProperties(x.studioImportProperties(body))
 assert.equal(props.portrait_style,'podcast');assert.equal(props.brand_outro_enabled,undefined)
 body.set('brand_outro_enabled','false');assert.equal(x.studioImportProperties(body).brand_outro_enabled,false)
 const experience=load('experience',{'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
 const done=experience.beginExperience('output_branding_save',{section:'app',brand_outro_enabled:false})
 done('completed',{brand_outro_enabled:false});done('failed')
 assert.equal(s.events.length,2);assert.equal(s.events[1].props.brand_outro_enabled,false)
 const late=experience.beginExperience('output_branding_save',{brand_outro_enabled:true});const n=s.events.length;s.tracker.clear();late('completed')
 assert.equal(s.events.length,n);assert.equal(JSON.stringify(props).includes('private'),false)
})

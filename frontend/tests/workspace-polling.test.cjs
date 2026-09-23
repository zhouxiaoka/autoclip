const {test}=require('node:test'),assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),ts=require('typescript')
const file=path.resolve(__dirname,'../src/features/studio/pollWorkspace.ts'),m=new Module(file,module)
m._compile(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,file)
const {pollWorkspace}=m.exports
const snapshot=(status,jobs=[])=>({drafts:[],events:[],jobs:jobs.map(status=>({status})),analysis:status?{status}:null})
function setup(){const controller=new AbortController(),data=[],errors=[];return{controller,data,errors,options:{signal:controller.signal,intervalMs:0,onData:x=>data.push(x),onError:e=>errors.push(e),onSettled(){}}}}
test('completion, failure and confirmation stop reads, including an empty old project',async()=>{
 for(const status of ['completed','failed','awaiting_confirmation',null]){
  const c=setup();let calls=0;await pollWorkspace(async()=>{calls++;return snapshot(status)},c.options);assert.equal(calls,1)
 }
})
test('analysis and queued/running exports continue until all active work finishes',async()=>{
 const c=setup(),rows=[snapshot('running'),snapshot('completed',['queued']),snapshot('completed',['running']),snapshot('completed',['completed','failed'])]
 await pollWorkspace(async()=>rows.shift(),c.options);assert.equal(c.data.length,4);assert.equal(rows.length,0)
})
test('HTTP errors stop immediately; network failures are bounded and keep prior data',async()=>{
 for(const status of [401,404,429,500]){const c=setup();let calls=0;await pollWorkspace(async()=>{calls++;throw {response:{status}}},c.options);assert.equal(calls,1)}
 const c=setup();let calls=0;await pollWorkspace(async()=>{if(++calls===1)return snapshot('running');throw Error('network')},c.options)
 assert.equal(calls,4);assert.equal(c.data.length,1);assert.equal(c.errors.length,3)
})
test('recovered network request resumes observation and a new observer refreshes terminal state',async()=>{
 const c=setup();let calls=0;const read=async()=>{if(++calls===1)throw Error('network');return snapshot('completed')}
 await pollWorkspace(read,c.options);await pollWorkspace(read,c.options);assert.equal(calls,3);assert.equal(c.data.length,2)
})
test('abort during an in-flight read prevents updates and any additional requests',async()=>{
 const c=setup();let calls=0,settled=0
 await pollWorkspace(async()=>{calls++;c.controller.abort();return snapshot('running')},{...c.options,onSettled(){settled++}})
 assert.equal(calls,1);assert.equal(c.data.length,0);assert.equal(settled,0)
})
test('abort interrupts the scheduled delay without another read',async()=>{
 const c=setup();let calls=0
 await pollWorkspace(async()=>{calls++;return snapshot('running')},{...c.options,intervalMs:60000,onSettled(){queueMicrotask(()=>c.controller.abort())}})
 assert.equal(calls,1)
})

const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),ts=require('typescript')
const file=path.resolve(__dirname,'../src/features/studio/types.ts'),m=new Module(file,module)
m._compile(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,file)
const {draftError,moveScene,draftDuration}=m.exports
const draft={title:'draft',scenes:[{id:'a',start:0,end:2},{id:'b',start:4,end:7}]}
test('scene reorder preserves source ranges and does not mutate original',()=>{const next=moveScene(draft,1,-1);assert.deepEqual(next.scenes.map(s=>s.id),['b','a']);assert.equal(draft.scenes[0].id,'a');assert.equal(draftDuration(next),5)})
test('invalid boundaries and empty title block save/export',()=>{assert.ok(draftError({...draft,title:'  '}));assert.ok(draftError({...draft,scenes:[{start:4,end:2}]}));assert.ok(draftError({...draft,scenes:[{start:NaN,end:3}]}));assert.equal(draftError(draft),null)})

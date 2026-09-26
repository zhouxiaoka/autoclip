const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs')
const vm=require('node:vm')
const ts=require('typescript')
const moduleObject={exports:{}}
vm.runInNewContext(ts.transpileModule(fs.readFileSync('src/features/studio/types.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{module:moduleObject,exports:moduleObject.exports})
const {draftDuration,applyCandidate}=moduleObject.exports
const base={title:'test',scenes:[{id:'a',start:0,end:9}]}
test('old drafts keep duration; added CTA time is reflected after replacing scenes',()=>{
 assert.equal(draftDuration(base),9)
 for(const template of ['auto','continue'])assert.equal(draftDuration({...base,cta:{template}}),9)
 for(const template of ['brand','challenge'])assert.equal(draftDuration({...base,cta:{template}}),11.5)
 const changed=applyCandidate({...base,cta:{template:'auto'}},{start:0,end:2,label:'short',evidence:''},0,'b')
 assert.equal(draftDuration(changed),4.5)
})

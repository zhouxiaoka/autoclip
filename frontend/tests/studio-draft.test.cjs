const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),ts=require('typescript')
const file=path.resolve(__dirname,'../src/features/studio/types.ts'),m=new Module(file,module)
m._compile(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,file)
const {draftError,moveScene,draftDuration}=m.exports
const draft={title:'draft',scenes:[{id:'a',start:0,end:2},{id:'b',start:4,end:7}]}
test('scene reorder preserves source ranges and does not mutate original',()=>{const next=moveScene(draft,1,-1);assert.deepEqual(next.scenes.map(s=>s.id),['b','a']);assert.equal(draft.scenes[0].id,'a');assert.equal(draftDuration(next),5)})
test('invalid boundaries and empty title block save/export',()=>{assert.ok(draftError({...draft,title:'  '}));assert.ok(draftError({...draft,scenes:[{start:4,end:2}]}));assert.ok(draftError({...draft,scenes:[{start:NaN,end:3}]}));assert.equal(draftError(draft),null)})
const {applyCandidate}=m.exports
const candidate={id:'visual-event',kind:'visual',label:'Obstacle',start:7,end:10,evidence:'Source evidence'}
test('candidate replacement preserves text and other scenes without leaking candidate-only fields',()=>{
 const original={...draft,hook:'My hook',language:'en'}
 const next=applyCandidate(original,candidate,0,'new-scene')
 assert.equal(next.hook,'My hook');assert.equal(next.language,'en')
 assert.deepEqual(next.scenes[0],{id:'new-scene',label:'Obstacle',start:7,end:10,evidence:'Source evidence'})
 assert.equal(next.scenes[1],original.scenes[1]);assert.equal(original.scenes[0].start,0)
})
test('appending the same source twice gives independent scene identities and enforces limits',()=>{
 const next=applyCandidate(applyCandidate(draft,candidate,'append','copy1'),candidate,'append','copy2')
 assert.deepEqual(next.scenes.slice(-2).map(s=>s.id),['copy1','copy2'])
 assert.throws(()=>applyCandidate({...draft,scenes:Array(30).fill(draft.scenes[0])},candidate,'append','extra'),/30/)
 assert.throws(()=>applyCandidate(draft,candidate,99,'bad'),/不存在/)
 assert.ok(draftError(next,8));assert.equal(draftError(next,10),null)
})

test('portrait recommendation updates composition and captions without modifying source or language',()=>{
 const original={...draft,language:'en',aspect:'landscape',layout:'fit',hook:''}
 const next=m.exports.portraitDesign(original)
 assert.equal(next.aspect,'portrait');assert.equal(next.layout,'crop');assert.equal(next.subtitle_style,'bold')
 assert.equal(next.title_style,original.title_style,'no opening title → its style is left alone')
 assert.equal(next.crop_x,.5);assert.equal(next.language,'en');assert.equal(next.scenes,original.scenes)
 assert.equal(original.layout,'fit')
 const titled=m.exports.portraitDesign({...original,hook:'Watch this'})
 assert.equal(titled.title_style,'comic');assert.equal(titled.title_template_version,6)
})
const {cropAt,frameModeAt,shotIndexAt,patchShot}=m.exports
test('shot lookups follow the track from the scene start and fall back to static crop',()=>{
 const scene={id:'s',label:'a',start:10,end:25,evidence:'',crop_x:.4,crop_track:[{start:0,crop_x:.5,mode:'fit'},{start:3,crop_x:.2},{start:9,crop_x:.8,mode:'crop'}]}
 assert.equal(shotIndexAt(scene,11),0);assert.equal(frameModeAt(scene,11),'fit')
 assert.equal(shotIndexAt(scene,13.5),1);assert.equal(frameModeAt(scene,13.5),'crop','missing mode means crop');assert.equal(cropAt(scene,13.5),.2)
 assert.equal(cropAt(scene,24.9),.8)
 const plain={...scene,crop_track:null}
 assert.equal(shotIndexAt(plain,12),-1);assert.equal(frameModeAt(plain,12),'crop');assert.equal(cropAt(plain,12),.4);assert.equal(cropAt(undefined,12,.7),.7)
})
test('patchShot edits only the shot under the playhead and seeds a track for untracked scenes',()=>{
 const scene={id:'s',label:'a',start:10,end:25,evidence:'',crop_track:[{start:0,crop_x:.5,mode:'fit'},{start:3,crop_x:.2,mode:'crop'}]}
 const next=patchShot(scene,11,{mode:'crop',crop_x:.6})
 assert.deepEqual(next.crop_track,[{start:0,crop_x:.6,mode:'crop'},{start:3,crop_x:.2,mode:'crop'}]);assert.equal(scene.crop_track[0].mode,'fit','original untouched')
 const seeded=patchShot({id:'u',label:'b',start:0,end:5,evidence:'',crop_x:.3},2,{mode:'fit'},.5)
 assert.deepEqual(seeded.crop_track,[{start:0,crop_x:.3,mode:'fit'}])
 assert.deepEqual(patchShot({id:'v',label:'c',start:0,end:5,evidence:''},2,{crop_x:.9},.5).crop_track,[{start:0,crop_x:.9,mode:'crop'}])
})

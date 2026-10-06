const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),ts=require('typescript')
const file=path.resolve(__dirname,'../src/features/studio/packagingLabel.ts'),m=new Module(file,module)
m.require=name=>name==='../../i18n'?{t:value=>value}:require(name)
m._compile(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,file)
const pack={template:'interview_zh',audience_language:'zh',source_language:'en',burned_captions:false,fallback:true,cues:[]}
test('missing or original-only captions never advertise bilingual captions',()=>{
 assert.equal(m.exports.packagingLabel(pack),'访谈式')
 assert.equal(m.exports.packagingLabel({...pack,cues:[{text:'Original source',original:''}]}),'访谈式')
 assert.equal(m.exports.packagingLabel({...pack,cues:[{text:'Untranslated source',original:'Original source'}]}),'访谈式')
 assert.equal(m.exports.packagingLabel({...pack,cues:[{text:'译文',original:'Original source'}]}),'访谈式 · 中英字幕')
 assert.equal(m.exports.packagingLabel({...pack,source_language:'other',cues:[{text:'译文',original:'日本語'}]}),'访谈式')
})
test('fallback hint distinguishes usable captions from an empty old package',()=>{
 assert.equal(m.exports.packagingFallbackHint(pack),'包装未能完整生成，字幕暂不可用')
 assert.equal(m.exports.packagingFallbackHint({...pack,cues:[{text:'字幕',original:''}]}),'包装未能完整生成，已保留可用字幕')
 assert.equal(m.exports.packagingFallbackHint({...pack,fallback:false}),'')
})

test('caption-free visual highlights do not claim missing requested subtitles',()=>{
 assert.equal(m.exports.packagingFallbackHint({...pack,source_language:'other'},[],false),'')
 assert.equal(m.exports.packagingFallbackHint(pack,[],true),'包装未能完整生成，字幕暂不可用')
})
test('caption-free request still describes actually recovered or burned fallback captions',()=>{
 assert.equal(m.exports.packagingFallbackHint(pack,['包装未能完整生成，已使用原字幕'],false),'包装未能完整生成，已保留可用字幕')
 assert.equal(m.exports.packagingFallbackHint({...pack,burned_captions:true},[],false),'包装未能完整生成，已保留可用字幕')
 assert.equal(m.exports.packagingFallbackHint({...pack,cues:[{text:'字幕',original:''}]},[],false),'包装未能完整生成，已保留可用字幕')
})

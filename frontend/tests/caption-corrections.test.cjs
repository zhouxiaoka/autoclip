const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')
const root = path.resolve(__dirname, '../src/features/studio')
const hooks = { useState: value => [value, () => {}], useRef: value => ({ current: value }), useCallback: f => f }
const mocks = { react: hooks, '../../i18n': { t: s => s }, '../../ui': { Btn: 'button', Row: 'section', fmtDuration: String } }
const Corrections = loadTs(path.join(root, 'CaptionCorrections.tsx'), mocks).default
const cue = { start: 1, end: 3, text: '错误译文', original: 'Source', source_id: 'a'.repeat(64) }
const draft = { title: 'Draft', scenes: [{start:0,end:10}], packaging: { source_language: 'en', audience_language: 'zh', translation_status: 'complete', cues: [cue, {...cue,start:3,end:5,text:'人工保留',manually_edited:true}] } }
function nodes(node) { return !node || typeof node !== 'object' ? [] : [node, ...[node.props?.children].flat(Infinity).flatMap(nodes)] }
test('completed translation exposes selected correction, retry and bounded source audition', () => {
 let patch, retry, seek
 const tree = nodes(Corrections({draft,patch: p => patch=p,onRetranslate:i=>retry=i,onSeek:(a,b)=>seek=[a,b]}))
 const textarea = tree.find(n=>n.type==='textarea')
 textarea.props.onChange({target:{value:'修正的译文'}})
 assert.equal(patch.packaging.cues[0].text,'修正的译文')
 assert.equal(patch.packaging.cues[0].manually_edited,true)
 assert.equal(patch.packaging.cues[0].source_id,cue.source_id)
 assert.equal(patch.packaging.cues[1],draft.packaging.cues[1])
 tree.find(n=>n.type==='button'&&n.props.children==='重译此句').props.onClick()
 tree.find(n=>n.type==='button'&&n.props.children==='试听原句').props.onClick()
 assert.equal(retry,0);assert.deepEqual(seek,[1,3]);assert.equal(cue.text,'错误译文')
})
test('latest edit is synchronous before React commits, protecting it from delayed responses',()=>{
 const {useDraftState}=loadTs(path.join(root,'useDraftState.ts'),{react:hooks})
 const [,set,current]=useDraftState();set(draft);const request=current.current
 set(d=>({...d,title:'new edit'}))
 assert.notEqual(current.current,request);assert.equal(current.current.title,'new edit')
})
test('empty caption cannot save or export and retranslation sends only the selected request',async()=>{
 const {draftError}=loadTs(path.join(root,'types.ts'))
 assert.equal(draftError({...draft,packaging:{...draft.packaging,cues:[{...cue,text:'  '}]}}),'字幕不能为空')
 const {setup}=require('./helpers/studio-harness.cjs');const seen=[]
 const h=setup({post:async(url,body)=>{seen.push({url,body});return draft.packaging}})
 await h.studioApi.retranslateCaption('project',draft,1)
 assert.deepEqual(JSON.parse(JSON.stringify(seen)),[{url:'/studio/project/retranslate-caption',body:{draft,cue_index:1}}]);assert.equal(h.events.length,0)
})
test('editor wires the sentence action through both settings layers',()=>{
 const fs=require('node:fs');const editor=fs.readFileSync(path.join(root,'StudioEditor.tsx'),'utf8')
 assert.match(editor,/onRetranslateCaption=\{\(index, packaging\) => void retryTranslation\(index, packaging\)\}/)
 assert.match(editor,/currentDraft.current !== draft/)
 for(const name of ['DraftSettingsPanel.tsx','PackagingSettings.tsx']) assert.match(fs.readFileSync(path.join(root,name),'utf8'),/onRetranslateCaption/)
})
test('missing foreign captions can be corrected and retried without putting placeholders into a saved draft',()=>{
 const {editableCues,correctCaption,captionRetranslation}=loadTs(path.join(root,'captionEdits.ts'))
 const missing={...cue,source_id:'b'.repeat(64),text:'未翻译的源句',source_text:'未翻译的源句'}
 const pack={...draft.packaging,cues:[],untranslated_cues:[missing],translation_total_rows:1,translated_rows:0,translation_status:'source_fallback'}
 assert.equal(editableCues(pack)[0],missing)
 const edited=correctCaption(pack,missing,'The corrected translation.')
 assert.equal(edited.cues[0].text,'The corrected translation.');assert.equal(edited.cues[0].manually_edited,true)
 assert.equal(edited.translation_status,'complete');assert.equal(edited.untranslated_cues.length,0)
 const request=captionRetranslation(pack,missing)
 assert.equal(request.index,0);assert.equal(request.packaging.cues[0],missing)
 assert.equal(pack.cues.length,0);assert.equal(pack.translated_rows,0)
})

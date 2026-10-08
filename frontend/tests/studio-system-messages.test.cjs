const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('typescript')
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server'),{createInstance}=require('i18next')
const langs=['zh','en','ja','ko','es','pt','ru','fr']
const catalogs=Object.fromEntries(langs.map(l=>[l,require('../src/i18n/locales/'+l+'.json')]))
const root=path.resolve(__dirname,'../src/features/studio')
function history(i18n){
 const exports={}
 const mocks={
  'react/jsx-runtime':require('react/jsx-runtime'),
  'react-i18next':{useTranslation:()=>({t:s=>i18n.t(s)})},
  '../../i18n':{t:s=>i18n.t(s),getLocale:()=>i18n.language},
  '../../ui':{Dialog:p=>React.createElement('section',null,p.children),ProgressLine:()=>null},
  'react-router-dom':{Link:p=>React.createElement('a',null,p.children)},
  './StudioDownloadLink':{default:()=>null},
 }
 vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root,'ExportHistory.tsx'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText,{exports,require:id=>{assert.ok(mocks[id],id);return mocks[id]}})
 return exports.default
}
test('export history renders localized server warnings/restart errors in all eight languages, retaining source titles and unknown errors',async()=>{
 const i=createInstance();await i.init({resources:Object.fromEntries(langs.map(l=>[l,{translation:catalogs[l]}])),lng:'en',fallbackLng:'en',keySeparator:false,nsSeparator:false,interpolation:{escapeValue:false}})
 const History=history(i),title='原素材没有音轨，本次导出无声',unknown='decoder failed at frame 42'
 const base={title,revision:2,created_at:'2026-09-25T00:00:00Z'}
 const jobs=[{...base,job_id:'ok',status:'completed',result:{warnings:[title]}},{...base,job_id:'restart',status:'failed',error:'服务已重启，请重新导出'},{...base,job_id:'unknown',status:'failed',error:unknown}]
 for(const lang of langs){
  await i.changeLanguage(lang)
  const html=renderToStaticMarkup(React.createElement(History,{open:true,onClose(){},projectId:'p',jobs}))
  assert.ok(html.includes('<b>'+title+'</b>'),lang+' source title preserved')
  assert.ok(html.includes(catalogs[lang][title]),lang+' warning')
  assert.ok(html.includes(catalogs[lang]['服务已重启，请重新导出']),lang+' restart')
  assert.ok(html.includes(unknown),lang+' diagnostics preserved')
 }
})
test('all backend processing stages have translations in eight catalogs',()=>{
 const stages=["导入任务未能启动，请重试；原素材与已有成片已保留","制作任务未能启动，请重试确认；原素材与已有成片已保留",'导出任务未能启动，请重试；已有成片已保留','下载素材','理解画面','准备素材','快速判断适合的制作类型','开始制作所选内容','制作内容切片','制作精彩高光','制作推广成片','扫描画面，寻找候选高光','复核首选高光的起止边界','组织推广开头与成片草稿','整理高光成片草稿']
 for(const lang of langs)for(const stage of stages){assert.ok(catalogs[lang][stage],lang+stage);if(lang!=='zh')assert.notEqual(catalogs[lang][stage],stage)}
})
test('source_blocked download hint matches the backend constant and is translated in eight catalogs',()=>{
 const src=fs.readFileSync(path.resolve(__dirname,'../../backend/utils/download_recovery.py'),'utf8')
 const hint=src.match(/^SOURCE_BLOCKED_HINT = '([^']+)'$/m)[1]
 for(const lang of langs){assert.ok(catalogs[lang][hint],lang);if(lang!=='zh')assert.notEqual(catalogs[lang][hint],hint,lang)}
 for(const file of ['../src/analytics/feedbackDraft.ts','../src/analytics/workflow.ts'])assert.ok(fs.readFileSync(path.resolve(__dirname,file),'utf8').includes('|source_blocked|'),file)
})
test('source_too_short / source_no_audio messages match the backend constants and are translated in eight catalogs',()=>{
 const src=fs.readFileSync(path.resolve(__dirname,'../../backend/pipeline/media_precheck.py'),'utf8')
 const literal=name=>{const body=src.match(new RegExp('^'+name+' = \\(?\\n?([\\s\\S]*?)\\)?\\n(?=\\S)','m'))[1];return [...body.matchAll(/"([^"]+)"/g)].map(m=>m[1]).join('')}
 const messages=['TOO_SHORT_MESSAGE','NO_AUDIO_MESSAGE','NO_AUDIO_AFTER_SCREENING_MESSAGE'].map(literal)
 assert.equal(messages.length,3)
 for(const message of messages){assert.ok(message.length>20,message);for(const lang of langs){assert.ok(catalogs[lang][message],lang+message);if(lang!=='zh')assert.notEqual(catalogs[lang][message],message,lang)}}
 for(const file of ['../src/analytics/feedbackDraft.ts','../src/analytics/workflow.ts'])assert.ok(fs.readFileSync(path.resolve(__dirname,file),'utf8').includes('|source_too_short|source_no_audio|'),file)
})
test('restart recovery messages match the backend constants and are translated in eight catalogs (RC156 #13)',()=>{
 const src=fs.readFileSync(path.resolve(__dirname,'../../backend/services/studio/store.py'),'utf8')
 const restart=src.match(/^RESTART_MESSAGE = '([^']+)'$/m)[1]
 const keys=[restart,'服务已重启，请重试这条','服务已重启，请重新生成封面','服务已重启，请重新导出','服务已重启，请重试分析','重新生成']
 for(const key of keys)assert.ok(src.includes(key)||key==='重新生成',key)
 for(const lang of langs)for(const key of keys){assert.ok(catalogs[lang][key],lang+key);if(lang!=='zh')assert.notEqual(catalogs[lang][key],key,lang+key)}
 for(const file of ['../src/analytics/feedbackDraft.ts','../src/analytics/workflow.ts','../../scripts/ingest_app_feedback.py'])assert.ok(fs.readFileSync(path.resolve(__dirname,file),'utf8').includes('|service_restarted)'),file)
})
test('Studio progress messages, including transcription progress, are translated in eight catalogs (RC156 #14)',()=>{
 const src=fs.readFileSync(path.resolve(__dirname,'../../backend/services/simple_pipeline_adapter.py'),'utf8')
 const transcribing=src.match(/^STUDIO_TRANSCRIBING_MESSAGE = '([^']+)'$/m)[1]
 const production=src.match(/^STUDIO_PRODUCTION_MESSAGE = '([^']+)'$/m)[1]
 const jobs=fs.readFileSync(path.resolve(__dirname,'../../backend/services/studio/jobs.py'),'utf8')
 const keys=[transcribing,production,'正在生成可发布成片','正在追加平台版本','正在重试成片版本']
 for(const key of keys.slice(1))assert.ok(jobs.includes(`'${key}'`),key)
 for(const lang of langs)for(const key of keys){assert.ok(catalogs[lang][key],lang+key);if(lang!=='zh')assert.notEqual(catalogs[lang][key],key,lang+key)}
})

const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path')
const read=file=>fs.readFileSync(path.join(__dirname,'..',file),'utf8')

test('E3 settings let the user pick the Whisper model download source',()=>{
 const api=read('src/services/api.ts'), ui=read('src/components/SpeechRecognitionConfig.tsx')
 assert.match(api,/export type WhisperModelSource = 'auto' \| 'huggingface' \| 'hf-mirror'/)
 assert.match(api,/api\.put\('\/whisper\/model-source', \{ source \}\)/)
 assert.match(ui,/aria-label=\{t\('模型下载源'\)\}/)
 assert.match(ui,/value: 'auto'.*value: 'huggingface'.*value: 'hf-mirror'/s)
 assert.match(ui,/speechApi\.setModelSource\(source\)/)
})

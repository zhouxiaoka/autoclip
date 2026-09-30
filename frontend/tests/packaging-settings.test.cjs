const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path')
const read=file=>fs.readFileSync(path.join(__dirname,'..',file),'utf8')
const settings=read('src/features/studio/PackagingSettings.tsx')
const panel=read('src/features/studio/DraftSettingsPanel.tsx')
const editor=read('src/features/studio/StudioEditor.tsx')
const types=read('src/features/studio/types.ts')

test('draft edits keep template packaging intact on save',()=>{
 assert.match(types,/packaging\?: Packaging \| null/)
 assert.match(editor,/const patch = \(changes: Partial<Draft>\) => \{ if \(draft\) \{ setDraft\(\{\.\.\.draft, \.\.\.changes\}\)/)
 assert.match(settings,/patch\(\{ packaging: \{ \.\.\.packaging, \.\.\.changes \} \}\)/)
})

test('this release only edits the two title lines and the editor tags switch',()=>{
 assert.match(settings,/title_lines: next\.filter/)
 assert.match(settings,/update\(\{ tags_enabled: checked \}\)/)
 assert.doesNotMatch(settings,/cues:|speakers:|highlights:/)
 assert.match(panel,/draft\.packaging \? <PackagingSettings draft=\{draft\} patch=\{patch\} \/>/)
 assert.match(panel,/\{!draft\.packaging && <Row label=\{t\("字幕"\)\}/)
})

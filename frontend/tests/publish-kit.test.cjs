const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path')
const read=file=>fs.readFileSync(path.join(__dirname,'..',file),'utf8')
const kit=read('src/features/studio/PublishKit.tsx')
const card=read('src/features/studio/OutputVariantCard.tsx')
const api=read('src/features/studio/api.ts')
const publish=read('src/pages/PublishClipPage.tsx')

test('every output card shows its publish kit and uses the designed cover as the poster',()=>{
 assert.match(card,/<PublishKit projectId=\{projectId\} variant=\{variant\}/)
 assert.match(card,/poster=\{\(variant\.cover \|\| coverStamp\) \? studioApi\.variantCover\(projectId, variant\.id, coverStamp\) : undefined\}/)
 assert.match(api,/output-variants\/\$\{variantId\}\/kit/)
 assert.match(api,/api\.put\(`\/studio\/\$\{pid\}\/output-variants\/\$\{variantId\}\/post`, post\)/)
})

test('post copy is pasted as title, description, then hashtags; the kit saves natively on desktop',()=>{
 assert.match(kit,/\[post\.title, post\.description, post\.tags\.map\(tag => `#\$\{tag\}`\)\.join\(' '\)\]\.filter\(Boolean\)\.join\('\\n\\n'\)/)
 assert.match(kit,/observeStudioDownload\(\(\) => saveLocalFile\(kitPath\)/)
 assert.match(kit,/studioDownloadRequested\(projectId, jobId, props\)/)
 assert.match(kit,/studioApi\.redesignVariantCover\(projectId, variant\.id\)/)
 assert.match(kit,/studioApi\.variantCoverJob\(projectId, variant\.id\)/)
})

test('the publish page starts from the output kit: copy, hashtags and the matching cover slot',()=>{
 assert.match(publish,/setTitle\(post\.title\)/)
 assert.match(publish,/setDescription\(\[post\.description, post\.tags\.map/)
 assert.match(publish,/coverApi\.get\(projectId, clipId, coverSlot\)/)
})

test('the thumbnail and caption open one cover dialog from the publish kit',()=>{
 const preview=read('src/features/studio/ExportCover.tsx')
 assert.match(kit,/className=\{`studio-post-cover/)
 assert.match(kit,/<img src=\{coverUrl\}/)
 assert.match(kit,/<ExportCoverButton[^>]+>\{thumbnail\}<\/ExportCoverButton>/)
 assert.match(preview,/aria-haspopup="dialog"[^>]*onClick=\{\(\) => setOpen\(true\)\}/)
 assert.doesNotMatch(card,/<ExportCoverButton/)
})

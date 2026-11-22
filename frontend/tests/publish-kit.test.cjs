const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path')
const read=file=>fs.readFileSync(path.join(__dirname,'..',file),'utf8')
const kit=read('src/features/studio/PublishKit.tsx')
const card=read('src/features/studio/OutputVariantCard.tsx')
const api=read('src/features/studio/api.ts')
const publish=read('src/pages/PublishClipPage.tsx')

const preview=read('src/features/studio/StudioPublishPreview.tsx')
const cover=read('src/features/studio/ExportCover.tsx')
const editor=read('src/features/studio/StudioEditor.tsx')

test('ready cards open the publish preview for the selected export',()=>{
 for(const source of [card,read('src/features/studio/DraftResultCard.tsx')]){
   assert.doesNotMatch(source,/<PublishKit|studio-publish-tools/)
   assert.match(source,/studioPublishPreviewPath\(projectId, (?:draft.id|job.draft_id),/)
 }
 assert.match(preview,/<PublishKit projectId=\{projectId\} job=\{job\} variant=\{variant\}/)
 assert.match(editor,/j.job_id === publishJobId && j.status === 'completed'/)
 assert.match(editor,/selectedVariant\?.render_job_id !== job.job_id/)
 assert.match(api,/output-variants\/\$\{variantId\}\/kit/)
 assert.match(api,/api\.put\(`\/studio\/\$\{pid\}\/output-variants\/\$\{variantId\}\/post`, post\)/)
})

test('post copy is pasted as title, description, then hashtags; the kit saves natively on desktop',()=>{
 assert.match(kit,/\[post\.title, post\.description, post\.tags\.map\(tag => `#\$\{tag\}`\)\.join\(' '\)\]\.filter\(Boolean\)\.join\('\\n\\n'\)/)
 assert.match(kit,/observeStudioDownload\(\(\) => saveLocalFile\(kitPath\)/)
 assert.match(kit,/studioDownloadRequested\(projectId, jobId, props\)/)
 assert.match(cover,/studioApi\.redesignVariantCover\(projectId, variant\.id,/)
 assert.match(cover,/studioApi\.variantCoverJob\(projectId, task\.variantId\)/)
})

test('the publish page starts from the output kit: copy, hashtags and the matching cover slot',()=>{
 assert.match(preview,/variant\?.post \?\? job.post/)
 assert.match(publish,/preparedPost.description, preparedPost.tags.map/)
 assert.match(cover,/exportCoverSlot\(job\)/)
})

test('the thumbnail and caption open one cover dialog from the publish kit',()=>{
 assert.match(kit,/<ExportCoverButton projectId=\{projectId\} job=\{job\}/)
 assert.match(cover,/<img src=\{src\}/)
 assert.match(cover,/aria-haspopup="dialog"/)
 assert.match(preview,/studioApi.video\(projectId, job.job_id\)/)
})

test('studio submissions reuse the platform controls on the preview and use its saved post',()=>{
 assert.match(preview,/<PublishClip projectId=\{projectId\} clipId=\{`studio-\$\{job.job_id\}`\}[^>]+preparedPost=\{post\}/)
 assert.doesNotMatch(preview,/navigate\(publishPath|发布这版成片/)
 assert.match(publish,/const title = preparedPost\?.title/)
 assert.match(publish,/if \(embedded\) return <section className="studio-publish-destinations">/)
 assert.match(publish,/studioPublishPreviewPath\(projectId, job.draft_id, jobId/)
})

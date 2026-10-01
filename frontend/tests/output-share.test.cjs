const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path')
const read=file=>fs.readFileSync(path.join(__dirname,'..',file),'utf8')
const share=read('src/features/studio/outputShare.ts')
const feedback=read('src/features/studio/OutputFeedback.tsx')
const card=read('src/features/studio/OutputVariantCard.tsx')
const download=read('src/features/studio/StudioDownloadLink.tsx')
const studio=read('src/analytics/studio.ts')
const workflow=read('src/analytics/workflow.ts')

test('share caption credits AutoClip with the repository link and is copied locally',()=>{
 assert.match(share,/REPO_URL = 'https:\/\/github\.com\/zhouxiaoka\/autoclip'/)
 assert.match(share,/t\('用 AutoClip 剪的'\)\} · \$\{REPO_URL\}/)
 assert.match(share,/navigator\.clipboard\.writeText/)
 assert.match(card,/copyText\(variant\.post \? `\$\{postCaption\(variant\.post\)\}\\n\\n\$\{shareCaption\(''\)\}`\.trim\(\) : shareCaption\(draft\?\.title\)\)/)
 assert.match(card,/trackOutputShare\(projectId, \{ share_target: 'copy_caption', \.\.\.analytics \}\)/)
})

test('rating is asked after a successful download at most once per project and once a week',()=>{
 assert.match(share,/RATING_INTERVAL_MS = 7 \* 86400000/)
 assert.match(share,/state\.projects\?\.includes\(projectKey\)\) return false/)
 assert.match(download,/message\.success\(t\('已保存到下载文件夹'\)\)\n\s+onSaved\?\.\(\)/)
 assert.match(card,/onSaved=\{downloaded\}/)
 assert.match(card,/if \(!shouldAskRating\(projectId\)\) return\n\s+markRatingAsked\(projectId\)/)
})

test('use-case invite goes to GitHub Discussions and nothing is uploaded',()=>{
 assert.match(share,/USE_CASE_URL = `\$\{REPO_URL\}\/discussions\/new\?category=use-cases`/)
 assert.match(feedback,/openExternalLink\(USE_CASE_URL\)/)
 assert.doesNotMatch(feedback,/textarea|<input/)
})

test('share and rating analytics only carry allowlisted enums',()=>{
 assert.match(workflow,/share_target: \['copy_caption', 'use_case_discussion'\]/)
 assert.match(workflow,/output_rating: \['ready', 'needs_edit', 'unusable'\]/)
 assert.match(studio,/captureBusinessEvent\('studio_output_shared', safeStudioProperties\(\{ \.\.\.workflow\.context\(projectId\), \.\.\.properties \}\)\)/)
 assert.match(studio,/captureBusinessEvent\('studio_output_rated', safeStudioProperties\(\{ \.\.\.workflow\.context\(projectId\), \.\.\.properties \}\)\)/)
 assert.match(workflow,/template: \['interview_zh', 'podcast_en', 'landscape', 'none'\]/)
 assert.match(workflow,/packaging_style: \['classic', 'boxed', 'spotlight', 'pop', 'cinematic'\]/)
})

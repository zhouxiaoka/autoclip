const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path')
const api=fs.readFileSync(path.join(__dirname,'../src/features/studio/api.ts'),'utf8')
const results=fs.readFileSync(path.join(__dirname,'../src/features/studio/StudioResults.tsx'),'utf8')
const card=fs.readFileSync(path.join(__dirname,'../src/features/studio/OutputVariantCard.tsx'),'utf8')

test('completed variants render the immutable output video directly',()=>{
 assert.match(card,/studioApi\.video\(projectId, variant\.render_job_id\)/)
 assert.match(card,/<video className="studio-variant-video"/)
})

test('result page appends platforms and retries only an output variant',()=>{
 assert.match(api,/appendPlatforms: \(pid: string, platforms: string\[\], outroEnabled: boolean\)/)
 assert.match(api,/`\/studio\/\$\{pid\}\/platforms`/)
 assert.match(api,/`\/studio\/\$\{pid\}\/output-variants\/\$\{variantId\}\/retry`/)
 assert.match(results,/studioApi\.appendPlatforms\(project\.id, platforms, workspace\.generation\?\.branding\.outro_enabled/)
 assert.match(results,/studioApi\.retryOutputVariant\(project\.id, variant\.id\)/)
 assert.doesNotMatch(results,/studioApi\.import\(/)
 assert.match(card,/重试这条/)
})

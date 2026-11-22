const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const read = rel => fs.readFileSync(path.join(__dirname, '..', rel), 'utf8')

test('projectApi.getProjects fetches larger pages and follows has_next pagination', () => {
  const apiSrc = read('src/services/api.ts')
  assert.match(apiSrc, /api\.get\('\/projects\/',\s*\{\s*params:\s*\{\s*page:\s*1,\s*size:\s*100\s*\}\s*\}\)/)
  assert.match(apiSrc, /pagination\?\.has_next/)
})

test('StudioEditor distinguishes already-rendered download dialog from fresh export and offers re-render', () => {
  const editorSrc = read('src/features/studio/StudioEditor.tsx')
  assert.match(editorSrc, /previewUrl\s*\?\s*t\("查看已导出"\)\s*:\s*t\("导出成片"\)/)
  assert.match(editorSrc, /title=\{previewUrl\s*\?\s*t\("已导出成片"\)\s*:\s*t\("导出成片"\)\}/)
  assert.match(editorSrc, /当前版本已渲染完成，可直接下载已有成片，或重新渲染新版本。/)
  assert.match(editorSrc, /onClick=\{render\}>\{t\("重新渲染"\)\}/)
})

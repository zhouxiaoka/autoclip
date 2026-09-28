const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')
const helper = path.join(__dirname, '../src/utils/videoUrl.ts')
const source = fs.readFileSync(helper, 'utf8')
const moduleValue = { exports: {} }
vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, { module: moduleValue, exports: moduleValue.exports, URL })
const { getVideoType } = moduleValue.exports
for (const url of [
  'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
  'https://youtu.be/dQw4w9WgXcQ?si=abc',
  'https://youtube.com/shorts/dQw4w9WgXcQ',
  'https://m.youtube.com/watch?v=dQw4w9WgXcQ',
  'https://music.youtube.com/watch?v=dQw4w9WgXcQ',
  'https://youtube.com/watch?si=abc&v=dQw4w9WgXcQ',
  'https://youtube.com/live/dQw4w9WgXcQ',
  'https://youtube.com/embed/dQw4w9WgXcQ',
  'https://youtube.com/v/dQw4w9WgXcQ',
  '  https://youtu.be/dQw4w9WgXcQ  ',
]) test(url, () => assert.equal(getVideoType(url), 'youtube'))
for (const url of ['https://www.bilibili.com/video/BV1xx411c7mu', 'https://bilibili.com/video/av123', 'https://b23.tv/Ab123'])
  test(url, () => assert.equal(getVideoType(url), 'bilibili'))
for (const url of ['https://youtube.com.evil.test/watch?v=x', 'https://evil.test/youtube.com/watch?v=x', 'javascript:alert(1)', 'https://youtube.com/watch?si=abc', 'https://youtube.com/playlist?list=x', 'https://youtu.be/', 'https://youtube.com/shorts/', 'not a URL'])
  test(url, () => assert.equal(getVideoType(url), null))

const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

function load(rel) {
  const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, rel), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText
  const module = { exports: {} }
  vm.runInNewContext(code, { module, exports: module.exports })
  return module.exports
}

const { readDownloadProgress, isSourceDownloading, displayedDownloadPercent } = load('../src/utils/downloadProgress.ts')

test('API settings.download_progress is the source download percent', () => {
  const project = {
    status: 'pending',
    settings: { download_status: 'downloading', download_progress: 30 },
  }
  assert.equal(readDownloadProgress(project), 30)
  assert.equal(isSourceDownloading(project), true)
})

test('progress 0 while download_status is downloading is still a download, not the 5% placeholder', () => {
  const project = {
    status: 'pending',
    settings: { download_status: 'downloading', download_progress: 0 },
  }
  assert.equal(readDownloadProgress(project), 0)
  assert.equal(isSourceDownloading(project), true)
})

test('a pending upload without download fields is not a source download', () => {
  const project = { status: 'pending', settings: { video_category: 'knowledge' } }
  assert.equal(readDownloadProgress(project), 0)
  assert.equal(isSourceDownloading(project), false)
})

test('finished download and failed projects are not shown as in-progress downloads', () => {
  assert.equal(isSourceDownloading({
    status: 'pending',
    settings: { download_status: 'completed', download_progress: 100 },
  }), false)
  assert.equal(isSourceDownloading({
    status: 'failed',
    settings: { download_status: 'downloading', download_progress: 30 },
  }), false)
})

test('a later list percent replaces the 5% importing placeholder when the download poll has not returned', () => {
  // 卡片先以 pending、没有下载字段挂上，进度是写死的 5。
  // 桌面端轮询如果打到壳页面会失败，polled 一直是 null，不能把 5 留住。
  assert.equal(displayedDownloadPercent(5, null), 5)
  assert.equal(displayedDownloadPercent(0, null), 0)
  assert.equal(displayedDownloadPercent(30, null), 30)
})

test('a successful download poll replaces the placeholder percent', () => {
  assert.equal(displayedDownloadPercent(5, 30), 30)
  assert.equal(displayedDownloadPercent(0, 0), 0)
})

test('legacy processing_config still wins when it actually carries the progress', () => {
  const project = {
    status: 'pending',
    processing_config: { download_progress: 12 },
    settings: { download_progress: 80 },
  }
  assert.equal(readDownloadProgress(project), 12)
  assert.equal(isSourceDownloading(project), true)
})

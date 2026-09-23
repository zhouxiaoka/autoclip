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

const { readDownloadProgress, isSourceDownloading } = load('../src/utils/downloadProgress.ts')

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

test('legacy processing_config still wins when it actually carries the progress', () => {
  const project = {
    status: 'pending',
    processing_config: { download_progress: 12 },
    settings: { download_progress: 80 },
  }
  assert.equal(readDownloadProgress(project), 12)
  assert.equal(isSourceDownloading(project), true)
})

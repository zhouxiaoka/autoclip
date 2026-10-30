const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('path')
const { runInSandbox } = require('./vm-sandbox.cjs')
const ts = require('typescript')

function load(relative) {
  const file = path.join(__dirname, relative)
  const exports = {}
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText
  runInSandbox(code, { exports, URL, require: () => ({}) })
  return exports
}

function plain(value) {
  return JSON.parse(JSON.stringify(value))
}

function storage() {
  const data = new Map()
  return {
    getItem: key => data.get(key) ?? null,
    setItem: (key, value) => { data.set(key, value) },
    removeItem: key => { data.delete(key) },
  }
}

const memory = load('../src/features/studio/platformMemory.ts')

test('T1: no success history defaults to a single locale platform', () => {
  const box = storage()
  memory.bindPlatformStorage(box)
  assert.equal(memory.hasSuccessHistory(), false)
  assert.deepEqual(plain(memory.platformsForLocale('zh-CN', false)), ['douyin'])
  assert.deepEqual(plain(memory.platformsForLocale('en-US', false)), ['tiktok'])
  assert.deepEqual(plain(memory.resolvePlatforms(true, 'zh-CN', null, false).platforms), ['douyin'])
  assert.deepEqual(plain(memory.resolvePlatforms(true, 'en', null, false).platforms), ['tiktok'])
  assert.equal(memory.resolvePlatforms(true, 'zh-CN', null, false).source, 'locale')
})

test('T1: after first success locale defaults widen for zh', () => {
  const box = storage()
  memory.bindPlatformStorage(box)
  assert.equal(memory.markFirstSuccess('2026-10-30T00:00:00.000Z'), true)
  assert.equal(memory.hasSuccessHistory(), true)
  assert.equal(memory.markFirstSuccess('2026-10-31T00:00:00.000Z'), false)
  assert.deepEqual(plain(memory.platformsForLocale('zh-CN', true)), ['xiaohongshu', 'douyin'])
  assert.deepEqual(plain(memory.platformsForLocale('en', true)), ['tiktok'])
  assert.deepEqual(plain(memory.resolvePlatforms(true, 'zh-CN', null).platforms), ['xiaohongshu', 'douyin'])
})

test('T1: remembered and manual defaults stay unrestricted', () => {
  const box = storage()
  memory.bindPlatformStorage(box)
  memory.writeRememberedPlatforms(['bilibili', 'xiaohongshu', 'douyin'])
  // Explicit remembered list (manual multi-select) is never clipped by T1.
  assert.deepEqual(plain(memory.resolvePlatforms(true, 'zh-CN', ['bilibili', 'xiaohongshu', 'douyin'], false).platforms), ['bilibili', 'xiaohongshu', 'douyin'])
  assert.equal(memory.resolvePlatforms(true, 'zh-CN').source, 'remembered')
  assert.deepEqual(plain(memory.resolvePlatforms(false, 'zh-CN', null, false)), { platforms: ['douyin'], source: 'user' })
})

test('T1: reuse stash carries platforms and source meta once', () => {
  const box = storage()
  memory.bindPlatformStorage(box)
  memory.stashReuseImport({
    platforms: ['xiaohongshu', 'not-real'],
    sourceUrl: 'https://example.com/v',
    sourceMeta: { project_id: 'p1', source_url: 'https://example.com/v' },
  })
  const once = memory.takeReuseImport()
  assert.deepEqual(plain(once.platforms), ['xiaohongshu'])
  assert.equal(once.sourceUrl, 'https://example.com/v')
  assert.equal(once.sourceMeta.project_id, 'p1')
  assert.equal(memory.takeReuseImport(), null)
})

test('T1: suggest another platform prefers 小红书 / Shorts', () => {
  assert.equal(memory.suggestAnotherPlatform('zh-CN', ['douyin']), 'xiaohongshu')
  assert.equal(memory.suggestAnotherPlatform('en', ['tiktok']), 'youtube_shorts')
})

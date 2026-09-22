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

const { pickPreset, defaultPlatforms, privateExtra, readApiDetail } = load('../src/publish/uploadPost.ts')

test('vertical platforms pick the shorts preset and others stay original', () => {
  assert.equal(pickPreset([]), 'original')
  assert.equal(pickPreset(['linkedin', 'x']), 'original')
  assert.equal(pickPreset(['linkedin', 'tiktok']), 'shorts')
  assert.equal(pickPreset(['youtube']), 'shorts')
})

test('connected vertical platforms are preselected, otherwise every connected platform', () => {
  assert.deepEqual(defaultPlatforms(['linkedin', 'x']), ['linkedin', 'x'])
  assert.deepEqual(defaultPlatforms(['linkedin', 'tiktok', 'x']), ['tiktok'])
  assert.deepEqual(defaultPlatforms(['tiktok', 'instagram', 'linkedin']), ['tiktok', 'instagram'])
  assert.deepEqual(defaultPlatforms([]), [])
})

test('private visibility only adds the documented fields for the selected platforms', () => {
  const plain = (value) => JSON.parse(JSON.stringify(value))
  assert.deepEqual(plain(privateExtra(['tiktok', 'youtube', 'linkedin'], 'private')), {
    privacy_level: 'SELF_ONLY',
    privacyStatus: 'private',
  })
  assert.deepEqual(plain(privateExtra(['tiktok', 'youtube'], 'public')), {})
  assert.deepEqual(plain(privateExtra(['linkedin'], 'private')), {})
})

test('api errors prefer the server detail over a generic message', () => {
  assert.equal(readApiDetail({ response: { data: { detail: '没有配置' } } }, '失败'), '没有配置')
  assert.equal(readApiDetail({ response: { data: { detail: [{ msg: 'a' }, { msg: 'b' }] } } }, '失败'), 'a；b')
  assert.equal(readApiDetail({ message: 'network' }, '失败'), 'network')
  assert.equal(readApiDetail(null, '失败'), '失败')
})

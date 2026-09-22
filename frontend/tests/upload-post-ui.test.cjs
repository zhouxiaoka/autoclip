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
  vm.runInNewContext(code, { module, exports: module.exports, Date })
  return module.exports
}

const { pickPreset, defaultPlatforms, privateExtra, readApiDetail, buildSchedule, recordStatusKey, recordTone } = load('../src/publish/uploadPost.ts')

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

test('schedule is omitted for send-now and rejected when the time is missing or past', () => {
  const now = Date.parse('2026-09-22T12:00:00')
  const plain = (value) => JSON.parse(JSON.stringify(value))
  assert.deepEqual(plain(buildSchedule('now', '', 'Asia/Shanghai', now)), { ok: true })
  assert.deepEqual(plain(buildSchedule('later', '', 'Asia/Shanghai', now)), { ok: false, reason: 'empty' })
  assert.deepEqual(plain(buildSchedule('later', '2026-09-22T11:00', 'Asia/Shanghai', now)), { ok: false, reason: 'past' })
  assert.deepEqual(plain(buildSchedule('later', '2026-10-01T09:00', 'Asia/Shanghai', now)), {
    ok: true,
    scheduled_date: '2026-10-01T09:00:00',
    timezone: 'Asia/Shanghai',
  })
})

test('record status stays a short label', () => {
  assert.equal(recordStatusKey('scheduled'), '已排期')
  assert.equal(recordStatusKey('completed'), '已发出')
  assert.equal(recordStatusKey('cancelled'), '已取消')
  assert.equal(recordStatusKey('failed'), '发布失败')
  assert.equal(recordStatusKey('submitted'), '处理中')
  assert.equal(recordTone('completed'), 'ok')
  assert.equal(recordTone('failed'), 'error')
  assert.equal(recordTone('cancelled'), 'muted')
  assert.equal(recordTone('scheduled'), 'accent')
})

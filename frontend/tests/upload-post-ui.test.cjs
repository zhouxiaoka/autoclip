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

const {
  pickPreset, renderPreset, defaultPlatforms, publishDestinations, platformLabel, privateExtra, readApiDetail, buildSchedule, recordStatusKey, recordTone,
  monthCells, upcomingWeekSlots, planWeek, dayKey, localStamp, focusMonth,
} = load('../src/publish/uploadPost.ts')

test('vertical platforms pick the shorts preset and others stay original', () => {
  assert.equal(pickPreset([]), 'original')
  assert.equal(pickPreset(['linkedin', 'x']), 'original')
  assert.equal(pickPreset(['linkedin', 'tiktok']), 'shorts')
  assert.equal(pickPreset(['youtube']), 'shorts')
})

test('the publish page renders vertical accounts as 9:16 and horizontal-only accounts as original', () => {
  assert.equal(renderPreset([]), 'douyin')
  assert.equal(renderPreset(['tiktok', 'youtube', 'linkedin']), 'douyin')
  assert.equal(renderPreset(['linkedin', 'x']), 'original')
  assert.equal(renderPreset(['bilibili']), 'bilibili')
  assert.equal(renderPreset(['tiktok', 'bilibili']), 'douyin')
  assert.equal(renderPreset(['bilibili', 'linkedin']), 'bilibili')
})

test('Bilibili sits with the connected accounts and keeps its own label', () => {
  assert.deepEqual(publishDestinations(['tiktok', 'youtube'], true), ['tiktok', 'youtube', 'bilibili'])
  assert.deepEqual(publishDestinations(['tiktok'], false), ['tiktok'])
  assert.deepEqual(defaultPlatforms(publishDestinations(['tiktok', 'youtube'], true)), ['tiktok', 'youtube'])
  assert.deepEqual(defaultPlatforms(publishDestinations([], true)), ['bilibili'])
  assert.equal(platformLabel('bilibili'), 'B站')
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

test('september 2026 opens on the monday before the first', () => {
  const cells = monthCells(2026, 8)
  assert.equal(cells.length, 42)
  assert.equal(dayKey(cells[0].date), '2026-08-31')
  assert.equal(cells[0].inMonth, false)
  assert.equal(dayKey(cells[1].date), '2026-09-01')
  assert.equal(cells[1].inMonth, true)
})

test('week slots keep the rest of this week, then next monday wednesday friday', () => {
  const plain = (value) => JSON.parse(JSON.stringify(value))
  const tuesdayMorning = upcomingWeekSlots(new Date(2026, 8, 22, 8)).map(localStamp)
  assert.deepEqual(plain(tuesdayMorning), ['2026-09-23T09:00:00', '2026-09-25T09:00:00'])
  const wednesdayAtNine = upcomingWeekSlots(new Date(2026, 8, 23, 9)).map(localStamp)
  assert.deepEqual(plain(wednesdayAtNine), ['2026-09-25T09:00:00'])
  const fridayEvening = upcomingWeekSlots(new Date(2026, 8, 25, 10)).map(localStamp)
  assert.deepEqual(plain(fridayEvening), ['2026-09-28T09:00:00', '2026-09-30T09:00:00', '2026-10-02T09:00:00'])
})

test('week plan ranks by score, skips clips already sent, and leaves an occupied minute', () => {
  const now = new Date(2026, 8, 21, 8)
  const plain = (value) => JSON.parse(JSON.stringify(value))
  const plan = planWeek(
    [
      { id: 'low', title: '低分', score: 0.4 },
      { id: 'high', title: '高分', score: 0.9 },
      { id: 'busy', title: '已发', score: 1 },
      { id: 'mid', title: '中分', score: 0.7 },
      { id: 'again', title: '再发', score: 0.95 },
    ],
    [
      { clip_id: 'busy', status: 'completed', title: '已发' },
      { clip_id: 'again', status: 'cancelled', title: '再发' },
      { clip_id: 'wed', status: 'scheduled', title: '周三已排', scheduled_date: '2026-09-23T09:00:00' },
    ],
    now,
  ).map((slot) => ({ stamp: slot.stamp, state: slot.state, clipId: slot.clipId, title: slot.title }))
  assert.deepEqual(plain(plan), [
    { stamp: '2026-09-21T09:00:00', state: 'new', clipId: 'again', title: '再发' },
    { stamp: '2026-09-23T09:00:00', state: 'taken', clipId: 'wed', title: '周三已排' },
    { stamp: '2026-09-25T09:00:00', state: 'new', clipId: 'high', title: '高分' },
  ])
})

const { publishGuideHref, PUBLISH_GUIDE_ORIGIN, PUBLISH_GUIDE_PATH } = load('../src/publish/guide.ts')

test('the in-app tutorial opens the official guide with the current language', () => {
  assert.equal(PUBLISH_GUIDE_ORIGIN, 'https://zhouxiaoka.github.io/autoclip_intro')
  assert.equal(PUBLISH_GUIDE_PATH, '/guides/publish/')
  assert.equal(publishGuideHref('zh'), 'https://zhouxiaoka.github.io/autoclip_intro/guides/publish/?lang=zh')
  assert.equal(publishGuideHref('pt-BR'), 'https://zhouxiaoka.github.io/autoclip_intro/guides/publish/?lang=pt')
  assert.equal(publishGuideHref('de'), 'https://zhouxiaoka.github.io/autoclip_intro/guides/publish/?lang=en')
  assert.equal(publishGuideHref(), 'https://zhouxiaoka.github.io/autoclip_intro/guides/publish/?lang=en')
})

test('calendar opens on the next scheduled month', () => {
  const now = new Date(2026, 8, 22, 8)
  const plain = (value) => JSON.parse(JSON.stringify(value))
  assert.deepEqual(plain(focusMonth([
    { status: 'completed', submitted_at: '2026-09-01T09:00:00' },
    { status: 'scheduled', scheduled_date: '2026-10-01T09:00:00' },
    { status: 'cancelled', scheduled_date: '2026-11-01T09:00:00' },
  ], now)), { year: 2026, month: 9 })
  assert.deepEqual(plain(focusMonth([], now)), { year: 2026, month: 8 })
})

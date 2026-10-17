// R30 #419 I492/I494/I495: each append refusal has its own error_code; the existing errorText -> t() path picks the
// copy, and every shipped locale (all 8) has it, so no user ever sees the raw code or a Chinese fallback.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

const { errorText } = loadTs(path.join(__dirname, '../src/features/studio/errorText.ts'))
const LOCALES = fs.readdirSync(path.join(__dirname, '../src/i18n/locales')).filter(f => f.endsWith('.json')).map(f => f.replace('.json', ''))
const CASES = [['append_platform_exists', 409, '该平台已有版本'], ['append_no_auto_output', 400, '没有可自动生成的平台版本'],
  ['append_retry_pending', 409, '请先确认待处理的重试'], ['append_attempt_running', 409, '上一次制作还没结束，请稍后再追加平台']]

test('the app ships 8 locales', () => assert.equal(LOCALES.length, 8))
for (const [code, status, key] of CASES) {
  test(`R30 ${code}: errorText maps the code, every locale translates it`, () => {
    const err = { message: `Request failed with status code ${status}`, response: { status, data: { detail: { error_code: code, message: 'backend text' } } } }
    assert.equal(errorText(err), key)
    for (const lang of LOCALES) {
      const text = JSON.parse(fs.readFileSync(path.join(__dirname, `../src/i18n/locales/${lang}.json`), 'utf8'))[key]
      assert.ok(text, `${lang} has the copy`)
      assert.ok(!text.includes(code), `${lang} does not show the raw code`)
      if (lang !== 'zh') assert.notEqual(text, key, `${lang} is translated`)
    }
  })
}
test('R30 unknown coded detail falls back to the backend message', () => {
  assert.equal(errorText({ response: { data: { detail: { error_code: 'other', message: '后端原文' } } } }), '后端原文')
})

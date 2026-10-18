// 1.5.7 refuses append-platform with one code. The page translates it; the lifecycle codes are gone.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

const { errorText } = loadTs(path.resolve(__dirname, '../src/features/studio/errorText.ts'))
const refusal = code => ({ response: { status: 409, data: { detail: { error_code: code, message: 'x' } } } })

test('append platform is one refusal, not a lifecycle of error codes', () => {
  assert.equal(errorText(refusal('append_platform_unavailable')), '这一版还不能追加平台，请新建一个项目')
})

const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const fs = require('node:fs')
const { loadTs } = require('./load-ts.cjs')
const fa = loadTs(path.resolve(__dirname, '../src/features/studio/failureAction.ts'))

test('R21 #162: vision-stage user-cause failure sends 「去设置」 to the vision binding', () => {
  assert.equal(fa.failureAction('llm_auth_invalid', 'invalid_key', 'vision').destination, '/settings?section=vision')
  assert.equal(fa.failureAction('authentication', null, 'vision').destination, '/settings?section=vision')
  assert.equal(fa.failureAction('authentication', null, 'subtitle').destination, '/settings?section=speech')
  for (const stage of ['analyze', 'screen', 'render', undefined, null, '']) assert.equal(fa.failureAction('invalid_key', null, stage).destination, '/settings?section=analysis', String(stage))
  // every section we emit is a key SettingsPage understands
  const page = fs.readFileSync(path.resolve(__dirname, '../src/pages/SettingsPage.tsx'), 'utf8')
  for (const s of ['vision', 'speech', 'analysis']) assert.match(page, new RegExp(`\\n\\s*${s}: \\{ section: 'ai', anchor: 'ai-defaults-`), s)
})

test('R21 #163: precise upstream type wins over the coarse error_code (one classification)', () => {
  const perm = '这个 API Key 没有该模型的使用权限，请到设置里更换'
  assert.equal(fa.failureAction('llm_auth_invalid', 'permission_denied').reason, perm)
  assert.equal(fa.failureAction('authentication', 'permission_denied').reason, perm)
  assert.equal(fa.failureAction('llm_auth_invalid', 'insufficient_quota').reason, '服务商账户余额不足，请充值或换一个服务商')
  // non-user upstream does not erase a user-cause code
  assert.equal(fa.failureAction('insufficient_quota', 'rate_limited').reason, '服务商账户余额不足，请充值或换一个服务商')
  assert.equal(fa.failureAction('timeout', 'rate_limited').kind, 'retry')
})

// Behavior tests for the failure-action page rule and secondary causes.

// failure-action.test.cjs
;(() => {
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
  const perm = '当前令牌没有该模型的权限，请到服务商控制台勾选模型或更换分组。'
  assert.equal(fa.failureAction('llm_auth_invalid', 'permission_denied').reason, perm)
  assert.equal(fa.failureAction('authentication', 'permission_denied').reason, perm)
  assert.equal(fa.failureAction('llm_auth_invalid', 'insufficient_quota').reason, '余额或令牌额度不足，请充值或更换令牌后再试。')
  // non-user upstream does not erase a user-cause code
  assert.equal(fa.failureAction('insufficient_quota', 'rate_limited').reason, '余额或令牌额度不足，请充值或更换令牌后再试。')
  assert.equal(fa.failureAction('timeout', 'rate_limited').kind, 'retry')
})
})()

// failure-action.test.cjs
;(() => {
const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const fs = require('node:fs')
const { loadTs } = require('./load-ts.cjs')
const fa = loadTs(path.resolve(__dirname, '../src/features/studio/failureAction.ts'))

// PM rule : stats stay product-first; the page leads with any cause the user can fix.
// Shape = backend analysis record for content(ASR 401) + highlight(vision timeout), either goal order.
const record = { error: 'x', error_code: 'timeout', failure_stage: 'vision', upstream_error_type: null,
  secondary_error_codes: ['authentication'], secondary_upstream_error_types: ['invalid_key'], secondary_failure_stages: ['subtitle'] }

for (const order of ['content,highlight', 'highlight,content']) {
  test(`R24 page: auth + timeout (${order}) shows the auth reason and 「去设置」`, () => {
    const action = fa.pageFailureAction(record)
    assert.equal(action.kind, 'settings')
    assert.equal(action.destination, '/settings?section=speech')
    assert.equal(action.reason, fa.failureAction('authentication', 'invalid_key', 'subtitle').reason)
  })
}

test('R24 page: product-only causes still retry', () => {
  assert.equal(fa.pageFailureAction({ error_code: 'timeout', secondary_error_codes: ['render'], secondary_upstream_error_types: [''] }).kind, 'retry')
})

test('R24 page: FailureActions uses the page rule', () => {
  const src = fs.readFileSync(path.resolve(__dirname, '../src/features/studio/FailureActions.tsx'), 'utf8')
  assert.match(src, /pageFailureAction\(info\)/)
})

test('R24 page: StudioResults hands the secondary causes to FailureActions', () => {
  const src = fs.readFileSync(path.resolve(__dirname, '../src/features/studio/StudioResults.tsx'), 'utf8')
  assert.match(src, /receiptFailureInfo\(workspace\.attempts, workspace\.analysis\?\.run_id\) \|\| analysisPageFailure\(workspace\.analysis, workspace\.generation\)/)
  const info = fa.analysisPageFailure(record)
  assert.deepEqual(info.secondary_error_codes, ['authentication'])
  assert.deepEqual(info.secondary_upstream_error_types, ['invalid_key'])
  assert.deepEqual(info.secondary_failure_stages, ['subtitle'])
  assert.equal(fa.pageFailureAction(info).kind, 'settings')
  assert.equal(fa.pageFailureAction(info).destination, '/settings?section=speech')
})
})()

// failure-action.test.cjs
;(() => {
const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const fs = require('node:fs')
const { loadTs } = require('./load-ts.cjs')
const wf = loadTs(path.resolve(__dirname, '../src/analytics/workflow.ts'))
const catalog = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../docs/analytics/event_catalog.json'), 'utf8'))
const plan = fs.readFileSync(path.resolve(__dirname, '../../docs/analytics/TRACKING_PLAN.md'), 'utf8')
const src = fs.readFileSync(path.resolve(__dirname, '../src/analytics/workflow.ts'), 'utf8')
const SECONDARY = ['secondary_error_codes', 'secondary_upstream_error_types']
const TERMINALS = ['studio_generation_finished', 'studio_production_finished']

test('R24 #2: both secondary fields are registered on both terminals (description, values, comma format)', () => {
  for (const ev of TERMINALS) {
    const opt = catalog.events[ev].optional_properties || {}
    for (const k of SECONDARY) {
      assert.ok(opt[k], `${ev}.${k} not registered`)
      assert.ok(opt[k].description && opt[k].format === 'comma_joined' && opt[k].max_items === 3, `${ev}.${k}`)
      assert.ok(catalog.enums[opt[k].values], `${ev}.${k} values enum`)
    }
  }
  for (const k of SECONDARY) assert.match(plan, new RegExp('`' + k + '`'))
})

test('R24 #2: the registered allow-lists are the ones the sanitizer enforces', () => {
  const codes = loadTs(path.resolve(__dirname, '../src/analytics/failureCodes.ts'))
  assert.equal(src.includes('const ERROR_CODE = /^'), false)
  assert.deepEqual([...catalog.enums.studio_error_code].sort(), [...codes.STUDIO_ERROR_CODES].sort())
  for (const code of catalog.enums.studio_error_code) assert.equal(codes.ERROR_CODE.test(code), true, code)
  assert.equal(codes.ERROR_CODE.test('http_429'), true)
  assert.equal(codes.ERROR_CODE.test('disk'), false)
  assert.equal(codes.ERROR_CODE.test('not_a_code'), false)
  assert.equal(catalog.events.studio_production_finished.optional_properties.secondary_upstream_error_types.values, 'upstream_error_type')
})

test('R24 #2: a terminal carries no unregistered secondary_* field (page-only stages stay off the event)', () => {
  const out = wf.safeStudioProperties({ secondary_error_codes: ['authentication'], secondary_upstream_error_types: ['invalid_key'],
    secondary_failure_stages: ['subtitle'], secondary_extra: ['x'] })
  const registered = Object.keys(catalog.events.studio_production_finished.optional_properties || {})
  const emitted = Object.keys(out).filter(k => k.startsWith('secondary_'))
  assert.deepEqual(emitted.sort(), [...SECONDARY].sort())
  for (const k of emitted) assert.ok(registered.includes(k), k)
})
})()

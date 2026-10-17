const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const fs = require('node:fs')
const { loadTs } = require('./load-ts.cjs')
const fa = loadTs(path.resolve(__dirname, '../src/features/studio/failureAction.ts'))

// PM rule (R24): stats stay product-first; the page leads with any cause the user can fix.
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
  assert.match(src, /receiptFailureInfo\(workspace\.attempts, workspace\.analysis\.run_id\) \|\| analysisPageFailure\(workspace\.analysis, workspace\.generation\)/)
  const info = fa.analysisPageFailure(record)
  assert.deepEqual(info.secondary_error_codes, ['authentication'])
  assert.deepEqual(info.secondary_upstream_error_types, ['invalid_key'])
  assert.deepEqual(info.secondary_failure_stages, ['subtitle'])
  assert.equal(fa.pageFailureAction(info).kind, 'settings')
  assert.equal(fa.pageFailureAction(info).destination, '/settings?section=speech')
})

const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const root = path.resolve(__dirname, '../..')
const catalogs = ['backend/core/event_catalog.json', 'docs/analytics/event_catalog.json'].map(rel =>
  JSON.parse(fs.readFileSync(path.join(root, rel), 'utf8')))

for (const catalog of catalogs) {
  const props = catalog.events.studio_generation_finished.optional_properties
  for (const key of ['source_duration_sec', 'platform_count', 'is_first_success_device', 'attempt_index_on_device']) {
    assert.ok(props[key], key)
  }
  for (const key of ['eta_initial_min', 'resumed_from', 'retry_kind']) {
    assert.equal(props[key].nullable, true, key)
  }
}

const contract = fs.readFileSync(path.join(root, 'frontend/src/analytics/successRateContract.ts'), 'utf8')
for (const key of ['source_duration_sec', 'platform_count', 'is_first_success_device', 'attempt_index_on_device']) {
  assert.match(contract, new RegExp(`'${key}'`))
}

const sql = fs.readFileSync(path.join(root, 'docs/analytics/success_rate.sql'), 'utf8')
assert.match(sql, /图 7（M1）：一次成功占比/)
assert.match(sql, /图 8（M1）：从未成功占比/)
assert.match(sql, /图 9（M1）：按 provider/)
assert.match(sql, /first_try_success_rate/)
assert.match(sql, /never_succeeded_rate/)

console.log('m1-success-dims ok')

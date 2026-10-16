const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const fs = require('node:fs')
const { loadTs } = require('./load-ts.cjs')

const presets = Object.keys(JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../backend/presets/provider_presets.json'), 'utf8')).providers)

test('R16 #41 every preset survives frontend provider sanitizing (no other for known presets)', () => {
  assert.equal(presets.length, 39)
  const workflow = loadTs(path.resolve(__dirname, '../src/analytics/workflow.ts'))
  const contract = loadTs(path.resolve(__dirname, '../src/analytics/successRateContract.ts'))
  for (const id of presets) {
    assert.equal(workflow.safeStudioProperties({ provider: id }).provider, id, id)
    assert.equal(contract.sanitizeProvider(id), id, id)
  }
  assert.deepEqual([...contract.TELEMETRY_PROVIDERS], [...presets, 'compatible', 'other'])
  assert.equal(workflow.safeStudioProperties({ provider: 'my-gateway' }).provider, undefined)
})

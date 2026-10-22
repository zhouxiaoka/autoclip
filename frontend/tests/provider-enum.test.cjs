// Behavior tests for the shared provider enum.

// provider-enum.test.cjs
;(() => {
const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const fs = require('node:fs')
const { loadTs } = require('./load-ts.cjs')

const presets = Object.keys(JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../backend/presets/provider_presets.json'), 'utf8')).providers)

test('R16 #41 every preset survives frontend provider sanitizing (no other for known presets)', () => {
  assert.equal(presets.length, 40)
  const workflow = loadTs(path.resolve(__dirname, '../src/analytics/workflow.ts'))
  const contract = loadTs(path.resolve(__dirname, '../src/analytics/successRateContract.ts'))
  for (const id of presets) {
    assert.equal(workflow.safeStudioProperties({ provider: id }).provider, id, id)
    assert.equal(contract.sanitizeProvider(id), id, id)
  }
  assert.deepEqual([...contract.TELEMETRY_PROVIDERS], [...presets, 'compatible', 'other'])
  assert.equal(workflow.safeStudioProperties({ provider: 'my-gateway' }).provider, undefined)
})

test('R19 #96 connection-test / settings experience events keep every preset provider (no other)', () => {
  const contract = loadTs(path.resolve(__dirname, '../src/analytics/successRateContract.ts'))
  const experience = loadTs(path.resolve(__dirname, '../src/analytics/experience.ts'), {
    './posthog': { captureBusinessEvent() {} },
    './observer': { workflow: { generation() { return 1 }, active() { return false } } },
    './workflow': loadTs(path.resolve(__dirname, '../src/analytics/workflow.ts')),
    './successRateContract': contract,
  }, path.resolve(__dirname, '../src/analytics'))
  for (const id of [...presets, 'compatible']) {
    assert.equal(experience.safeExperience({ provider: id }).provider, id, id)
    assert.equal(contract.telemetryProvider(id), id, id)
  }
  for (const id of ['siliconflow', 'openrouter', 'anthropic', 'byteplus-modelark']) assert.equal(experience.safeExperience({ provider: id }).provider, id)
  assert.equal(experience.safeExperience({ provider: 'https://my-gateway.example/v1' }).provider, undefined)
  assert.equal(contract.telemetryProvider('my-gateway'), 'other')
  assert.equal(contract.telemetryProvider(undefined), 'other')
  // useModelSettings must not keep a private provider whitelist for events.
  const hook = fs.readFileSync(path.resolve(__dirname, '../src/features/settings/useModelSettings.ts'), 'utf8')
  assert.doesNotMatch(hook, /PROVIDERS\[[^\]]*\]\s*\?\s*[^:]+:\s*'other'/)
  assert.doesNotMatch(hook, /provider\s*\|\|\s*'other'/)
  assert.equal((hook.match(/telemetryProvider\(/g) || []).length, 5)
})
})()

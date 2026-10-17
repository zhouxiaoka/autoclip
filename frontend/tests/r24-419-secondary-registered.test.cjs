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
  const regex = src.match(/const ERROR_CODE = \/\^\(([^)]*)\)\$\//)[1].split('|').filter(c => !c.startsWith('http_'))
  assert.deepEqual([...catalog.enums.studio_error_code].sort(), [...regex].sort())
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

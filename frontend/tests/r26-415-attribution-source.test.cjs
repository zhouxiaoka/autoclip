// R26 #415 #392: attribution_source (request | phase | local) reaches the studio events; nothing else.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const ts = require('typescript')
const { runInSandbox } = require('./vm-sandbox.cjs')

function load(name) {
  const file = path.join(__dirname, '../src/analytics', `${name}.ts`)
  const source = fs.readFileSync(file, 'utf8').replaceAll('import.meta.env', '__env')
  const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText
  const module = { exports: {} }
  runInSandbox(js, { exports: module.exports, module, Date, Math, console, __env: { DEV: false },
    require: (id) => {
      if (id === './failureCodes') return require('./load-ts.cjs').loadTs(path.join(__dirname, '../src/analytics/failureCodes.ts'))
      throw new Error(`Unexpected dependency: ${id}`)
    } }, { filename: file })
  return module.exports
}
const workflow = load('workflow')

test('allowlist keeps the three attribution sources and drops anything else', () => {
  for (const value of ['request', 'phase', 'local']) {
    assert.equal(workflow.safeStudioProperties({ attribution_source: value }).attribution_source, value)
  }
  assert.equal(workflow.safeStudioProperties({ attribution_source: '/Users/me/secret' }).attribution_source, undefined)
})

test('pickAttribution carries the record source; a local failure without identity still says local', () => {
  const own = workflow.pickAttribution({ status: 'failed', provider: 'glm', config_source: 'preset', attribution_source: 'phase' })
  assert.equal(own.attribution_source, 'phase')
  const local = workflow.pickAttribution({ status: 'failed', attribution_source: 'local', http_status: 503 })
  assert.equal(local.attribution_source, 'local')
  assert.equal(local.provider, undefined)
  assert.equal(local.http_status, undefined)
})

test('catalog registers the enum on the three studio terminal events', () => {
  const catalog = JSON.parse(fs.readFileSync(path.join(__dirname, '../../backend/core/event_catalog.json'), 'utf8'))
  assert.deepEqual(catalog.enums.attribution_source, ['request', 'phase', 'local'])
  for (const event of ['studio_screen_finished', 'studio_generation_finished', 'studio_production_finished']) {
    assert.equal(catalog.events[event].enums.attribution_source, 'attribution_source', event)
  }
})

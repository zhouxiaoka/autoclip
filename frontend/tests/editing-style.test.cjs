const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

function load(rel) {
  const exports = {}
  const source = fs.readFileSync(path.join(__dirname, '../src', rel), 'utf8')
  vm.runInNewContext(ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText, { exports, CSS: { supports: () => true }, Date, Math, JSON, Number, Array, Object, Map, Set, String, URL, RegExp })
  return exports
}

const style = load('features/studio/editingStyle.ts')
const workflow = load('analytics/workflow.ts')

test('a manual style wins and a bad recommendation stays editorial', () => {
  const decision = (manual, recommended, current) => JSON.parse(JSON.stringify(style.selectionAfterRecommendation(manual, recommended, current)))
  assert.deepEqual(decision('street', 'editorial', 'editorial'), { selected: 'street', apply: false })
  assert.deepEqual(decision(null, 'street', 'editorial'), { selected: 'street', apply: true })
  assert.deepEqual(decision(null, 'editorial', 'editorial'), { selected: 'editorial', apply: false })
  const bad = style.normalizeRecommendation({ template: 'neon', reason_code: 'secret title', signals: { people: 'duo', scene: 'street' } })
  assert.equal(bad.template, 'editorial')
  assert.equal(bad.reason_code, 'default')
  assert.equal(bad.signals.people, 'duo')
  assert.equal(bad.signals.scene, 'street')
  assert.equal(style.normalizeRecommendation(null), null)
  assert.equal(style.degradeFromEnvironment(2, true, false), true)
  assert.equal(style.degradeFromEnvironment(8, true, false), false)
  assert.equal(style.degradeFromEnvironment(8, false, false), true)
  assert.equal(style.intelMacFromHints('macOS', 'x86'), true)
  assert.equal(style.intelMacFromHints('macOS', 'arm'), false)
  assert.equal(style.intelMacFromHints('Windows', 'x86'), false)
  assert.equal(JSON.stringify(style.templateImportFields(false, 'street', 'editorial')), '{}')
})

test('picker telemetry keeps recommendation enums and drops free text', () => {
  const shown = workflow.safeStudioProperties({
    recommended: 'street', reason_code: 'street_quick', flag_variant: 'visual', source_kind: 'link', latency_ms: 180,
    title: 'private title',
  })
  assert.equal(shown.recommended, 'street')
  assert.equal(shown.reason_code, 'street_quick')
  assert.equal(shown.flag_variant, 'visual')
  assert.equal(shown.latency_ms, 180)
  assert.equal(JSON.stringify(shown).includes('private'), false)
  const play = workflow.safeStudioProperties({ template: 'editorial', trigger: 'hover', first_frame_ms: 40, is_recommended: true })
  assert.equal(play.trigger, 'hover')
  assert.equal(play.first_frame_ms, 40)
  assert.equal(play.is_recommended, true)
  const legacy = workflow.safeStudioProperties({ trigger: 'manual' })
  assert.equal(legacy.trigger, 'manual')
  const finished = workflow.safeStudioProperties(workflow.generationSummary({
    generation: { recommended_template: 'editorial', accepted_recommendation: false },
    output_variants: [], jobs: [], drafts: [],
  }))
  assert.equal(finished.recommended_template, 'editorial')
  assert.equal(finished.accepted_recommendation, false)
})

test('bundled style previews stay inside the size budget', () => {
  const dir = path.join(__dirname, '../src/assets/editing-style')
  const names = fs.readdirSync(dir).filter(name => !name.startsWith('.'))
  assert.deepEqual(names.sort(), [
    'classic.poster.webp', 'classic.preview.mp4', 'classic.preview.webm',
    'editorial.poster.webp', 'editorial.preview.mp4', 'editorial.preview.webm',
    'street.poster.webp', 'street.preview.mp4', 'street.preview.webm',
  ])
  let total = 0
  for (const name of names) {
    const size = fs.statSync(path.join(dir, name)).size
    total += size
    assert.ok(size <= 300 * 1024, name)
    if (name.endsWith('.poster.webp')) assert.ok(size <= 30 * 1024, name)
    if (name.endsWith('.webm') || name.endsWith('.mp4')) assert.ok(size <= 120 * 1024, name)
  }
  assert.ok(total <= 500 * 1024, String(total))
})

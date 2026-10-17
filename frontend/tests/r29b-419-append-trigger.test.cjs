// R29b #419 (Dong): an appended platform round's terminal carries trigger=append_platform so the dashboard can
// split it from first generations; the results page says "this append finished", never "re-run", in every language.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

const memory = () => { const m = new Map(); return { getItem: k => m.get(k) ?? null, setItem: (k, v) => m.set(k, v), removeItem: k => m.delete(k) } }
const A = 't-aaaaaaaaaaaaaaaa', B = 't-bbbbbbbbbbbbbbbb', F1 = 't-f1f1f1f1f1f1f1f1', F2 = 't-f2f2f2f2f2f2f2f2'
const gen = (id, seq, flow, trigger) => ({ attempt_id: id, flow_id: flow, sequence: seq, kind: 'generation', trigger, state: 'completed', run_id: 'run-' + id.slice(2, 6), summary: {} })

test('R29b: the generation terminal carries the receipt trigger (append_platform), registered in the catalog', () => {
  const workflow = loadTs(path.resolve(__dirname, '../src/analytics/workflow.ts'))
  const events = []
  const t = new workflow.WorkflowTracker(memory(), () => true, (event, props) => { events.push({ event, props }); return true }, () => Date.parse('2026-10-17T00:00:00Z'))
  const first = gen(A, 1, F1, 'initial'), append = gen(B, 2, F2, 'append_platform')
  t.watchAttempt('p1', first); t.watchAttempt('p1', append)
  const live = { material_origin: 'user', attempts: [first, append], generation: { status: 'completed', attempt_id: B }, output_variants: [], analysis: { status: 'completed' } }
  for (const w of t.list()) t.observeStudio(w, live)
  const got = Object.fromEntries(events.filter(e => e.event === 'studio_generation_finished').map(e => [e.props.attempt_id, e.props.trigger]))
  assert.deepEqual(got, { [A]: 'initial', [B]: 'append_platform' })
  const catalog = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../docs/analytics/event_catalog.json'), 'utf8'))
  assert.equal(catalog.events.studio_generation_finished.enums.trigger, 'attempt_trigger')
  assert.ok(catalog.enums.attempt_trigger.includes('append_platform'))
})

const KEY = '本次追加已完成，之前还有 {{count}} 条未完成版本可重试。'
const RERUN = { zh: /重跑/, en: /re-?run/i, es: /repetici|reejecu/i, fr: /relance/i, pt: /nova execu|reexecu/i, ru: /повторн/i, ja: /再実行/, ko: /재실행/ }
for (const lang of Object.keys(RERUN)) {
  test(`R29b ${lang}: the append line exists, never says re-run, count is a trailing value`, () => {
    const text = JSON.parse(fs.readFileSync(path.join(__dirname, `../src/i18n/locales/${lang}.json`), 'utf8'))[KEY]
    assert.ok(text, 'translated')
    assert.doesNotMatch(text, RERUN[lang])
    if (lang === 'zh') assert.match(text, /^本次追加已完成，之前还有/)
    else if (['ja', 'ko'].includes(lang)) assert.match(text, /\{\{count\}\}/)   // no plural forms
    else assert.match(text, /:\s*\{\{count\}\}$/)
  })
}

test('R30 I490: appendPlatforms watches the returned receipt with the existing watchAttempt entry', async () => {
  const { setup } = require('./helpers/studio-harness.cjs')
  const receipt = { attempt_id: 't-cccccccccccccccc', kind: 'generation', trigger: 'append_platform', state: 'open', sequence: 2, flow_id: 't-f3f3f3f3f3f3f3f3' }
  const h = setup({ post: () => ({ variants: [], attempt: receipt }) })
  await h.studioApi.appendPlatforms('p1', ['bilibili'], false)
  assert.equal(JSON.stringify(h.tracker.list().map(w => w.attemptId)), JSON.stringify([receipt.attempt_id]))
})

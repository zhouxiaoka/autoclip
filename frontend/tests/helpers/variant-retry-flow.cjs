// Drives the real partial page 「重试这条」 flow and returns the captured analytics events.
// `node tests/helpers/variant-retry-flow.cjs` prints them as JSON (used by the DuckDB v4 SQL test).
const { setup, renderResults } = require('./studio-harness.cjs')

async function run({ stopAfterClick = false } = {}) {
  const h = setup()
  const { tracker, events } = h
  const partial = { material_origin: 'user', generation: { auto_start: true, status: 'partial', error_code: 'timeout', completed_variant_count: 1 },
    analysis: { status: 'completed', outcome: 'partial' }, drafts: [], jobs: [], events: [],
    output_variants: [{ id: 'v-ok', status: 'completed', strategy_id: 'douyin' }, { id: 'v-bad', status: 'failed', strategy_id: 'xhs', render_job_id: 'job-1' }] }
  tracker.watch('studio-generation', 'p1')
  tracker.observeStudio(tracker.list().find(w => w.kind === 'studio-generation'), partial)
  const cards = []
  renderResults(partial, h.studioApi, cards)
  await cards.find(c => c.variant.id === 'v-bad').onRetry()   // what the card's 「重试这条」 button calls
  if (stopAfterClick) return h
  // backend after the retry: variant re-rendered, generation completed
  const done = { ...partial, generation: { ...partial.generation, status: 'completed', error_code: undefined, completed_variant_count: 2 },
    output_variants: [{ id: 'v-ok', status: 'completed', strategy_id: 'douyin' }, { id: 'v-bad', status: 'completed', strategy_id: 'xhs', render_job_id: 'job-2' }] }
  for (const w of tracker.list()) tracker.observeStudio(w, done)
  return h
}

module.exports = { run }
if (require.main === module) run().then(h => process.stdout.write(JSON.stringify(h.events)))

// #419 real chain: backend workspace snapshots + the backend's retry-command response (JSON on stdin, produced by
// backend/tests/test_studio_attempts.py through the real store/jobs) -> real tracker + real studio api +
// real StudioResults 「重试这条」 button -> captured events (stdout) -> the real v4 SQL in the Python test.
const { setup, renderResults } = require('./studio-harness.cjs')

async function run(input) {
  const memory = new Map()
  const storage = { getItem: k => memory.get(k) ?? null, setItem: (k, v) => memory.set(k, v), removeItem: k => memory.delete(k) }
  const posts = []
  const h = setup({ storage, post: (url, body) => { posts.push({ url, body }); return input.retry_response } })
  h.tracker.rememberProject(input.pid, { material_origin: 'user' })
  h.tracker.watch('studio-generation', input.pid, undefined, undefined, {}, false, input.import_run)
  for (const w of h.tracker.list()) h.tracker.observeStudio(w, input.partial)
  const cards = []
  renderResults(input.partial, h.studioApi, cards)
  await cards.find(c => c.variant.id === input.retry_variant).onRetry()
  // restart: a fresh tracker over the same storage sees the final state (twice) - no duplicate, same lineage
  const again = new h.workflow.WorkflowTracker(storage, () => true, h.capture)
  for (let i = 0; i < 2; i++) for (const w of again.list()) again.observeStudio(w, input.final)
  return { events: h.events, posts }
}

module.exports = { run }
if (require.main === module) {
  let raw = ''
  process.stdin.on('data', d => { raw += d }).on('end', () => run(JSON.parse(raw)).then(r => process.stdout.write(JSON.stringify(r))))
}

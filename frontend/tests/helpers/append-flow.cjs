// R30 #419 I490 real chain: first-round workspace + the backend's append response (JSON on stdin, produced by
// backend/tests/test_r30_419_append_chain_duckdb.py through the real store/jobs) -> real tracker + real studio api
// appendPlatforms -> captured events (stdout) -> the real v4 SQL in the Python test.
const { setup } = require('./studio-harness.cjs')

async function run(input) {
  const memory = new Map()
  const storage = { getItem: k => memory.get(k) ?? null, setItem: (k, v) => memory.set(k, v), removeItem: k => memory.delete(k) }
  const posts = []
  const h = setup({ storage, post: (url, body) => { posts.push({ url, body }); return input.append_response } })
  h.tracker.rememberProject(input.pid, { material_origin: 'user' })
  h.tracker.watch('studio-generation', input.pid, undefined, undefined, {}, false, input.import_run)
  for (const w of h.tracker.list()) h.tracker.observeStudio(w, input.first)
  await h.studioApi.appendPlatforms(input.pid, input.platforms, false)
  const again = new h.workflow.WorkflowTracker(storage, () => true, h.capture)  // restart: no duplicate
  for (let i = 0; i < 2; i++) for (const w of again.list()) again.observeStudio(w, input.final)
  return { events: h.events, posts }
}

module.exports = { run }
if (require.main === module) {
  let raw = ''
  process.stdin.on('data', d => { raw += d }).on('end', () => run(JSON.parse(raw)).then(r => process.stdout.write(JSON.stringify(r))))
}

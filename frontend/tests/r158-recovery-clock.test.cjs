// #418 R29: the timing contract of the install-recovery wait (157/418-r29-plan.md, Dong 11:49: cap = 2 x pollMs +
// 2 x READINESS_TIMEOUT_MS = 14s, OFFLINE_MS 30s). Every cell asserts the exact observation N that reaches the outcome
// and that observation N-1 still continues. Runs against the real controller with a virtual clock: each request
// advances the clock by its duration, the page waits T between the end of a round and the next poll.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

const dir = path.resolve(__dirname, '../src/features/studio')
const recovery = loadTs(path.join(dir, 'transcriptionRecovery.ts'), {}, dir)
const check = (code, extra = {}) => ({ checks: { transcription: { ok: code === 'ok', code, repair: 'none', ...extra } } })
const netErr = () => Object.assign(new Error('timeout of 5000ms exceeded'), { code: 'ECONNABORTED', response: undefined })

/** A downloading wait on a virtual clock. `mode`: 'down' (every probe ends without a response after probeMs),
 * 'up' (answered, no progress: probe probeMs + getModels readMs). `sleepOnce` is added inside the next request. */
function virtual({ mode, probeMs = 0, readMs = 0 }) {
  const v = { t: 0, mode, probeMs, readMs, sleepOnce: 0, polls: 0 }
  const sleep = () => { const s = v.sleepOnce; v.sleepOnce = 0; return s }
  const api = {
    readiness: async () => {
      v.t += v.probeMs + (v.mode === 'down' ? sleep() : 0)
      if (v.mode === 'down') throw netErr()
      return check('whisper_model_downloading', { model: 'base' })
    },
    getModels: async () => { v.t += v.readMs + sleep(); return [{ name: 'base', status: 'downloading', downloadProgress: null }] },
    getRuntimeStatus: async () => ({ status: 'installing' }), installRuntime: async () => {}, downloadModel: async () => {},
  }
  const c = recovery.createRecoveryController(api, { now: () => v.t })
  c.open('whisper_model_downloading', 'base')
  const label = () => c.state.phase === 'failed' && c.state.offline ? 'offline' : c.state.phase === 'downloading' ? 'continue' : c.state.phase
  /** n polls, each T after the previous round ended; returns the outcome label after each. */
  v.run = async (T, n) => { const seen = []; for (let i = 0; i < n; i++) { v.t += T; await c.poll(); v.polls++; seen.push(label()) } return seen }
  v.c = c
  return v
}
const S = 1000
/** [name, T, column, round] -> expected N. Columns: down (5s probe timeout) -> offline; up0 (answered at once, no
 * progress) -> timeout; slow (4.9s probe + 4.9s read) -> timeout. Observation spacing g = T + round, counted
 * c = min(g, 14s), N = ceil(threshold / c). */
const COLUMNS = {
  down: { mode: 'down', probeMs: 5 * S, outcome: 'offline' },
  up0: { mode: 'up', outcome: 'timeout' },
  slow: { mode: 'up', probeMs: 4900, readMs: 4900, outcome: 'timeout' },
  down15: { mode: 'down', probeMs: 15 * S, outcome: 'offline' },
  up15: { mode: 'up', probeMs: 7500, readMs: 7500, outcome: 'timeout' },
}
const MATRIX = [
  // T,      column,  N     (g, counted, wall clock)
  [2 * S,    'down',  5],   // g7 c7 -> 35s
  [2 * S,    'up0',   300], // c2 -> exactly 600s (>= boundary)
  [2 * S,    'slow',  51],  // g11.8 c11.8 -> 601.8s (the 14s cap keeps this column at 10 minutes)
  [4100,     'down',  4],   // g9.1 -> 36.4s (R28 E: never ended)
  [4100,     'up0',   147], // c4.1 -> 602.7s
  [4100,     'slow',  44],  // g13.9 -> 611.6s
  [9 * S,    'down',  3],   // g14 c14 -> 42s
  [9 * S,    'up0',   67],  // c9 -> 603s
  [9 * S,    'slow',  43],  // g18.8 c14 -> 808.4s
  [60 * S,   'down',  3],   // g65 c14 -> 195s (R28 G: never ended)
  [60 * S,   'up0',   43],  // c14 -> 43 min
  [60 * S,   'slow',  43],  // g69.8 c14 -> 50 min
  [2 * S,    'down15', 3],  // one round of 15s (Dong): g17 c14 -> 51s
  [2 * S,    'up15',  43],  // g17 c14 -> 731s
  [1 * S,    'down',  5],   // g6 -> exactly 30s (>= boundary of OFFLINE_MS)
  [1 * S,    'up0',   600], // c1 -> exactly 600s
  [1 * S,    'slow',  56],  // g10.8 -> 604.8s
]
const round = col => (COLUMNS[col].probeMs || 0) + (COLUMNS[col].readMs || 0)

test('R29 contract constants: OFFLINE_MS 30s, STALL_MS 10min, poll 2s, read timeout 5s (cap 14s)', () => {
  assert.deepEqual([recovery.OFFLINE_MS, recovery.STALL_MS, recovery.POLL_MS, recovery.READINESS_TIMEOUT_MS], [30 * S, 600 * S, 2 * S, 5 * S])
})

for (const [T, col, N] of MATRIX) {
  test(`R29 matrix: T=${T / S}s, ${col} -> ${COLUMNS[col].outcome} at exactly observation ${N}`, async () => {
    const v = virtual(COLUMNS[col])
    const seen = await v.run(T, N)
    assert.deepEqual(seen.slice(0, N - 1).filter(x => x !== 'continue'), [], `continue before observation ${N}`)
    assert.equal(seen[N - 1], COLUMNS[col].outcome, `observation ${N}`)
    assert.equal(v.t, N * (T + round(col)), 'wall clock N x g')
  })
}

test('R29 alternating answered / unanswered, no progress: never offline (every answer clears it), timeout at exactly 600s from either branch', async () => {
  for (const firstDown of [true, false]) {
    const v = virtual({ mode: 'up' })
    const seen = []
    for (let k = 1; k <= 300; k++) { v.mode = (k % 2 === 1) === firstDown ? 'down' : 'up'; seen.push(...await v.run(2 * S, 1)) }
    assert.deepEqual(seen.slice(0, 299).filter(x => x !== 'continue'), [], `firstDown=${firstDown}`)
    // observation 300 is unanswered when the first one was answered: the unanswered branch judges the stall too
    assert.equal(seen[299], 'timeout', `firstDown=${firstDown}: observation 300 (${v.mode})`)
  }
})

test('R29 sleep with a probe in flight: counts 14s (offline 26s -> 40s: offline); 14s -> 28s: still waiting, next poll 30s', async () => {
  for (const [before, wakeAs] of [[13, 'offline'], [7, 'continue']]) {
    const v = virtual({ mode: 'down' })
    assert.deepEqual((await v.run(2 * S, before)).filter(x => x !== 'continue'), [])
    v.sleepOnce = 30 * 60 * S
    assert.deepEqual(await v.run(2 * S, 1), [wakeAs], `${before * 2}s + 14s`)
    if (wakeAs === 'continue') assert.deepEqual(await v.run(2 * S, 1), ['offline'])
  }
})

test('R29 I576 (Dong): a 9m55s sleep inside the follow-up read counts 14s: 9:50 -> timeout on waking; 1:00 -> 1:14, then 8:46 more', async () => {
  for (const [before, wakeAs, more] of [[295, 'timeout', 0], [30, 'continue', 263]]) {
    const v = virtual({ mode: 'up' })
    assert.deepEqual((await v.run(2 * S, before)).filter(x => x !== 'continue'), [], `${before * 2}s before the sleep`)
    v.sleepOnce = 595 * S
    assert.deepEqual(await v.run(2 * S, 1), [wakeAs])
    if (!more) continue
    const after = await v.run(2 * S, more)
    assert.deepEqual([after.indexOf('timeout'), after.slice(0, more - 1).every(x => x === 'continue')], [more - 1, true], '526s = 263 polls more')
  }
})

test('R29 first round: open() starts counting at once (the first observation counts its whole spacing)', async () => {
  // T=2s, 5s timeouts: 7 + 7 + 7 + 7 + 7 = 35s at observation 5; a first observation counted as 0 would need 6
  const v = virtual(COLUMNS.down)
  assert.deepEqual(await v.run(2 * S, 5), ['continue', 'continue', 'continue', 'continue', 'offline'])
})

// mulberry32: a fixed PRNG so every seed is reproducible
const prng = seed => () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296 }
test('R29 property: T in [0.5s, 120s], round in [0s, 10s], 200 seeds: the outcome comes at exactly N = ceil(threshold / min(g, 14s))', async () => {
  for (let seed = 1; seed <= 200; seed++) {
    const r = prng(seed)
    const T = 500 + Math.floor(r() * 119500)
    const mode = r() < 0.5 ? 'down' : 'up'
    const probeMs = Math.floor(r() * 5000); const readMs = mode === 'up' ? Math.floor(r() * 5000) : 0
    const g = T + probeMs + readMs
    const N = Math.ceil((mode === 'down' ? 30 * S : 600 * S) / Math.min(g, 14 * S))
    const v = virtual({ mode, probeMs, readMs })
    const seen = await v.run(T, N)
    const at = seen.findIndex(x => x !== 'continue')
    assert.equal(at, N - 1, `seed ${seed}: T=${T} probe=${probeMs} read=${readMs} ${mode}: expected observation ${N}, got ${at + 1}`)
    assert.equal(seen[at], mode === 'down' ? 'offline' : 'timeout', `seed ${seed}`)
    assert.ok(v.t <= N * g, `seed ${seed}: within N x g`)
  }
})

test('R29 recoveryClock.observe (pure): counted = clamp(now - lastAt, 0, 2 x poll + 2 x read timeout); answers clear offline, progress clears stall', () => {
  const clockMod = loadTs(path.join(dir, 'recoveryClock.ts'), {}, dir)
  // JSON: the module runs in its own vm context (other Object prototype)
  const o = (c, now, answered, progressed, pollMs = 2 * S) => JSON.parse(JSON.stringify(clockMod.observe(c, { now, answered, progressed, pollMs, readTimeoutMs: 5 * S })))
  const c0 = JSON.parse(JSON.stringify(clockMod.startClock(1000)))
  assert.deepEqual(c0, { lastAt: 1000, offlineMs: 0, stalledMs: 0, unanswered: false })
  assert.equal(clockMod.capMs(2 * S, 5 * S), 14 * S)
  assert.equal(o(c0, 500, false, false).counted, 0, 'a clock going backwards counts 0')
  assert.equal(o(c0, 1000 + 13999, false, false).counted, 13999)
  assert.equal(o(c0, 1000 + 10 * 60 * S, false, false).counted, 14 * S)
  const a = o(c0, 8000, false, false)
  assert.deepEqual(a, { clock: { lastAt: 8000, offlineMs: 7000, stalledMs: 7000, unanswered: true }, counted: 7000, outcome: 'continue' })
  assert.deepEqual(o(a.clock, 10000, true, false).clock, { lastAt: 10000, offlineMs: 0, stalledMs: 9000, unanswered: false })
  assert.deepEqual(o(a.clock, 10000, true, true).clock, { lastAt: 10000, offlineMs: 0, stalledMs: 0, unanswered: false })
  assert.equal(o({ lastAt: 0, offlineMs: 16 * S, stalledMs: 0, unanswered: true }, 14 * S, false, false).outcome, 'offline', '16 + 14 = 30')
  assert.equal(o({ lastAt: 0, offlineMs: 0, stalledMs: 586 * S, unanswered: false }, 14 * S, true, false).outcome, 'timeout', '586 + 14 = 600')
  assert.equal(o({ lastAt: 0, offlineMs: 0, stalledMs: 585 * S, unanswered: false }, 14 * S, true, false).outcome, 'continue')
  assert.equal(o({ lastAt: 0, offlineMs: 29 * S, stalledMs: 599 * S, unanswered: true }, 2 * S, false, false).outcome, 'offline', 'offline wins over timeout')
  assert.equal(o({ lastAt: 0, offlineMs: 0, stalledMs: 599 * S, unanswered: true }, 2 * S, false, false).outcome, 'timeout', 'an unanswered observation judges the stall')
})

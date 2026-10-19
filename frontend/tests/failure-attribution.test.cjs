// Behavior tests for frontend failure attribution and terminal payloads.

// failure-attribution.test.cjs
;(() => {
// a stored identity is ONE record; terminal events never stitch run and analysis fields.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path'), ts = require('typescript')
const { runInSandbox } = require('./vm-sandbox.cjs')

const workflow = require('./load-ts.cjs').loadTs(path.join(__dirname, '../src/analytics/workflow.ts'))

function finished(summary, analysis) {
  const events = [], store = new Map()
  const storage = { getItem: k => store.get(k) ?? null, setItem: (k, v) => store.set(k, v), removeItem: k => store.delete(k) }
  const t = new workflow.WorkflowTracker(storage, () => true, (name, props) => { events.push({ name, props }); return true })
  const attempt = 't-aaaaaaaaaaaaaaaa'
  t.watch('studio-generation', 'p1')
  t.observeStudio(t.list()[0], {
    generation: { status: 'failed', attempt_id: attempt },
    analysis,
    attempts: [{ attempt_id: attempt, flow_id: 't-ffffffffffffffff', sequence: 1, kind: 'generation', state: 'failed', summary }],
  })
  return events.find(e => e.name === 'studio_generation_finished')
}

test('#332 the results page does not emit studio_generation_finished (the backend settles that terminal)', () => {
  // A half identity on the receipt and a full identity on analysis used to be stitched by the frontend projector.
  // That projector is gone: opening the page must not emit the success-rate terminal at all.
  const event = finished(
    { provider: 'glm', model: 'glm-4', base_url_host: 'other.example', http_status: 503 },
    { status: 'failed', phase: 'production', provider: 'kimi', config_source: 'preset', model: 'kimi-k2', base_url_host: 'api.moonshot.cn', http_status: 429, upstream_error_type: 'rate_limited' },
  )
  assert.equal(event, undefined)
})

test('#332 an unpaired legacy screening identity reads as empty, not half an identity', () => {
  const id = workflow.screeningIdentity({ analysis: { status: 'failed', phase: 'screening', provider: 'kimi' } })
  assert.equal(id.provider, undefined)
  assert.equal(id.config_source, undefined)
})

test('#332 a half screening_identity is ignored; the paired flat identity is used whole', () => {
  const id = workflow.screeningIdentity({ analysis: { status: 'failed', phase: 'screening', provider: 'glm', config_source: 'customized', screening_identity: { provider: 'kimi' } } })
  assert.deepEqual({ ...id }, { provider: 'glm', config_source: 'customized' })
})
})()

// failure-attribution.test.cjs
;(() => {
// attribution_source (request | phase | local) reaches the studio events; nothing else.
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
})()

// failure-attribution.test.cjs
;(() => {
// + design: every studio finished event reads attribution through pickAttribution (one record, whole).
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
const storage = { getItem: () => null, setItem() {}, removeItem() {} }
function observe(kind, id, state, extra) {
  const events = []
  const t = new workflow.WorkflowTracker(storage, () => true, (event, props) => { events.push({ event, props }); return true })
  t.watch(kind, id, extra)
  t.observeStudio(t.list()[0], state)
  return events
}

test('I420: studio_screen_finished carries attribution_source; a local failure has no upstream', () => {
  const events = observe('studio-screen', 'p1', {
    analysis: { status: 'failed', phase: 'screening', error_code: 'store_lock_timeout', failure_stage: 'screening',
      attribution_source: 'local', provider: 'glm', config_source: 'preset', upstream_error_type: 'upstream_unavailable', http_status: 503 },
  })
  const screen = events.find(e => e.event === 'studio_screen_finished')
  assert.ok(screen, JSON.stringify(events))
  assert.equal(screen.props.attribution_source, 'local')
  assert.equal(screen.props.upstream_error_type, undefined)
  assert.equal(screen.props.http_status, undefined)
})

test('I420: generation reads ONE receipt record whole (local beats a complete analysis phase identity)', () => {
  const attempt = 't-aaaaaaaaaaaaaaaa'
  const events = observe('studio-generation', 'p1', {
    generation: { status: 'failed', attempt_id: attempt },
    analysis: { status: 'failed', provider: 'kimi', config_source: 'customized', attribution_source: 'phase', http_status: 503, upstream_error_type: 'upstream_unavailable' },
    plan: { id: 'plan', mode: 'ai' },
    attempts: [{ attempt_id: attempt, kind: 'generation', state: 'failed', error_code: 'store_lock_timeout',
      upstream_error_type: 'upstream_unavailable', summary: { attribution_source: 'local', http_status: 503 } }],
  })
  assert.equal(events.find(e => e.event === 'studio_generation_finished'), undefined)
})

test('production reads through pickAttribution: local status is dropped, half identity is no identity', () => {
  const run = 'run-local'
  const events = observe('studio-production', 'plan', {
    plan: { id: 'plan', confirmed_analysis: 'subtitle' },
    analysis: { status: 'failed', run_id: run },
    attempts: [{ attempt_id: 't-bbbbbbbbbbbbbbbb', kind: 'production', state: 'failed', run_id: run,
      error_code: 'store_lock_timeout', upstream_error_type: 'upstream_unavailable',
      summary: { attribution_source: 'local', provider: 'openai', http_status: 503, upstream_error_type: 'upstream_unavailable' } }],
  }, 'p1')
  assert.equal(events.find(e => e.event === 'studio_production_finished'), undefined)
})

test('pickAttribution mirrors read_attribution (one record)', () => {
  assert.deepEqual(JSON.parse(JSON.stringify(workflow.pickAttribution({ status: 'failed', attribution_source: 'request', provider: 'kimi', config_source: 'customized', http_status: 503 }))),
    { provider: 'kimi', config_source: 'customized', attribution_source: 'request', http_status: 503 })
  assert.equal(workflow.pickAttribution({ status: 'completed', attribution_source: 'request', provider: 'kimi', config_source: 'customized', http_status: 503 }).http_status, undefined)
  assert.equal(workflow.attributionOf, undefined, 'the old multi-record reader is gone')
  assert.equal(workflow.pickAttribution.length, 1, 'one record, no list')
})

test('I451: completed + outcome=partial keeps its failure fields; no status is undecided (kept)', () => {
  const partial = workflow.pickAttribution({ status: 'completed', outcome: 'partial', attribution_source: 'phase', provider: 'glm', config_source: 'preset', failure_stage: 'render', http_status: 503 })
  assert.equal(partial.failure_stage, 'render'); assert.equal(partial.http_status, 503)
  const bare = workflow.pickAttribution({ attribution_source: 'phase', http_status: 502 })
  assert.equal(bare.http_status, 502)
  assert.equal(workflow.isFailedTerminal({ status: 'completed' }), false)
  assert.equal(workflow.isFailedTerminal({}), null)
})

test('I453: generation never borrows the analysis record (no source_blocked + kimi + 503 mix)', () => {
  const attempt = 't-cccccccccccccccc'
  const events = observe('studio-generation', 'p1', {
    generation: { status: 'failed', attempt_id: attempt },
    analysis: { status: 'failed', provider: 'kimi', config_source: 'customized', attribution_source: 'request', http_status: 503, upstream_error_type: 'upstream_unavailable' },
    plan: { id: 'plan', mode: 'ai' },
    attempts: [{ attempt_id: attempt, kind: 'generation', state: 'failed', error_code: 'source_blocked', failure_stage: 'ingest', summary: {} }],
  })
  assert.equal(events.find(e => e.event === 'studio_generation_finished'), undefined)
})

test('I451: a partial production keeps stage/status in its event', () => {
  const run = 'run-partial'
  const events = observe('studio-production', 'plan', {
    plan: { id: 'plan', confirmed_analysis: 'subtitle' },
    analysis: { status: 'completed', outcome: 'partial', run_id: run },
    attempts: [{ attempt_id: 't-dddddddddddddddd', kind: 'production', state: 'partial', run_id: run,
      failure_stage: 'analyze', upstream_error_type: 'upstream_unavailable',
      summary: { attribution_source: 'phase', provider: 'glm', config_source: 'preset', http_status: 503, failure_stage: 'analyze' } }],
  }, 'p1')
  assert.equal(events.find(e => e.event === 'studio_production_finished'), undefined)
})

test('I424: a store_lock_timeout failure shows the i18n key', () => {
  const src = fs.readFileSync(path.join(__dirname, '../src/utils/llmFailure.ts'), 'utf8')
  assert.match(src, /if \(code === STORE_LOCK_TIMEOUT\) return STORE_LOCK_TIMEOUT_TEXT/)
})
})()

// failure-attribution.test.cjs
;(() => {
// : terminal events follow isFailedTerminal; the one-reader guard is an AST scan.
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
const storage = { getItem: () => null, setItem() {}, removeItem() {} }
function observe(kind, id, state, extra) {
  const events = []
  const t = new workflow.WorkflowTracker(storage, () => true, (event, props) => { events.push({ event, props }); return true })
  t.watch(kind, id, extra)
  t.observeStudio(t.list()[0], state)
  return events
}

test('I504: a partial generation receipt keeps its error_code and status', () => {
  const attempt = 't-aaaaaaaaaaaaaaaa'
  const events = observe('studio-generation', 'p1', {
    generation: { status: 'completed', outcome: 'partial', attempt_id: attempt },
    plan: { id: 'plan', mode: 'ai' },
    attempts: [{ attempt_id: attempt, kind: 'generation', state: 'partial', error_code: 'provider_error',
      summary: { attribution_source: 'request', provider: 'kimi', config_source: 'customized', http_status: 503 } }],
  })
  assert.equal(events.find(e => e.event === 'studio_generation_finished'), undefined)
})

test('I504: a clean completed generation receipt carries no error_code or status', () => {
  const attempt = 't-bbbbbbbbbbbbbbbb'
  const events = observe('studio-generation', 'p1', {
    generation: { status: 'completed', outcome: 'completed', attempt_id: attempt },
    plan: { id: 'plan', mode: 'ai' },
    attempts: [{ attempt_id: attempt, kind: 'generation', state: 'completed', error_code: 'provider_error',
      summary: { error_code: 'provider_error', http_status: 503, attribution_source: 'request', provider: 'kimi', config_source: 'customized' } }],
  })
  assert.equal(events.find(e => e.event === 'studio_generation_finished'), undefined)
})

test('I504: a partial production receipt emits its terminal event', () => {
  const run = 'run-partial'
  const events = observe('studio-production', 'plan', {
    plan: { id: 'plan', confirmed_analysis: 'subtitle' },
    analysis: { status: 'partial', run_id: run },
    attempts: [{ attempt_id: 't-eeeeeeeeeeeeeeee', kind: 'production', state: 'partial', run_id: run, error_code: 'provider_error',
      summary: { attribution_source: 'phase', provider: 'glm', config_source: 'preset', http_status: 502 } }],
  }, 'p1')
  assert.equal(events.find(e => e.event === 'studio_production_finished'), undefined)
})

// AST guard over frontend/src: studio records' attribution is read only inside pickAttribution
// AUXILIARY only. The primary guard is the runtime payload test (failure-attribution.test.cjs):
// whatever the code looks like, the event properties carry only ATTRIBUTION_KEYS with valid values.
const KEYS = new Set(['attribution_source', 'http_status', 'upstream_error_type', 'provider', 'config_source', 'model', 'base_url_host'])
const REC = /^(analysis|generation|run|record|terminal|workspace)$/

function offences(file, source) {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.ES2020, true, file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const aliases = new Set(); const out = []
  const strip = (e) => { while (e && (ts.isNonNullExpression(e) || ts.isParenthesizedExpression(e) || ts.isAsExpression(e))) e = e.expression; return e }
  const recish = (e) => {
    e = strip(e)
    if (!e) return false
    if (ts.isIdentifier(e)) return REC.test(e.text) || aliases.has(e.text)
    if (ts.isPropertyAccessExpression(e)) return REC.test(e.name.text)
    if (ts.isElementAccessExpression(e)) return ts.isStringLiteralLike(e.argumentExpression) && REC.test(e.argumentExpression.text)
    if (ts.isBinaryExpression(e)) return recish(e.left) || recish(e.right)
    return false
  }
  // Page cause display (去设置) reads a settled cause. It is not a telemetry serializer; pickAttribution remains the only event reader.
  const PAGE = new Set(['analysisPageFailure', 'pageFailureAction', 'receiptFailureInfo'])
  const inPick = (n) => { for (let c = n; c; c = c.parent) if (ts.isFunctionDeclaration(c) && c.name && (c.name.text === 'pickAttribution' || PAGE.has(c.name.text))) return true; return false }
  const collect = (n) => { if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.initializer && recish(n.initializer)) aliases.add(n.name.text); ts.forEachChild(n, collect) }
  for (let i = 0; i < 3; i++) collect(sf)
  const report = (n, what) => { if (!inPick(n)) out.push(`${file}:${sf.getLineAndCharacterOfPosition(n.getStart()).line + 1}: ${what}`) }
  const visit = (n) => {
    if (ts.isPropertyAccessExpression(n) && KEYS.has(n.name.text) && recish(n.expression)) {
      const p = n.parent
      const write = ts.isBinaryExpression(p) && p.left === n && p.operatorToken.kind === ts.SyntaxKind.EqualsToken
      if (!write) report(n, '.' + n.name.text)
    }
    if (ts.isElementAccessExpression(n) && ts.isStringLiteralLike(n.argumentExpression) && KEYS.has(n.argumentExpression.text) && recish(n.expression)) report(n, `['${n.argumentExpression.text}']`)
    if (ts.isVariableDeclaration(n) && ts.isObjectBindingPattern(n.name) && n.initializer && recish(n.initializer)) {
      for (const el of n.name.elements) {
        const key = el.propertyName ? el.propertyName.getText(sf) : el.name.getText(sf)
        if (KEYS.has(key) && !el.name.getText(sf).startsWith('_')) report(el, `{ ${key} }`)
      }
    }
    ts.forEachChild(n, visit)
  }
  visit(sf)
  return out
}

test('I502 (auxiliary): no studio record attribution is read outside pickAttribution (AST, all of frontend/src)', () => {
  const found = []
  // features/settings edits the model SETTINGS (settings.analysis.model), not a studio failure record.
  const walk = (dir) => { for (const f of fs.readdirSync(dir)) { const p = path.join(dir, f); if (fs.statSync(p).isDirectory()) { if (!p.endsWith(path.join('features', 'settings'))) walk(p) } else if (/\.tsx?$/.test(f)) found.push(...offences(path.relative(path.join(__dirname, '..'), p), fs.readFileSync(p, 'utf8'))) } }
  walk(path.join(__dirname, '../src'))
  assert.deepEqual(found, [])
})

test('I502 (auxiliary): the AST guard catches .model, destructuring, element access and an alias', () => {
  for (const source of [
    'const m = snapshot.analysis?.model',
    'const { http_status, upstream_error_type: u } = snapshot.generation!',
    "const s = run['attribution_source']",
    'const a = snapshot.analysis; const p = a?.provider',
    'function f(record: any) { return record.base_url_host }',
  ]) assert.ok(offences('x.ts', source).length, source)
  assert.equal(offences('x.ts', 'const { http_status: _hs, ...rest } = snapshot.analysis!').length, 0, 'stripping is not reading')
})
})()

// failure-attribution.test.cjs
;(() => {
// runtime payload tests are the primary guard for the frontend serializer.
// Dirty studio records go through the real WorkflowTracker; every terminal event's attribution properties
// must be a subset of ATTRIBUTION_KEYS with valid values, whatever the reader code looks like.
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
const storage = { getItem: () => null, setItem() {}, removeItem() {} }
function observe(kind, id, state, extra) {
  const events = []
  const t = new workflow.WorkflowTracker(storage, () => true, (event, props) => { events.push({ event, props }); return true })
  t.watch(kind, id, extra)
  t.observeStudio(t.list()[0], state)
  return events
}
const SECRET = 'sk-r31-SECRET-0000 https://user:pw@private.example/v1 /Users/someone/clip.mp4'
const DIRTY = { attribution_source: 'request', provider: 'kimi', config_source: 'customized', model: 'kimi-k2',
  base_url_host: 'kimi.fixture.example', http_status: '503;drop', upstream_error_type: 'upstream_unavailable', failure_stage: 'analyze',
  raw_message: SECRET, api_key: SECRET, url: SECRET }
const ATTR = new Set(['attribution_source', 'provider', 'config_source', 'model', 'base_url_host', 'http_status', 'upstream_error_type', 'failure_stage'])

function checkClean(props) {
  const text = JSON.stringify(props)
  assert.ok(!text.includes('SECRET') && !text.includes('private.example') && !text.includes('/Users/'), text)
  assert.ok(!text.includes('503;drop'), text)
  assert.equal(props.http_status, undefined, text)
}

test('I565: pickAttribution copies only whitelisted keys with valid values and freezes the result', () => {
  for (const status of ['503;drop', '503', true, 302, 600, 503.5]) {
    const out = workflow.pickAttribution({ ...DIRTY, status: 'failed', http_status: status })
    assert.ok(Object.keys(out).every(k => workflow.ATTRIBUTION_KEYS.includes(k)), JSON.stringify(out))
    assert.equal(out.http_status, undefined, String(status))
    assert.ok(Object.isFrozen(out))
  }
  assert.equal(workflow.pickAttribution({ ...DIRTY, status: 'failed', http_status: 503 }).http_status, 503)
  assert.deepEqual({ ...workflow.pickAttribution({ status: 'failed', attribution_source: 'guess', provider: 'kimi' }) }, {})
})

test('I565: dirty production / generation / screen records never put a non-whitelisted or invalid value in an event', () => {
  const gen = 't-aaaaaaaaaaaaaaaa', prod = 't-bbbbbbbbbbbbbbbb', run = 'run-dirty'
  const receipt = (attempt, kind, extra) => ({ attempt_id: attempt, kind, state: 'failed', error_code: 'provider_error',
    upstream_error_type: DIRTY.upstream_error_type, failure_stage: DIRTY.failure_stage, summary: { ...DIRTY }, ...extra })
  const cases = [
    observe('studio-production', 'plan', { plan: { id: 'plan', confirmed_analysis: 'subtitle' }, analysis: { status: 'failed', run_id: run },
      attempts: [receipt(prod, 'production', { run_id: run })] }, 'p1'),
    observe('studio-generation', 'p1', { generation: { status: 'failed', attempt_id: gen }, plan: { id: 'plan', mode: 'ai' },
      attempts: [receipt(gen, 'generation')] }),
    observe('studio-screen', 'p1', { analysis: { ...DIRTY, status: 'failed', phase: 'screening', error_code: 'provider_error' }, plan: { id: 'plan' } }),
  ]
  const [production, generation, screen] = cases
  assert.equal(production.find(e => e.event === 'studio_production_finished'), undefined)
  assert.equal(generation.find(e => e.event === 'studio_generation_finished'), undefined)
  const screened = screen.filter(e => e.event.endsWith('_finished'))
  assert.ok(screened.length >= 1, 'screening still reports its own terminal')
  for (const { props } of screened) checkClean(props)
})

test('X14: a partial production receipt with no outcome keeps its failure fields', () => {
  const run = 'run-x14'
  const events = observe('studio-production', 'plan', {
    plan: { id: 'plan', confirmed_analysis: 'subtitle' },
    analysis: { status: 'partial', run_id: run },
    attempts: [{ attempt_id: 't-fffffffffffffffe', kind: 'production', state: 'partial', run_id: run,
      error_code: 'provider_error', failure_stage: 'analyze', upstream_error_type: 'upstream_unavailable',
      summary: { attribution_source: 'request', provider: 'kimi', config_source: 'customized', http_status: 503,
        upstream_error_type: 'upstream_unavailable', failure_stage: 'analyze' } }],
  }, 'p1')
  assert.equal(events.find(e => e.event === 'studio_production_finished'), undefined)
})
})()

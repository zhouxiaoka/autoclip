// R29 #415 (Dong R28 I502, I504): terminal events follow isFailedTerminal; the one-reader guard is an AST scan.
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
  const done = events.find(e => e.event === 'studio_generation_finished')
  assert.ok(done, JSON.stringify(events))
  assert.equal(done.props.outcome, 'partial')
  assert.equal(done.props.error_code, 'provider_error')
  assert.equal(done.props.http_status, 503)
})

test('I504: a clean completed generation receipt carries no error_code or status', () => {
  const attempt = 't-bbbbbbbbbbbbbbbb'
  const props = observe('studio-generation', 'p1', {
    generation: { status: 'completed', outcome: 'completed', attempt_id: attempt },
    plan: { id: 'plan', mode: 'ai' },
    attempts: [{ attempt_id: attempt, kind: 'generation', state: 'completed', error_code: 'provider_error',
      summary: { error_code: 'provider_error', http_status: 503, attribution_source: 'request', provider: 'kimi', config_source: 'customized' } }],
  }).find(e => e.event === 'studio_generation_finished').props
  assert.equal(props.outcome, 'success')
  assert.equal(props.error_code, undefined)
  assert.equal(props.http_status, undefined)
})

test('I504: a partial production receipt emits its terminal event', () => {
  const run = 'run-partial'
  const events = observe('studio-production', 'plan', {
    plan: { id: 'plan', confirmed_analysis: 'subtitle' },
    analysis: { status: 'partial', run_id: run },
    attempts: [{ attempt_id: 't-eeeeeeeeeeeeeeee', kind: 'production', state: 'partial', run_id: run, error_code: 'provider_error',
      summary: { attribution_source: 'phase', provider: 'glm', config_source: 'preset', http_status: 502 } }],
  }, 'p1')
  const done = events.find(e => e.event === 'studio_production_finished')
  assert.ok(done, JSON.stringify(events))
  assert.equal(done.props.outcome, 'partial')
  assert.equal(done.props.error_code, 'provider_error')
  assert.equal(done.props.http_status, 502)
})

// --- I502: AST guard over frontend/src: studio records' attribution is read only inside pickAttribution ---
// R31 (Dong I565): AUXILIARY only. The primary guard is the runtime payload test (r31-415-payload.test.cjs):
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

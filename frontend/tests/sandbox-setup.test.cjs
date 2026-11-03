// Guards for tests/setup.cjs. Every case runs a probe test file in a fresh `node --require setup --test`
// process, exactly like `npm test`, so none of them depends on how this file itself was started (#274).
const { test } = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const SETUP = path.join(__dirname, 'setup.cjs')
function runWithSetup(body, { setup = true, env = {} } = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ac-setup-'))
  const file = path.join(dir, 'probe.test.cjs')
  fs.writeFileSync(file, `const { test, after } = require('node:test')\nconst vm = require('node:vm')\n${body}\n`)
  const clean = Object.fromEntries(Object.entries(process.env).filter(([k]) => k !== 'NODE_TEST_CONTEXT' && k !== 'NODE_OPTIONS' && k !== 'AC_STRICT_SETUP_OWNER'))
  const result = spawnSync(process.execPath, [...(setup ? ['--require', SETUP] : []), '--test', file], { encoding: 'utf8', cwd: __dirname, env: { ...clean, ...env } })
  fs.rmSync(dir, { recursive: true, force: true })
  return result
}
function failsOnlyWithSetup(body, pattern) {
  assert.equal(runWithSetup(body, { setup: false }).status, 0, 'without the setup this is a false pass')
  const r = runWithSetup(body)
  assert.notEqual(r.status, 0, r.stdout + r.stderr)
  if (pattern) assert.match(r.stdout + r.stderr, pattern)
}

test('a sandbox that forgot URL / URLSearchParams still gets them; explicit values win', () => {
  const r = runWithSetup(`test('probe', () => {
  const ok = vm.runInNewContext('(() => { try { return !!new URL("https://a.b") && !!new URLSearchParams("a=1") } catch { return false } })()', {})
  if (!ok) throw new Error('URL missing')
  if (vm.runInNewContext('URL', { URL: 'mine' }) !== 'mine') throw new Error('explicit URL lost')
})`)
  assert.equal(r.status, 0, r.stdout + r.stderr)
})

test('#272 timers, AbortController, Blob and DOM types are not leaked into sandboxes', () => {
  const r = runWithSetup(`test('probe', () => {
  const seen = vm.runInNewContext('[typeof setTimeout, typeof clearTimeout, typeof AbortController, typeof Blob, typeof HTMLElement, typeof window].join()', {})
  if (seen !== 'undefined,undefined,undefined,undefined,undefined,undefined') throw new Error('leaked: ' + seen)
})`)
  assert.equal(r.status, 0, r.stdout + r.stderr)
})

test('#234 console.error during a test fails it (passed silently before)', () => {
  failsOnlyWithSetup(`test('probe', () => { console.error('Warning: something React swallowed') })`, /swallowed error\(s\) during the test/)
})

test('Node runtime warnings printed through console.error are not application errors', () => {
  const hint = '(Use `node --trace-warnings ...` to show where the warning was created)'
  const r = runWithSetup(`test('probe', () => {
  console.error('(node:1) ExperimentalWarning: The MockTimers API is an experimental feature')
  console.error('(node:1) MaxListenersExceededWarning: Possible EventTarget memory leak detected. 11 abort listeners added to [AbortSignal]. MaxListeners is 10.')
  console.error(${JSON.stringify(hint)})
})`)
  assert.equal(r.status, 0, r.stdout + r.stderr)
  failsOnlyWithSetup(`test('probe', () => { console.error('ExperimentalWarning: boom') })`, /ExperimentalWarning: boom/)
})

test('#270 console.error at module top level fails the file', () => {
  failsOnlyWithSetup(`console.error('top level')\ntest('probe', () => {})`, /top level/)
  failsOnlyWithSetup(`console.error('top level, no tests')`, /top level, no tests/)
})

test('#270 console.error after the last test fails the file', () => {
  failsOnlyWithSetup(`test('probe', () => { setImmediate(() => console.error('late')) })`, /late/)
  failsOnlyWithSetup(`test('probe', () => {})\nafter(() => console.error('in after hook'))`, /in after hook/)
})

test('#275 AC_SANDBOX_LENIENT no longer turns the check off', () => {
  for (const value of ['1', '0']) {
    const r = runWithSetup(`test('probe', () => { console.error('x') })`, { env: { AC_SANDBOX_LENIENT: value } })
    assert.notEqual(r.status, 0, `AC_SANDBOX_LENIENT=${value}`)
  }
})

test('#276 only the test-file process registers hooks: one summary, no empty "tests 0" run', () => {
  const r = runWithSetup(`test('probe', () => {})`, { env: { NODE_OPTIONS: '' } })
  assert.equal(r.status, 0, r.stdout + r.stderr)
  assert.equal((r.stdout.match(/^# tests /mg) || []).length, 1, r.stdout)
  assert.equal((r.stdout.match(/<\?xml|^TAP version/mg) || []).length, 1, r.stdout)
})

test('#234 an unhandled rejection during a test fails it', () => {
  const r = runWithSetup(`test('probe', async () => { Promise.reject(new Error('lost')); await new Promise(r => setImmediate(r)) })`)
  assert.notEqual(r.status, 0)
})

test('#299 console.error inside a module loaded through loadTs fails the test (passed silently before)', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ac-loadts-'))
  const mod = path.join(dir, 'noisy.ts')
  fs.writeFileSync(mod, "export function run(): number { console.error('handler failed: boom'); return 1 }\n")
  try {
    failsOnlyWithSetup(`const { loadTs } = require(${JSON.stringify(path.join(__dirname, 'load-ts.cjs'))})
test('probe', () => { if (loadTs(${JSON.stringify(mod)}).run() !== 1) throw new Error('not loaded') })`, /handler failed: boom/)
  } finally { fs.rmSync(dir, { recursive: true, force: true }) }
})

test('#300 console.error in an exit listener the test file registers later still fails the file', () => {
  failsOnlyWithSetup(`test('probe', () => {})\nprocess.on('exit', () => console.error('in a late exit listener'))`, /in a late exit listener/)
})

test('#302 a child forked by a test file is not hooked again: no second "tests" summary', () => {
  const r = runWithSetup(`const fs = require('node:fs'); const path = require('node:path'); const os = require('node:os')
const { fork } = require('node:child_process')
test('probe', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ac-fork-'))
  const child = path.join(dir, 'worker.test.cjs')
  fs.writeFileSync(child, "process.stdout.write(process.env.AC_STRICT_SETUP_OWNER === String(process.pid) ? 'CHILD:HOOKED' : 'CHILD:CLEAN')")
  const out = await new Promise((resolve, reject) => {
    const cp = fork(child, { silent: true }); let text = ''
    cp.stdout.on('data', d => { text += d }); cp.on('error', reject); cp.on('exit', () => resolve(text))
  })
  fs.rmSync(dir, { recursive: true, force: true })
  if (out !== 'CHILD:CLEAN') throw new Error('forked child was hooked: ' + JSON.stringify(out))
})`)
  assert.equal(r.status, 0, r.stdout + r.stderr)
})

test('#329 a child forked with a "--test" script argument is still not hooked again', () => {
  const r = runWithSetup(`const fs = require('node:fs'); const path = require('node:path'); const os = require('node:os')
const { fork } = require('node:child_process')
test('probe', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ac-fork-arg-'))
  const child = path.join(dir, 'worker.test.cjs')
  fs.writeFileSync(child, "process.stdout.write(process.env.AC_STRICT_SETUP_OWNER === String(process.pid) ? 'CHILD:HOOKED' : 'CHILD:CLEAN')")
  const out = await new Promise((resolve, reject) => {
    const cp = fork(child, ['--test'], { silent: true }); let text = ''
    cp.stdout.on('data', d => { text += d }); cp.on('error', reject); cp.on('exit', () => resolve(text))
  })
  fs.rmSync(dir, { recursive: true, force: true })
  if (out !== 'CHILD:CLEAN') throw new Error('a "--test" script argument re-hooked the child: ' + JSON.stringify(out))
})`)
  assert.equal(r.status, 0, r.stdout + r.stderr)
})

test('#313 console.error inside code run through the shared vm helper fails the test, own console or not', () => {
  const helper = JSON.stringify(path.join(__dirname, 'vm-sandbox.cjs'))
  failsOnlyWithSetup(`const { runInSandbox } = require(${helper})
test('probe', () => { runInSandbox("console.error('loader swallowed: boom')", {}) })`, /loader swallowed: boom/)
  failsOnlyWithSetup(`const { runInSandbox } = require(${helper})
test('probe', () => { runInSandbox("console.log('x'); console.error('own console: boom')", { console: { log() {} } }) })`, /own console: boom/)
})

test('#315 a new runner started by a test file hooks its own test files again', () => {
  const r = runWithSetup(`const fs = require('node:fs'); const path = require('node:path'); const os = require('node:os')
const { spawnSync } = require('node:child_process')
test('probe', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ac-runner-'))
  const inner = path.join(dir, 'inner.test.cjs')
  fs.writeFileSync(inner, "require('node:test').test('inner', () => { console.error('inner swallowed') })")
  const env = { ...process.env }; delete env.NODE_TEST_CONTEXT
  const out = spawnSync(process.execPath, ['--require', ${JSON.stringify(SETUP)}, '--test', inner], { encoding: 'utf8', env })
  fs.rmSync(dir, { recursive: true, force: true })
  if (out.status === 0) throw new Error('inner runner lost the strict setup: ' + out.stdout)
})`)
  assert.equal(r.status, 0, r.stdout + r.stderr)
})

// happy-dom arrives with #418, which merges before this PR (agreed order #418 -> #422).
let happy = null
try { happy = require.resolve('happy-dom') } catch { /* not installed on this branch */ }
const HAPPY = JSON.stringify(happy)
const throwingClick = `const el = win.document.createElement('div'); el.addEventListener('click', () => { throw new ReferenceError('HTMLElement is not defined') }); el.click()`
test('#234 an exception inside a happy-dom listener on globalThis.window fails the test', { skip: !happy && 'happy-dom comes with #418' }, () => {
  failsOnlyWithSetup(`const { Window } = require(${HAPPY}); globalThis.window = new Window()
test('probe', () => { const win = window; ${throwingClick} })`, /happy-dom event handler/)
})
test('#271 a window created inside the test body, or at module top level, is covered too', { skip: !happy && 'happy-dom comes with #418' }, () => {
  failsOnlyWithSetup(`const { Window } = require(${HAPPY})
test('probe', () => { const win = new Window(); ${throwingClick} })`, /happy-dom event handler/)
  failsOnlyWithSetup(`const { Window } = require(${HAPPY}); const win = new Window({ url: 'http://localhost/' })
test('probe', () => { ${throwingClick} })`, /happy-dom event handler/)
})
test('#301 a window from a native import() of happy-dom is covered too', { skip: !happy && 'happy-dom comes with #418' }, () => {
  const url = JSON.stringify(happy && require('node:url').pathToFileURL(happy).href)
  failsOnlyWithSetup(`test('probe', async () => { const { Window } = await import(${url}); const win = new Window(); ${throwingClick} })`, /happy-dom event handler/)
})
test('#314 a native import() of happy-dom with a ?query is covered too', { skip: !happy && 'happy-dom comes with #418' }, () => {
  const url = JSON.stringify(happy && require('node:url').pathToFileURL(happy).href + '?x=1')
  failsOnlyWithSetup(`test('probe', async () => { const { Window } = await import(${url}); const win = new Window(); ${throwingClick} })`, /happy-dom event handler/)
})

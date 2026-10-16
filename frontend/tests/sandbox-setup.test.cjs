// Guards for tests/setup.cjs: sandboxes get the standard globals, explicit values win, and errors that
// product code or happy-dom would swallow fail the test instead of passing silently.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const vm = require('node:vm')

const SETUP = path.join(__dirname, 'setup.cjs')
function runWithSetup(body, withSetup = true) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ac-setup-'))
  const file = path.join(dir, 'probe.test.cjs')
  fs.writeFileSync(file, `const { test } = require('node:test')\n${body}\n`)
  const result = spawnSync(process.execPath, [...(withSetup ? ['--require', SETUP] : []), '--test', file], { encoding: 'utf8', cwd: __dirname, env: Object.fromEntries(Object.entries(process.env).filter(([k]) => k !== 'NODE_TEST_CONTEXT' && k !== 'NODE_OPTIONS')) })
  fs.rmSync(dir, { recursive: true, force: true })
  return result
}

test('a sandbox that forgot URL / timers still gets them; explicit values win', { skip: !vm.runInNewContext.toString().includes('fill') && 'run through npm test' }, () => {
  assert.equal(vm.runInNewContext('typeof URL + typeof setTimeout + typeof AbortController', {}), 'functionfunctionfunction')
  assert.equal(vm.runInNewContext('URL', { URL: 'mine' }), 'mine')
  assert.equal(vm.runInNewContext('typeof window', {}), 'undefined', 'window stays the test\'s decision')
})

test('a feature-detected global swallowed by try/catch is now reachable', () => {
  const r = runWithSetup(`const vm = require('node:vm')
test('probe', () => { const ok = vm.runInNewContext('(() => { try { return !!new URL("https://a.b") } catch { return false } })()', {}); if (!ok) throw new Error('URL missing') })`)
  assert.equal(r.status, 0, r.stdout + r.stderr)
})

test('#234 console.error during a test fails it (passed silently before)', () => {
  const body = `test('probe', () => { console.error('Warning: something React swallowed') })`
  assert.equal(runWithSetup(body, false).status, 0, 'without the setup this is a false pass')
  const r = runWithSetup(body)
  assert.notEqual(r.status, 0)
  assert.match(r.stdout, /swallowed error\(s\) during the test/)
})

test('#234 an unhandled rejection during a test fails it', () => {
  const r = runWithSetup(`test('probe', async () => { Promise.reject(new Error('lost')); await new Promise(r => setImmediate(r)) })`)
  assert.notEqual(r.status, 0)
})

let happy = null
try { happy = require.resolve('happy-dom') } catch { /* not installed on this branch */ }
test('#234 an exception inside a happy-dom event listener fails the test (happy-dom swallows it otherwise)', { skip: !happy && 'happy-dom not installed on this branch' }, () => {
  const body = `const { Window } = require(${JSON.stringify(happy)}); globalThis.window = new Window()
test('probe', () => { const el = window.document.createElement('div'); el.addEventListener('click', () => { throw new ReferenceError('HTMLElement is not defined') }); el.click() })`
  assert.equal(runWithSetup(body, false).status, 0, 'without the setup happy-dom swallows the throw: false pass')
  const r = runWithSetup(`const { Window } = require(${JSON.stringify(happy)}); globalThis.window = new Window()
test('probe', () => { const el = window.document.createElement('div'); el.addEventListener('click', () => { throw new ReferenceError('HTMLElement is not defined') }); el.click() })`)
  assert.notEqual(r.status, 0)
  assert.match(r.stdout, /DOM event handler|window\.console\.error/)
})

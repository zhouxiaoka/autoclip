// Shared strict test setup, loaded by `npm test` and the redline gate via `node --require ./tests/setup.cjs --test`.
// It only activates inside the per-file test processes the runner spawns, never in the parent runner
// or in processes a test spawns (#276).
//
// 1. Swallowed errors fail the run: console.error, an exception inside a happy-dom event listener and an
//    unhandled rejection. A problem is never cleared without being reported (#270): one recorded at module
//    top level, between tests or in a test's own window fails the next test, and anything left after the
//    last test fails the file at exit. There is no opt-out (#275).
//    A problem recorded after the exit check already ran (an exit listener the test file registered later)
//    still sets a non-zero exit code (#300).
// 2. Every happy-dom window is covered, whenever and wherever the test creates it (#271), whether the test
//    loads happy-dom with require() or with a native import() (#301).
// 3. vm sandboxes only get URL / URLSearchParams when they forgot them (#209). Timers, AbortController and
//    DOM types are the test's own decision and must be passed explicitly (#272). Loaders hand their
//    sandbox the monitored console explicitly (tests/load-ts.cjs, #299).
// 4. A process forked or spawned by a test file (it inherits --require and NODE_TEST_CONTEXT) is not
//    hooked again (#302).
'use strict'
const OWNER = 'AC_STRICT_SETUP_OWNER'
// #315: the owner marker is bound to one runner session. A new `node --test` runner (with this setup) is a fresh
// session: it drops an inherited marker so its own test files are hooked again.
if (process.execArgv.includes('--test')) delete process.env[OWNER]  // #329: the runner flag only, never a script argument
if (process.env.NODE_TEST_CONTEXT && /\.test\.c?js$/.test(process.argv[1] || '') && !process.env[OWNER]
    && require('node:worker_threads').isMainThread) {
  process.env[OWNER] = String(process.pid)  // inherited by every child of this test file (#302)
  const vm = require('node:vm')
  const util = require('node:util')
  const Module = require('node:module')

  // ---- vm sandboxes: only the two URL globals
  const FILLED = ['URL', 'URLSearchParams']
  function fill(context) {
    if (!context || typeof context !== 'object' || vm.isContext(context) || context.happyDOM) return context
    for (const name of FILLED) if (!Object.prototype.hasOwnProperty.call(context, name)) context[name] = globalThis[name]
    return context
  }
  const runInNewContext = vm.runInNewContext
  vm.runInNewContext = function (code, context, ...rest) { return runInNewContext.call(this, code, fill(context ?? {}), ...rest) }
  const createContext = vm.createContext
  vm.createContext = function (context, ...rest) { return createContext.call(this, fill(context ?? {}), ...rest) }

  // ---- strict errors
  const problems = []
  let exitChecked = false
  function record(message) {
    if (!exitChecked) { problems.push(message); return }
    // #300: the exit check already ran; a later exit listener must not end the file with code 0
    process.stderr.write('swallowed error(s) outside any test:\n' + message + '\n')
    process.exitCode = 1
  }
  const realError = console.error.bind(console)
  // Node's own warning printer uses console.error. Those lines are not application errors:
  // CI's Node 20 prints MaxListenersExceededWarning and the MockTimers ExperimentalWarning this way.
  console.error = (...args) => {
    const text = util.format(...args)
    if (/\(node:\d+\) (?:MaxListenersExceededWarning|ExperimentalWarning):/.test(text)
        || text.includes('Use `node --trace-warnings')) {
      realError(...args)
      return
    }
    record('console.error: ' + text)
    realError(...args)
  }
  process.on('unhandledRejection', reason => { record('unhandled rejection: ' + util.inspect(reason)) })

  // happy-dom routes every listener / timer exception of every window through
  // BrowserWindow#[dispatchError], so patching it once covers windows created anywhere (#271).
  const patched = new WeakSet()
  function patchHappyDom(exports) {
    const proto = exports && exports.BrowserWindow && exports.BrowserWindow.prototype
    const key = exports && exports.PropertySymbol && exports.PropertySymbol.dispatchError
    if (!proto || typeof key !== 'symbol' || patched.has(proto)) return
    patched.add(proto)
    const original = proto[key]
    proto[key] = function (error) {
      record('error in a happy-dom event handler: ' + util.inspect(error))
      return original.call(this, error)
    }
  }
  const load = Module._load
  Module._load = function (request, parent, ...rest) {
    const exports = load.call(this, request, parent, ...rest)
    if (request === 'happy-dom' || /[\\/]happy-dom[\\/]lib[\\/]index\.js$/.test(request)) patchHappyDom(exports)
    return exports
  }
  // #301: native import() bypasses Module._load. The loader hook appends a call to this function to
  // happy-dom's ESM entry, so the window class is patched before the importing test sees it.
  globalThis[Symbol.for('autoclip.test.happyDomLoaded')] = patchHappyDom
  require('node:module').register(require('node:url').pathToFileURL(require('node:path').join(__dirname, 'setup-hooks.mjs')))

  function take() { return problems.splice(0) }
  const nodeTest = require('node:test')
  nodeTest.beforeEach(t => {
    const found = take()  // recorded before this test (module top level, previous test's late callbacks)
    if (found.length) throw new Error('swallowed error(s) before the test ' + JSON.stringify(t.name) + ':\n' + found.join('\n'))
  })
  nodeTest.afterEach(() => {
    const found = take()
    if (found.length) throw new Error('swallowed error(s) during the test:\n' + found.join('\n'))
  })
  process.on('exit', () => {
    exitChecked = true
    const found = take()
    if (!found.length) return
    process.stderr.write('swallowed error(s) outside any test:\n' + found.join('\n') + '\n')
    process.exitCode = 1
  })
}

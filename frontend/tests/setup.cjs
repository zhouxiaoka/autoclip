// Shared strict test setup, loaded by `npm test` and the redline gate via `node --require ./tests/setup.cjs --test`.
// It only activates inside the per-file test processes the runner spawns, never in the parent runner
// or in processes a test spawns (#276).
//
// 1. Swallowed errors fail the run: console.error, an exception inside a happy-dom event listener and an
//    unhandled rejection. A problem is never cleared without being reported (#270): one recorded at module
//    top level, between tests or in a test's own window fails the next test, and anything left after the
//    last test fails the file at exit. There is no opt-out (#275).
// 2. Every happy-dom window is covered, whenever and wherever the test creates it (#271).
// 3. vm sandboxes only get URL / URLSearchParams when they forgot them (#209). Timers, AbortController and
//    DOM types are the test's own decision and must be passed explicitly (#272).
'use strict'
if (process.env.NODE_TEST_CONTEXT && /\.test\.c?js$/.test(process.argv[1] || '')) {
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
  const realError = console.error.bind(console)
  console.error = (...args) => { problems.push('console.error: ' + util.format(...args)); realError(...args) }
  process.on('unhandledRejection', reason => { problems.push('unhandled rejection: ' + util.inspect(reason)) })

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
      problems.push('error in a happy-dom event handler: ' + util.inspect(error))
      return original.call(this, error)
    }
  }
  const load = Module._load
  Module._load = function (request, parent, ...rest) {
    const exports = load.call(this, request, parent, ...rest)
    if (request === 'happy-dom' || /[\\/]happy-dom[\\/]lib[\\/]index\.js$/.test(request)) patchHappyDom(exports)
    return exports
  }

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
    const found = take()
    if (!found.length) return
    process.stderr.write('swallowed error(s) outside any test:\n' + found.join('\n') + '\n')
    process.exitCode = 1
  })
}

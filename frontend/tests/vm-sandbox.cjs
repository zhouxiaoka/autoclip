// The one way tests evaluate source in a vm sandbox (#313). Every loader goes through runInSandbox so a
// console.error inside the loaded module reaches the strict setup (tests/setup.cjs): the sandbox always gets the
// monitored global console. A test that passes its own console keeps its other methods, but error still goes to the
// monitored one. Nothing else is injected here (URL / URLSearchParams come from setup.cjs, #209/#272).
// tests/vm-sandbox.test.cjs fails when a test file calls node:vm directly instead.
'use strict'
const vm = require('node:vm')

function withMonitoredConsole(context) {
  const ctx = context ?? {}
  const own = ctx.console
  if (own === undefined || own === console) {
    ctx.console = console
  } else {
    const merged = Object.create(own)
    merged.error = (...args) => console.error(...args)
    ctx.console = merged
  }
  return ctx
}

function runInSandbox(code, context, options) {
  return vm.runInNewContext(code, withMonitoredConsole(context), options)
}

module.exports = { runInSandbox }

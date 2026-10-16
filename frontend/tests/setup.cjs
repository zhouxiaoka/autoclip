// Shared test setup (R22 follow-up): loaded by `npm test` via --require into every test process.
//
// 1. vm sandboxes get the standard globals a browser bundle can rely on (URL, HTMLElement, ...). A sandbox
//    that forgot one turned `new URL()` / `instanceof HTMLElement` into a ReferenceError, which product code
//    then swallowed in its own try/catch or event handler, so tests passed without the code under test
//    ever running (#209). Only missing names are filled; whatever a test passes explicitly wins.
//    `window` / `document` / `navigator` / storage are never added: tests decide on those themselves.
// 2. Errors that would otherwise vanish fail the test: console.error, an exception thrown inside a
//    happy-dom event listener (reported on the window), and unhandled rejections.
'use strict'
const vm = require('node:vm')
const util = require('node:util')
const fs = require('node:fs')

const JS_GLOBALS = ['URL', 'URLSearchParams', 'TextEncoder', 'TextDecoder', 'AbortController', 'AbortSignal', 'Blob',
  'structuredClone', 'queueMicrotask', 'setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'atob', 'btoa',
  'console', 'performance', 'Intl']
const DOM_GLOBALS = ['HTMLElement', 'Element', 'Node', 'Event', 'CustomEvent', 'EventTarget', 'KeyboardEvent', 'MouseEvent',
  'ClipboardEvent', 'DragEvent', 'File', 'FileList', 'FormData', 'DataTransfer', 'HTMLInputElement', 'HTMLTextAreaElement',
  'HTMLButtonElement', 'HTMLVideoElement', 'DOMParser', 'getComputedStyle', 'requestAnimationFrame', 'cancelAnimationFrame']

function source(name) {
  const win = globalThis.window
  if (DOM_GLOBALS.includes(name)) return win && win.happyDOM ? win[name] : undefined
  return globalThis[name]
}

const audit = process.env.AC_SANDBOX_AUDIT
function fill(context) {
  if (!context || typeof context !== 'object' || vm.isContext(context)) return context
  if (context.happyDOM || /node_modules[\\/]/.test(new Error().stack.split('\n').slice(3, 4).join(''))) return context  // libraries' own contexts (happy-dom's Window)
  for (const name of [...JS_GLOBALS, ...DOM_GLOBALS]) {
    if (Object.prototype.hasOwnProperty.call(context, name)) continue
    const value = source(name)
    if (value === undefined) continue
    if (!audit) { context[name] = value; continue }
    Object.defineProperty(context, name, { configurable: true, enumerable: false, get() {
      if (name !== 'console') fs.appendFileSync(audit, `${process.argv[1] || ''}\t${currentTest() || ''}\t${name}\n`)
      return value
    } })
  }
  return context
}
let testName = ''
function currentTest() { return testName }

const runInNewContext = vm.runInNewContext
vm.runInNewContext = function (code, context, ...rest) { return runInNewContext.call(this, code, fill(context ?? {}), ...rest) }
const createContext = vm.createContext
vm.createContext = function (context, ...rest) { return createContext.call(this, fill(context ?? {}), ...rest) }

// ---- 2. strict: swallowed errors fail the test
const problems = []
const realError = console.error.bind(console)
console.error = (...args) => { problems.push('console.error: ' + util.format(...args)); realError(...args) }
process.on('unhandledRejection', reason => { problems.push('unhandled rejection: ' + util.inspect(reason)) })

let hooked = null
function hookWindow() {
  const win = globalThis.window
  if (!win || !win.happyDOM || hooked === win) return
  hooked = win
  win.addEventListener('error', event => { problems.push('error in a DOM event handler: ' + util.inspect(event.error || event.message)) })
  // happy-dom logs listener exceptions through window.console
  if (win.console && win.console !== console) win.console.error = (...args) => { problems.push('window.console.error: ' + util.format(...args)) }
}

const nodeTest = require('node:test')
nodeTest.beforeEach(t => { testName = t.name; hookWindow(); problems.length = 0 })
nodeTest.afterEach(() => {
  hookWindow()
  if (process.env.AC_SANDBOX_LENIENT || !problems.length) { problems.length = 0; return }
  const found = problems.splice(0)
  throw new Error('swallowed error(s) during the test:\n' + found.join('\n'))
})

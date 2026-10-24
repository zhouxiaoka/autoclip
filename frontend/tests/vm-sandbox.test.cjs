// Guard for #313: every test evaluates source through tests/vm-sandbox.cjs, which hands the sandbox the monitored
// console. A loader that calls node:vm itself would silently drop console.error again.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const ALLOWED = new Set(['setup.cjs', 'vm-sandbox.cjs', 'sandbox-setup.test.cjs', 'vm-sandbox.test.cjs'])
const DIRECT = /\b(runInNewContext|runInContext|runInThisContext|createContext|compileFunction|SourceTextModule)\b|\bvm\.Script\b|new\s+Script\s*\(/

test('#313 no test file calls node:vm directly; all loaders use runInSandbox', () => {
  const offenders = []
  for (const name of fs.readdirSync(__dirname).filter(n => /\.c?js$|\.mjs$/.test(n)).sort()) {
    if (ALLOWED.has(name)) continue
    fs.readFileSync(path.join(__dirname, name), 'utf8').split('\n').forEach((line, i) => {
      if (DIRECT.test(line)) offenders.push(`${name}:${i + 1}: ${line.trim()}`)
    })
  }
  assert.deepEqual(offenders, [], 'use runInSandbox from tests/vm-sandbox.cjs')
})

test('#330 no test file keeps an unused node:vm import', () => {
  const unused = []
  for (const name of fs.readdirSync(__dirname).filter(n => /\.c?js$|\.mjs$/.test(n)).sort()) {
    if (ALLOWED.has(name)) continue
    const text = fs.readFileSync(path.join(__dirname, name), 'utf8')
    const bound = text.match(/\b(\w+)\s*=\s*require\(['"]node:vm['"]\)/)
    if (bound && !new RegExp(`\\b${bound[1]}\\.`).test(text)) unused.push(name)
  }
  assert.deepEqual(unused, [], 'drop the unused node:vm import')
})

test('#313 the helper hands the sandbox the monitored console', () => {
  const { runInSandbox } = require('./vm-sandbox.cjs')
  assert.equal(runInSandbox('console', {}), console)
  const own = { log() {} }
  const seen = runInSandbox('console', { console: own })
  assert.equal(seen.log, own.log)
  assert.notEqual(seen.error, undefined)
})

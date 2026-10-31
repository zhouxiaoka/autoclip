const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

test('#487 bindRestartRefresh pulls the list as soon as the shell signals ready', async () => {
  const { bindRestartRefresh } = loadTs(path.resolve(__dirname, '../src/hooks/useProjectPolling.ts'), {
    '../services/api': { projectApi: { getProjects: async () => [] } },
    '../store/useProjectStore': { useProjectStore: { getState: () => ({ isDragging: false }) } },
  })
  const listeners = new Set()
  const subscribe = (fn) => { listeners.add(fn); return () => listeners.delete(fn) }
  let calls = 0
  const stop = bindRestartRefresh(subscribe, async () => { calls += 1 })
  assert.equal(calls, 0)
  for (const fn of [...listeners]) fn()
  await Promise.resolve()
  assert.equal(calls, 1)
  stop()
  for (const fn of [...listeners]) fn()
  await Promise.resolve()
  assert.equal(calls, 1)
})

test('HomePage wires apiConfigManager isReady into project polling restart', () => {
  const fs = require('node:fs')
  const src = fs.readFileSync(path.resolve(__dirname, '../src/pages/HomePage.tsx'), 'utf8')
  assert.match(src, /subscribeRestart:\s*onRestart\s*=>\s*apiConfigManager\.addListener/)
  assert.match(src, /if\s*\(\s*config\.isReady\s*\)\s*onRestart\(\)/)
})

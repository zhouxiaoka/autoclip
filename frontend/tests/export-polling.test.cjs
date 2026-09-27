const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const ts = require('typescript')
const file = path.resolve(__dirname, '../src/features/exports/pollExportJob.ts')
const compiled = new Module(file, module)
compiled._compile(ts.transpileModule(fs.readFileSync(file, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText, file)
const { pollExportJob } = compiled.exports
const options = (controller = new AbortController()) => ({ signal: controller.signal, onProgress() {}, intervalMs: 0, maxAttempts: 3 })

test('queued and running jobs reach completion and preserve warnings', async () => {
  const jobs = [
    { job_id: 'a', status: 'queued' },
    { job_id: 'a', status: 'running', percent: 40 },
    { job_id: 'a', status: 'completed', percent: 100, result: { warnings: ['source subtitle absent'] } },
  ]
  const progress = []
  const result = await pollExportJob(async () => jobs.shift(), { ...options(), onProgress: p => progress.push(p) })
  assert.deepEqual(progress, [10, 40, 100])
  assert.deepEqual(result.result.warnings, ['source subtitle absent'])
})

test('failed render exposes the server error and stops polling', async () => {
  let calls = 0
  await assert.rejects(pollExportJob(async () => { calls++; return { status: 'failed', error: 'encoder failed' } }, options()), /encoder failed/)
  assert.equal(calls, 1)
})

test('timeout bounds observation without claiming server cancellation', async () => {
  let calls = 0
  await assert.rejects(pollExportJob(async () => { calls++; return { status: 'running' } }, options()), /后台任务可能仍在运行/)
  assert.equal(calls, 3)
})

test('aborted observer never starts a request', async () => {
  const controller = new AbortController()
  controller.abort()
  let calls = 0
  await assert.rejects(pollExportJob(async () => { calls++ }, options(controller)), { name: 'AbortError' })
  assert.equal(calls, 0)
})

test('unmount during an in-flight request suppresses stale progress and result', async () => {
  const controller = new AbortController()
  const progress = []
  await assert.rejects(pollExportJob(async () => {
    controller.abort()
    return { status: 'completed', percent: 100 }
  }, { ...options(controller), onProgress: p => progress.push(p) }), { name: 'AbortError' })
  assert.deepEqual(progress, [])
})

test('aborting while waiting clears the pending timer', async () => {
  const controller = new AbortController()
  let calls = 0
  const promise = pollExportJob(async () => { calls++ }, { ...options(controller), intervalMs: 10000 })
  controller.abort()
  await assert.rejects(promise, { name: 'AbortError' })
  assert.equal(calls, 0)
})

test('network errors are surfaced without silently repeating the job', async () => {
  const failure = new Error('network unavailable')
  await assert.rejects(pollExportJob(async () => { throw failure }, options()), err => err === failure)
})

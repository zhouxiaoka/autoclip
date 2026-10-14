const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

function transpile(rel) {
  const file = path.join(__dirname, rel)
  const source = fs.readFileSync(file, 'utf8').replaceAll('import.meta.env', '__env')
  return {
    file,
    js: ts.transpileModule(source, {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
    }).outputText,
  }
}

function loadFeedback(captureImpl) {
  const events = []
  const raw = []
  let enabled = true
  const fetchCalls = []
  const draft = transpile('../src/analytics/feedbackDraft.ts')
  const module = { exports: {} }
  const draftExports = {}
  vm.runInNewContext(draft.js, { module: { exports: draftExports }, exports: draftExports, URLSearchParams }, { filename: draft.file })
  const fb = transpile('../src/analytics/feedback.ts')
  const capture = (name, props) => {
    if (!enabled) return false
    events.push({ name, props: { ...props } })
    return true
  }
  vm.runInNewContext(fb.js, {
    module, exports: module.exports,
    __env: { VITE_PUBLIC_POSTHOG_FEEDBACK_SURVEY_ID: '' },
    fetch: (...args) => { fetchCalls.push(args); return Promise.reject(new Error('network should not run')) },
    require: (id) => {
      if (id === './posthog') {
        return {
          captureBusinessEvent: captureImpl || capture,
          isAnalyticsEnabled: () => enabled,
          posthog: { capture: (name, props) => raw.push({ name, props }), getSurveys: undefined, get_distinct_id: () => 'anon-1' },
        }
      }
      if (id === './feedbackDraft') return draftExports
      if (id === './lifecycle') return { getRuntimeInfo: () => ({ version: '1.5.7', os: 'macos', arch: 'arm64' }) }
      if (id === '../services/api') return { settingsApi: { getCurrentProvider: async () => ({ provider: 'ollama', model: 'qwen' }) } }
      if (id === '../features/settings/modelSettingsApi') return { modelSettingsApi: { get: async () => ({ transcription: { provider: 'whisper_local', model: 'tiny' } }) } }
      throw new Error(`Unexpected dependency: ${id}`)
    },
  }, { filename: fb.file })
  return {
    api: module.exports,
    events,
    raw,
    fetchCalls,
    setEnabled: (value) => { enabled = value },
  }
}

test('feedback.ts does not call posthog.capture or /capture/', () => {
  const src = fs.readFileSync(path.join(__dirname, '../src/analytics/feedback.ts'), 'utf8')
  assert.doesNotMatch(src, /posthog\.capture\s*\(/)
  assert.doesNotMatch(src, /\/capture\//)
  assert.match(src, /captureBusinessEvent\('feedback_opened'/)
  assert.match(src, /captureBusinessEvent\('feedback_dismissed'/)
  assert.match(src, /captureBusinessEvent\('feedback_submitted'/)
})

test('opened and dismissed go through the whitelist and respect opt-out', () => {
  const s = loadFeedback()
  const survey = { id: 'surv-1', name: 'AutoClip 应用内反馈' }
  s.api.trackFeedbackOpened({ source: 'settings' }, survey)
  s.api.trackFeedbackDismissed({ source: 'settings' }, survey)
  assert.deepEqual(s.raw, [])
  assert.equal(s.events[0].name, 'feedback_opened')
  assert.equal(s.events[0].props.source, 'settings')
  assert.equal(s.events[1].name, 'survey shown')
  assert.equal(s.events[2].name, 'feedback_dismissed')
  assert.equal(s.events[3].name, 'survey dismissed')
  s.events.length = 0
  s.setEnabled(false)
  s.api.trackFeedbackOpened({ source: 'failure', stage: 'ANALYZE' }, survey)
  s.api.trackFeedbackDismissed({ source: 'failure' }, survey)
  assert.equal(s.events.length, 0)
  assert.equal(s.fetchCalls.length, 0)
})

test('submitFeedback drops text/contact and does not post when opted out', async () => {
  const s = loadFeedback()
  const payload = {
    category: 'bug',
    text: '进度停住了请看 /Users/xxx/Movies/talk.mp4',
    contact: 'person@example.com',
    context: { source: 'failure', stage: 'ANALYZE', error_code: 'timeout' },
  }
  const on = await s.api.submitFeedback(payload)
  assert.equal(on.ok, true)
  assert.equal(s.events.length, 1)
  assert.equal(s.events[0].name, 'feedback_submitted')
  assert.equal(s.events[0].props.category, 'bug')
  assert.equal(s.events[0].props.source, 'failure')
  assert.equal(s.events[0].props.error_code, 'timeout')
  assert.equal(s.events[0].props.text, undefined)
  assert.equal(s.events[0].props.contact, undefined)
  assert.ok(!JSON.stringify(s.events[0].props).includes('person@example.com'))
  assert.ok(!JSON.stringify(s.events[0].props).includes('进度停住了'))
  assert.ok(!JSON.stringify(s.events[0].props).includes('/Users/xxx'))
  assert.ok(on.fallbackUrl.includes('github.com'))
  assert.equal(s.fetchCalls.length, 0)
  assert.deepEqual(s.raw, [])

  s.events.length = 0
  s.setEnabled(false)
  const off = await s.api.submitFeedback(payload)
  assert.equal(off.ok, false)
  assert.equal(s.events.length, 0)
  assert.equal(s.fetchCalls.length, 0)
  assert.ok(off.fallbackUrl.includes('github.com'))
})

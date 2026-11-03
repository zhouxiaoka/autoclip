const { test } = require('node:test')
const assert = require('node:assert/strict')
const { loadTs } = require('./load-ts.cjs')

const trial = loadTs('trialRunResult.ts')

const plain = x => JSON.parse(JSON.stringify(x))

test('trialLines empty for quick or missing result', () => {
  assert.deepEqual(plain(trial.trialLines(null)), [])
  assert.deepEqual(plain(trial.trialLines({ probe_kind: 'quick' })), [])
})

test('trialLines three tones for pass / rate-warn / fail', () => {
  const pass = trial.trialLines({
    probe_kind: 'trial',
    trial_context_ok: true,
    trial_rate_limited: false,
    trial_json_ok: true,
  })
  assert.equal(pass.length, 3)
  assert.equal(pass[0].label, '上下文 ✓')
  assert.equal(pass[1].label, '速率 ✓')
  assert.equal(pass[2].label, '输出格式 ✓')
  assert.equal(pass.every(l => l.tone === 'ok'), true)

  const warn = trial.trialLines({
    probe_kind: 'trial',
    trial_context_ok: true,
    trial_rate_limited: true,
    trial_json_ok: true,
  })
  assert.equal(warn[1].tone, 'warn')
  assert.match(warn[1].label, /速率 ⚠/)

  const fail = trial.trialLines({
    probe_kind: 'trial',
    trial_context_ok: false,
    trial_rate_limited: false,
    trial_json_ok: false,
  })
  assert.equal(fail[0].tone, 'fail')
  assert.equal(fail[2].tone, 'fail')
  assert.equal(fail[0].label, '上下文 ✗')
  assert.equal(fail[2].label, '输出格式 ✗')
})

test('showTrialFailedBadge and estimate parts', () => {
  assert.equal(trial.showTrialFailedBadge({ trial_status: 'failed' }), true)
  assert.equal(trial.showTrialFailedBadge({ trial_status: 'passed' }), false)
  assert.equal(trial.showTrialFailedBadge({}), false)
  assert.deepEqual(
    plain(trial.trialEstimateParts({
      probe_kind: 'trial',
      trial_estimate_requests: 4,
      trial_estimate_minutes: 1.5,
    })),
    { n: 4, m: 1.5 },
  )
  assert.equal(trial.trialEstimateParts({ probe_kind: 'quick' }), null)
})

test('applyValidation persists trial_* on connection for F5', () => {
  const providers = {
    PROVIDERS: {
      dashscope: { name: '阿里云百炼' }, openai: { name: 'OpenAI' },
      compatible: { name: '自定义' },
    },
  }
  const i18n = { t: x => x }
  const defaults = loadTs('modelDefaults.ts')
  const access = loadTs('providerAccess.ts', { '../../i18n': i18n, './providers': providers })
  const urls = loadTs('providerUrl.ts')
  const logic = loadTs('modelSettingsLogic.ts', {
    './providers': providers,
    './modelDefaults': defaults,
    './providerAccess': access,
    './providerUrl': urls,
  })
  const settings = {
    version: 1, saved: false,
    connections: [{ id: 'a', name: 'c', provider: 'compatible', base_url: 'https://gw.example/v1', api_key: 'k', image_api: 'auto', image_base_url: '' }],
    analysis: { connection_id: 'a', model: 'm', capability: 'auto' },
    vision: null, cover: null, transcription: { provider: 'whisper_local', model: 'base' },
    cover_enabled: false, allow_send_frame: false, analysis_mode: 'auto', allow_visual_screening: true,
    chunk_size: 5000, min_score_threshold: .7, max_clips_per_collection: 5,
  }
  const failed = logic.applyValidation(settings, 'a', {
    success: true, ok: true, result: 'ok',
    probe_kind: 'trial',
    trial_passed: false,
    trial_context_ok: true,
    trial_rate_limited: true,
    trial_json_ok: true,
    trial_avg_ms: 900,
    trial_estimate_requests: 2,
    trial_estimate_minutes: 0.3,
  })
  const row = failed.connections[0]
  assert.equal(row.trial_status, 'failed')
  assert.equal(row.trial_rate_limited, true)
  assert.equal(row.trial_avg_ms, 900)
  // Connection still validated ok — yellow badge only.
  assert.equal(row.validation_status === 'failed', false)
})

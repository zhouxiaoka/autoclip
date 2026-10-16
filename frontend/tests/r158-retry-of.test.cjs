const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

test('1.5.8 one-click retry: new attempt_id, linked to the failed one via retry_of', () => {
  const workflow = loadTs(path.resolve(__dirname, '../src/analytics/workflow.ts'))
  const events = []
  const tracker = new workflow.WorkflowTracker({ getItem: () => null, setItem() {}, removeItem() {} },
    () => true, (event, props) => { events.push({ event, props }); return true })
  const failed = { material_origin: 'user', generation: { status: 'failed', error_code: 'service_restarted' }, analysis: { status: 'failed', phase: 'production', error_code: 'service_restarted' } }
  tracker.watch('studio-generation', 'p1')
  tracker.observeStudio(tracker.list()[0], failed)
  tracker.watch('studio-generation', 'p1', undefined, undefined, {}, true)
  tracker.observeStudio(tracker.list().find(w => w.kind === 'studio-generation'), { ...failed, generation: { status: 'completed' }, analysis: { status: 'completed' } })
  const finished = events.filter(e => e.event === 'studio_generation_finished')
  assert.equal(finished.length, 2)
  const [first, second] = finished.map(e => e.props)
  assert.ok(first.attempt_id && second.attempt_id && first.attempt_id !== second.attempt_id)
  assert.equal(first.retry_of, undefined)
  assert.equal(second.retry_of, first.attempt_id)
})

test('1.5.8 failed-state Retry button reuses the rerun API, which restarts the watch (new attempt + retry_of)', () => {
  const fs = require('node:fs')
  const ui = fs.readFileSync(path.resolve(__dirname, '../src/features/studio/StudioResults.tsx'), 'utf8')
  const failed = ui.slice(ui.indexOf("workspace.analysis?.status==='failed'"))
  assert.match(failed.slice(0, 900), /!workspace\.output_variants\?\.length && <Btn[^>]*onClick=\{\(\)=>act\('retry-analysis', async\(\)=>\{await studioApi\.analyze\(project\.id, !!automatic\)\}\)\}>\{t\("重试"\)\}/)
  const api = fs.readFileSync(path.resolve(__dirname, '../src/features/studio/api.ts'), 'utf8')
  assert.match(api, /analyze: \(pid: string, automatic = false\)[\s\S]{0,300}workflow\.watch\('studio-screen', pid, undefined, undefined, props, true/)
  // retry_of survives the property allow-list and is never accepted when not a telemetry id
  const workflow = loadTs(path.resolve(__dirname, '../src/analytics/workflow.ts'))
  assert.equal(workflow.safeStudioProperties({ retry_of: 't-0123456789abc' }).retry_of, 't-0123456789abc')
  assert.equal(workflow.safeStudioProperties({ retry_of: 'https://x/sk-abc' }).retry_of, undefined)
})

test('1.5.8 failed-state action per code: user-cause codes get 「去设置」 + reason, everything else keeps Retry', () => {
  const fs = require('node:fs')
  const fa = loadTs(path.resolve(__dirname, '../src/features/studio/failureAction.ts'))
  const settings = { authentication: 'API Key 无效或已过期，请到设置里更新后再试', llm_auth_invalid: 'API Key 无效或已过期，请到设置里更新后再试', invalid_key: 'API Key 无效或已过期，请到设置里更新后再试', insufficient_quota: '服务商账户余额不足，请充值或换一个服务商', llm_not_configured: '还没有配置可用的模型，请先到设置里添加' }
  for (const [code, reason] of Object.entries(settings)) {
    assert.deepEqual({ ...fa.failureAction(code) }, { kind: 'settings', reason, destination: '/settings?section=analysis' }, code)
  }
  assert.equal(fa.failureAction('provider_error', 'permission_denied').kind, 'settings')
  assert.equal(fa.failureAction('provider_error', 'invalid_key').reason, settings.invalid_key)
  for (const code of ['service_restarted', 'timeout', 'connection', 'rate_limited', 'provider_error', 'whisper_not_installed', 'model_not_found', 'bad_endpoint', 'source_too_short', 'unexpected', '', undefined, null]) {
    assert.equal(fa.failureAction(code).kind, 'retry', String(code))
  }
  assert.equal(fa.failureAction('timeout', 'rate_limited').kind, 'retry')
  // single shared source: TS mirrors event_catalog attribution.user_cause (both copies)
  for (const file of ['../../backend/core/event_catalog.json', '../../docs/analytics/event_catalog.json']) {
    const uc = JSON.parse(fs.readFileSync(path.resolve(__dirname, file), 'utf8')).attribution.user_cause
    assert.deepEqual([...fa.USER_CAUSE_ERROR_CODES], uc.error_codes, file)
    assert.deepEqual([...fa.USER_CAUSE_UPSTREAM_TYPES], uc.upstream_types, file)
    const v4 = JSON.parse(fs.readFileSync(path.resolve(__dirname, file), 'utf8')).attribution.success_rate_v4
    if (v4) {  // once #416 lands: user_cause == v4 overall exclusion minus cancellation
      assert.deepEqual([...uc.error_codes].sort(), v4.overall_excluded_error_codes.filter(c => !/cancel/.test(c)).sort())
      assert.deepEqual([...uc.upstream_types].sort(), [...v4.overall_excluded_upstream_types].sort())
    }
  }
  // reasons + button copy in all 8 locales
  for (const lang of ['en', 'es', 'fr', 'ja', 'ko', 'pt', 'ru', 'zh']) {
    const data = JSON.parse(fs.readFileSync(path.resolve(__dirname, `../src/i18n/locales/${lang}.json`), 'utf8'))
    for (const key of ['去设置', ...new Set([...Object.values(settings), '这个 API Key 没有该模型的使用权限，请到设置里更换'])]) assert.ok(data[key], `${lang}: ${key}`)
  }
  // UI wiring: settings branch replaces Retry
  const ui = fs.readFileSync(path.resolve(__dirname, '../src/features/studio/StudioResults.tsx'), 'utf8')
  assert.match(ui, /action\.kind==='settings' \? <><span className="studio-muted">\{t\(action\.reason\)\}<\/span><Btn[^>]*onClick=\{\(\)=>navigate\(action\.destination\)\}>\{t\("去设置"\)\}<\/Btn><\/> : !workspace\.output_variants\?\.length && <Btn/)
})

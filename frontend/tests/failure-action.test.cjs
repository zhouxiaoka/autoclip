// Behavior tests for the failure-action page rule and secondary causes.

// failure-action.test.cjs
;(() => {
const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const fs = require('node:fs')
const { loadTs } = require('./load-ts.cjs')
const fa = loadTs(path.resolve(__dirname, '../src/features/studio/failureAction.ts'))

test('R21 #162: vision-stage user-cause failure sends 「去设置」 to the vision binding', () => {
  assert.equal(fa.failureAction('llm_auth_invalid', 'invalid_key', 'vision').destination, '/settings?section=vision')
  assert.equal(fa.failureAction('authentication', null, 'vision').destination, '/settings?section=vision')
  assert.equal(fa.failureAction('authentication', null, 'subtitle').destination, '/settings?section=speech')
  for (const stage of ['analyze', 'screen', 'render', undefined, null, '']) assert.equal(fa.failureAction('invalid_key', null, stage).destination, '/settings?section=analysis', String(stage))
  // every section we emit is a key SettingsPage understands
  const page = fs.readFileSync(path.resolve(__dirname, '../src/pages/SettingsPage.tsx'), 'utf8')
  for (const s of ['vision', 'speech', 'analysis']) assert.match(page, new RegExp(`\\n\\s*${s}: \\{ section: 'ai', anchor: 'ai-defaults-`), s)
})

test('R21 #163: precise upstream type wins over the coarse error_code (one classification)', () => {
  const perm = '当前令牌没有该模型的权限，请到服务商控制台勾选模型或更换分组。'
  assert.equal(fa.failureAction('llm_auth_invalid', 'permission_denied').reason, perm)
  assert.equal(fa.failureAction('authentication', 'permission_denied').reason, perm)
  const quota = fa.failureAction('llm_auth_invalid', 'insufficient_quota')
  assert.equal(quota.kind, 'settings')
  assert.equal(quota.reason, '余额或令牌额度不足，请充值或更换令牌后再试。')
  assert.equal(quota.reason.includes('API Key'), false)
  assert.equal(fa.failureAction('provider_error', 'insufficient_quota').reason, quota.reason)
  // non-user upstream does not erase a user-cause code
  assert.equal(fa.failureAction('insufficient_quota', 'rate_limited').reason, '余额或令牌额度不足，请充值或更换令牌后再试。')
  assert.equal(fa.failureAction('timeout', 'rate_limited').kind, 'retry')
})

test('B2: whisper gate codes open speech settings, a normal failure still retries', () => {
  const readiness = loadTs(path.resolve(__dirname, '../src/features/studio/importReadiness.ts'))
  assert.deepEqual([...fa.WHISPER_GATE_CODES], [
    'whisper_not_installed', 'whisper_install_failed', 'whisper_model_missing', 'whisper_model_failed',
  ])
  for (const code of fa.WHISPER_GATE_CODES) {
    const action = fa.failureAction(code)
    assert.equal(action.kind, 'install_asr', code)
    assert.equal(action.destination, '/settings?section=speech', code)
    assert.equal(action.label, '安装转写', code)
    assert.equal(readiness.gateKind(code), 'install', `${code} must stay the install half of readiness.GATE_CODES`)
    const page = fa.pageFailureAction({ error_code: code })
    assert.equal(page.kind, 'install_asr', code)
    assert.equal(page.destination, '/settings?section=speech', code)
    assert.equal(page.label, '安装转写', code)
  }
  for (const code of ['timeout', 'service_restarted', 'provider_error', 'transcription_empty', 'whisper_installing', 'whisper_model_downloading']) {
    assert.equal(fa.failureAction(code).kind, 'retry', code)
  }
  const led = fa.pageFailureAction({ error_code: 'timeout', secondary_error_codes: ['whisper_model_missing'] })
  assert.equal(led.kind, 'install_asr')
  assert.equal(led.destination, '/settings?section=speech')
  assert.equal(led.label, '安装转写')
  const auth = fa.failureAction('llm_auth_invalid')
  assert.equal(auth.kind, 'settings')
  assert.equal(auth.destination, '/settings?section=analysis')
  assert.equal(auth.label, undefined)
  for (const lang of ['en', 'es', 'fr', 'ja', 'ko', 'pt', 'ru', 'zh']) {
    const data = JSON.parse(fs.readFileSync(path.resolve(__dirname, `../src/i18n/locales/${lang}.json`), 'utf8'))
    assert.equal(typeof data['安装转写'], 'string', lang)
    assert.ok(data['安装转写'].length > 0, lang)
  }
})

test('X1 suggestedAction maps model, whisper, material and restart', () => {
  const model = fa.suggestedAction('timeout', null, 'analyze')
  assert.equal(model.id, 'switch_model')
  assert.equal(model.label, '换模型重试')
  assert.equal(model.kind, 'settings')
  assert.equal(model.destination, '/settings?section=analysis')
  assert.equal(fa.suggestedAction('provider_error', 'model_not_found', 'vision').destination, '/settings?section=vision')
  assert.equal(fa.suggestedAction('invalid_response', 'permission_denied', 'subtitle').id, 'switch_model')
  assert.equal(fa.suggestedAction(null, 'bad_endpoint', 'analyze').label, '换模型重试')
  const install = fa.suggestedAction('whisper_not_installed', null, 'subtitle')
  assert.equal(install.id, 'install_transcription')
  assert.equal(install.label, '安装转写')
  assert.equal(install.destination, '/settings?section=speech')
  for (const code of fa.WHISPER_GATE_CODES) assert.equal(fa.suggestedAction(code).id, 'install_transcription', code)
  const material = fa.suggestedAction('source_no_audio')
  assert.equal(material.id, 'change_material')
  assert.equal(material.label, '换素材 / 加字幕')
  assert.equal(material.destination, '/')
  for (const code of ['transcription_empty', 'subtitle_setup', 'source_unreadable', 'timeline_empty']) {
    assert.equal(fa.suggestedAction(code).id, 'change_material', code)
  }
  const restart = fa.suggestedAction('service_restarted', 'timeout', 'render')
  assert.equal(restart.id, 'keep_window')
  assert.equal(restart.label, '保持窗口打开，或缩短素材')
  assert.equal(restart.kind, 'note')
  assert.equal(restart.destination, undefined)
  assert.equal(fa.suggestedAction('frame_extract_failed'), null)
  assert.equal(fa.suggestedAction('store_lock_timeout'), null)
  assert.equal(fa.suggestedAction('unknown'), null)
  assert.equal(fa.diagnoseSuggestionId(null), 'none')
  assert.equal(fa.diagnoseSuggestionId(model), 'switch_model')
  assert.equal(fa.diagnoseInsteadOfRetry({ count: 2, same_code: true }), true)
  assert.equal(fa.diagnoseInsteadOfRetry({ count: 3, same_code: true }), true)
  assert.equal(fa.diagnoseInsteadOfRetry({ count: 2, same_code: false }), false)
  assert.equal(fa.diagnoseInsteadOfRetry({ count: 1, same_code: true }), false)
  assert.equal(fa.diagnoseInsteadOfRetry(null), false)
  const page = fa.pageSuggestedAction({ error_code: 'timeout', upstream_error_type: null, failure_stage: 'vision' })
  assert.equal(page.action.id, 'switch_model')
  assert.equal(page.action.destination, '/settings?section=vision')
  assert.equal(page.errorCode, 'timeout')
})
})()

// failure-action.test.cjs
;(() => {
const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const fs = require('node:fs')
const { loadTs } = require('./load-ts.cjs')
const fa = loadTs(path.resolve(__dirname, '../src/features/studio/failureAction.ts'))

// PM rule : stats stay product-first; the page leads with any cause the user can fix.
// Shape = backend analysis record for content(ASR 401) + highlight(vision timeout), either goal order.
const record = { error: 'x', error_code: 'timeout', failure_stage: 'vision', upstream_error_type: null,
  secondary_error_codes: ['authentication'], secondary_upstream_error_types: ['invalid_key'], secondary_failure_stages: ['subtitle'] }

for (const order of ['content,highlight', 'highlight,content']) {
  test(`R24 page: auth + timeout (${order}) shows the auth reason and 「去设置」`, () => {
    const action = fa.pageFailureAction(record)
    assert.equal(action.kind, 'settings')
    assert.equal(action.destination, '/settings?section=speech')
    assert.equal(action.reason, fa.failureAction('authentication', 'invalid_key', 'subtitle').reason)
  })
}

test('R24 page: product-only causes still retry', () => {
  assert.equal(fa.pageFailureAction({ error_code: 'timeout', secondary_error_codes: ['render'], secondary_upstream_error_types: [''] }).kind, 'retry')
})

test('R24 page: FailureActions uses the page rule', () => {
  const src = fs.readFileSync(path.resolve(__dirname, '../src/features/studio/FailureActions.tsx'), 'utf8')
  assert.match(src, /pageFailureAction\(info\)/)
})

test('R24 page: StudioResults hands the secondary causes to FailureActions', () => {
  const src = fs.readFileSync(path.resolve(__dirname, '../src/features/studio/StudioResults.tsx'), 'utf8')
  assert.match(src, /receiptFailureInfo\(workspace\.attempts, workspace\.analysis\?\.run_id\) \|\| analysisPageFailure\(workspace\.analysis, workspace\.generation\)/)
  const info = fa.analysisPageFailure(record)
  assert.deepEqual(info.secondary_error_codes, ['authentication'])
  assert.deepEqual(info.secondary_upstream_error_types, ['invalid_key'])
  assert.deepEqual(info.secondary_failure_stages, ['subtitle'])
  assert.equal(fa.pageFailureAction(info).kind, 'settings')
  assert.equal(fa.pageFailureAction(info).destination, '/settings?section=speech')
})
})()

// failure-action.test.cjs
;(() => {
const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const fs = require('node:fs')
const { loadTs } = require('./load-ts.cjs')
const wf = loadTs(path.resolve(__dirname, '../src/analytics/workflow.ts'))
const catalog = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../docs/analytics/event_catalog.json'), 'utf8'))
const plan = fs.readFileSync(path.resolve(__dirname, '../../docs/analytics/TRACKING_PLAN.md'), 'utf8')
const src = fs.readFileSync(path.resolve(__dirname, '../src/analytics/workflow.ts'), 'utf8')
const SECONDARY = ['secondary_error_codes', 'secondary_upstream_error_types']
const TERMINALS = ['studio_generation_finished', 'studio_production_finished']

test('R24 #2: both secondary fields are registered on both terminals (description, values, comma format)', () => {
  for (const ev of TERMINALS) {
    const opt = catalog.events[ev].optional_properties || {}
    for (const k of SECONDARY) {
      assert.ok(opt[k], `${ev}.${k} not registered`)
      assert.ok(opt[k].description && opt[k].format === 'comma_joined' && opt[k].max_items === 3, `${ev}.${k}`)
      assert.ok(catalog.enums[opt[k].values], `${ev}.${k} values enum`)
    }
  }
  for (const k of SECONDARY) assert.match(plan, new RegExp('`' + k + '`'))
})

test('R24 #2: the registered allow-lists are the ones the sanitizer enforces', () => {
  const codes = loadTs(path.resolve(__dirname, '../src/analytics/failureCodes.ts'))
  assert.equal(src.includes('const ERROR_CODE = /^'), false)
  assert.deepEqual([...catalog.enums.studio_error_code].sort(), [...codes.STUDIO_ERROR_CODES].sort())
  for (const code of catalog.enums.studio_error_code) assert.equal(codes.ERROR_CODE.test(code), true, code)
  assert.equal(codes.ERROR_CODE.test('http_429'), true)
  assert.equal(codes.ERROR_CODE.test('disk'), false)
  assert.equal(codes.ERROR_CODE.test('not_a_code'), false)
  assert.equal(catalog.events.studio_production_finished.optional_properties.secondary_upstream_error_types.values, 'upstream_error_type')
})

test('R24 #2: a terminal carries no unregistered secondary_* field (page-only stages stay off the event)', () => {
  const out = wf.safeStudioProperties({ secondary_error_codes: ['authentication'], secondary_upstream_error_types: ['invalid_key'],
    secondary_failure_stages: ['subtitle'], secondary_extra: ['x'] })
  const registered = Object.keys(catalog.events.studio_production_finished.optional_properties || {})
  const emitted = Object.keys(out).filter(k => k.startsWith('secondary_'))
  assert.deepEqual(emitted.sort(), [...SECONDARY].sort())
  for (const k of emitted) assert.ok(registered.includes(k), k)
})
})()

// failure-action.test.cjs — X2 five kinds
;(() => {
const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const fs = require('node:fs')
const { loadTs } = require('./load-ts.cjs')
const fa = loadTs(path.resolve(__dirname, '../src/features/studio/failureAction.ts'))

test('X2: FailureAction.kind covers retry | settings | install_asr | switch_model | recharge', () => {
  assert.deepEqual([...fa.SWITCHABLE_UPSTREAM].sort(), [
    'bad_endpoint', 'invalid_response', 'model_not_found', 'rate_limited', 'timeout', 'upstream_unavailable',
  ].sort())
  assert.deepEqual([...fa.SPONSOR_PROVIDERS].sort(), ['api88', 'apimart', 'infistar'].sort())

  assert.equal(fa.failureAction('timeout').kind, 'retry')

  const auth = fa.failureAction('llm_auth_invalid', 'invalid_key')
  assert.equal(auth.kind, 'settings')

  assert.equal(fa.failureAction('whisper_not_installed').kind, 'install_asr')

  for (const upstream of fa.SWITCHABLE_UPSTREAM) {
    assert.equal(fa.failureAction(null, upstream, null, 2).kind, 'switch_model', upstream)
    const single = fa.failureAction(null, upstream, null, 1)
    assert.equal(single.kind, 'settings', upstream)
    assert.equal(single.reason, fa.ADD_PROVIDER_HINT, upstream)
    assert.equal(single.label, '去设置', upstream)
    // unknown count keeps prior behavior (retry for non-user-cause)
    assert.equal(fa.failureAction(null, upstream, null, null).kind, 'retry', upstream)
  }

  const recharge = fa.failureAction('provider_error', 'insufficient_quota', null, null, 'api88')
  assert.equal(recharge.kind, 'recharge')
  assert.equal(recharge.provider, 'api88')
  assert.equal(recharge.label, '去 88API 充值')
  assert.match(recharge.destination, /^https?:\/\//)
  // non-sponsor quota → 查看余额 (opens keyUrl / docs)
  const quota = fa.failureAction('provider_error', 'insufficient_quota', null, null, 'openai')
  assert.equal(quota.kind, 'recharge')
  assert.equal(quota.label, '查看余额')
  assert.match(quota.destination, /^https?:\/\//)
})

test('X2: pageFailureAction uses connection_count and provider', () => {
  assert.equal(fa.pageFailureAction({
    error_code: 'timeout', upstream_error_type: 'rate_limited', connection_count: 3,
  }).kind, 'switch_model')
  assert.equal(fa.pageFailureAction({
    error_code: 'timeout', upstream_error_type: 'rate_limited', connection_count: 1,
  }).kind, 'settings')
  assert.equal(fa.pageFailureAction({
    error_code: 'provider_error', upstream_error_type: 'insufficient_quota', provider: 'infistar',
  }).kind, 'recharge')
})

test('X2: FailureActions routes the five kinds', () => {
  const src = fs.readFileSync(path.resolve(__dirname, '../src/features/studio/FailureActions.tsx'), 'utf8')
  assert.match(src, /action\.kind === 'install_asr'/)
  assert.match(src, /action\.kind === 'switch_model'/)
  assert.match(src, /action\.kind === 'recharge'/)
  assert.match(src, /SwitchModelDialog/)
  assert.match(src, /SWITCH_MODEL_LABEL/)
  const dialog = fs.readFileSync(path.resolve(__dirname, '../src/features/studio/SwitchModelDialog.tsx'), 'utf8')
  assert.match(dialog, /defaultSwitchOption/)
  assert.match(dialog, /ProviderQualityMarks/)
  const home = fs.readFileSync(path.resolve(__dirname, '../src/pages/HomePage.tsx'), 'utf8')
  assert.match(home, /handleSwitchModelAndRetry/)
  assert.match(home, /retry_kind: 'switch_model'/)
  assert.match(home, /choice\?\.connectionId|choice \|\|/)
  const api = fs.readFileSync(path.resolve(__dirname, '../src/features/studio/api.ts'), 'utf8')
  assert.match(api, /retry_kind/)
  const catalog = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../docs/analytics/event_catalog.json'), 'utf8'))
  assert.deepEqual(catalog.enums.retry_kind, ['same', 'switch_model', 'after_install'])
})
})()

// failure-action.test.cjs — R3 resume button copy
;(() => {
const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const fs = require('node:fs')
const { loadTs } = require('./load-ts.cjs')
// FailureActions is TSX — load via transpile like project-card does for plan helpers
const ts = require('typescript')
const React = require('react')
const code = ts.transpileModule(fs.readFileSync(path.resolve(__dirname, '../src/features/studio/FailureActions.tsx'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, esModuleInterop: true },
}).outputText
const { runInSandbox } = require('./vm-sandbox.cjs')
const module = { exports: {} }
const stubs = {
  '../../i18n': { t: (k) => k },
  '../../ui': { Btn: () => null, Dialog: () => null },
  '../../utils/timelineFailure': { WEAK_LOCAL_TIMELINE_REASON: 'weak', weakLocalTimelineFailure: () => false },
  '../../utils/externalLinks': { openExternalLink: async () => {} },
  './failureAction': loadTs(path.resolve(__dirname, '../src/features/studio/failureAction.ts')),
  './SwitchModelDialog': { __esModule: true, default: () => null },
  './switchModelOptions': {},
}
runInSandbox(code, {
  module, exports: module.exports, console,
  require: (id) => stubs[id] || require(id),
})
const fa = module.exports

test('R3: retry label uses resume_point; fresh secondary when checkpoint exists', () => {
  const none = fa.failurePlan({ error_code: 'timeout' }, true, false, null, null)
  assert.equal(none.buttons.find(b => b.key === 'retry').label, '重试')
  assert.equal(none.buttons.find(b => b.key === 'fresh'), undefined)

  const sub = fa.failurePlan({ error_code: 'timeout' }, true, false, null, { point: 'subtitle', label: '已有字幕，从分析开始' })
  assert.equal(sub.buttons.find(b => b.key === 'retry').label, '已有字幕，从分析开始')
  assert.equal(sub.buttons.find(b => b.key === 'fresh').label, '从头重做')

  const step = fa.failurePlan({ error_code: 'timeout' }, true, false, null, { point: 'step2', label: '从第 2 步继续' })
  assert.equal(step.buttons.find(b => b.key === 'retry').label, '从第 2 步继续')
  assert.equal(step.buttons.find(b => b.key === 'fresh').label, '从头重做')
})

test('R3: api.retry accepts fresh', () => {
  const src = fs.readFileSync(path.resolve(__dirname, '../src/features/studio/api.ts'), 'utf8')
  assert.match(src, /fresh\?: boolean/)
  assert.match(src, /fresh: !!opts\?\.fresh/)
})
})()


// failure-action.test.cjs — X3 sponsor recharge / billable N
;( () => {
const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const fs = require('node:fs')
const { loadTs } = require('./load-ts.cjs')
const fa = loadTs(path.resolve(__dirname, '../src/features/studio/failureAction.ts'))

test('X3: sponsor insufficient_quota → 去 XX 充值 with topup_url', () => {
  for (const [id, short] of [['api88', '88API'], ['infistar', 'Infistar'], ['apimart', 'APIMart']]) {
    const action = fa.failureAction('provider_error', 'insufficient_quota', null, null, id)
    assert.equal(action.kind, 'recharge', id)
    assert.equal(action.label, `去 ${short} 充值`, id)
    const target = fa.rechargeTarget(id)
    assert.equal(target.sponsor, true, id)
    assert.equal(action.destination, target.url, id)
    assert.ok(target.url.includes(id === 'api88' ? '88api.ai' : id === 'infistar' ? 'infistar' : 'apimart'), id)
  }
  assert.equal(fa.RECHARGE_HINT, '密钥没问题，是余额不足。充值后点重试即可。')
})

test('X3: non-sponsor insufficient_quota → 查看余额', () => {
  const action = fa.failureAction('provider_error', 'insufficient_quota', null, null, 'deepseek')
  assert.equal(action.kind, 'recharge')
  assert.equal(action.label, fa.VIEW_BALANCE_LABEL)
  assert.match(action.destination, /^https?:\/\//)
})

test('X3: billableCallsLine has N requests, no dollar amount', () => {
  assert.equal(fa.billableCallsLine(3), '本次已消耗 3 次请求')
  assert.doesNotMatch(fa.billableCallsLine(3), /\$|￥|元/)
  const card = fa.presentedFailure({
    error_code: 'provider_error',
    upstream_error_type: 'insufficient_quota',
    billable_calls_before_failure: 5,
  }, fa.RECHARGE_HINT)
  assert.equal(card.billing, '本次已消耗 5 次请求')
  assert.equal(card.reason, fa.RECHARGE_HINT)
})

test('X3: FailureActions opens http destination + uses RECHARGE_HINT', () => {
  const src = fs.readFileSync(path.resolve(__dirname, '../src/features/studio/FailureActions.tsx'), 'utf8')
  assert.match(src, /RECHARGE_HINT/)
  assert.match(src, /openExternalLink/)
  assert.match(src, /https\?:/)
})
})()

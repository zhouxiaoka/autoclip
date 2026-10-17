const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

const guidance = loadTs('firstRunGuidance.ts')
const experience = loadTs(path.join(__dirname, '../src/analytics/experience.ts'), {
  './posthog': { captureBusinessEvent() {} },
  './observer': { workflow: { generation() { return 1 }, active() { return false } } },
  './workflow': loadTs(path.join(__dirname, '../src/analytics/workflow.ts')),
  './successRateContract': { sanitizeProviderValidationProperties: x => x, SuccessRateEvent: { ProviderValidationFinished: 'provider_validation_finished' }, TELEMETRY_PROVIDERS: loadTs(path.join(__dirname, '../src/analytics/successRateContract.ts')).TELEMETRY_PROVIDERS },
}, path.join(__dirname, '../src/analytics'))

test('first-run defaults to 88API and maps choices to later / one-click / settings', () => {
  assert.deepEqual([...guidance.FIRST_RUN_CHOICES], ['api88', 'infistar', 'other'])
  assert.equal(guidance.FIRST_RUN_DEFAULT, 'api88')
  assert.equal(guidance.firstRunPrimaryAction('api88'), 'one_click')
  assert.equal(guidance.firstRunPrimaryAction('infistar'), 'one_click')
  assert.equal(guidance.firstRunPrimaryAction('other'), 'open_settings')
  assert.equal(guidance.firstRunSponsor('other'), null)
  assert.equal(guidance.firstRunPrimaryLabel('other').key, '去设置选择其他服务商')
  const oneClick = guidance.firstRunPrimaryLabel('api88', '88API')
  assert.equal(oneClick.key, '通过 {{name}} 一键获取')
  assert.equal(oneClick.values.name, '88API')
})

test('setup_action one_click keeps provider and drops keys, URLs and user text', () => {
  const props = experience.safeExperience({
    placement: 'home_setup',
    action: 'one_click',
    provider: 'api88',
    presentation_id: 't-aaaaaaaaaaaa',
    api_key: 'sk-secret',
    register_url: 'https://88api.ai/sign-up?aff=2PIc&key=sk-secret',
    base_url: 'https://api.88api.ai/v1',
    title: '用户自己的标题',
    text: '用户粘贴的说明',
  })
  assert.equal(props.action, 'one_click')
  assert.equal(props.provider, 'api88')
  assert.equal(props.placement, 'home_setup')
  assert.equal(props.api_key, undefined)
  assert.equal(props.register_url, undefined)
  assert.equal(props.base_url, undefined)
  assert.equal(props.title, undefined)
  assert.equal(props.text, undefined)
  const dumped = JSON.stringify(props)
  assert.equal(dumped.includes('sk-secret'), false)
  assert.equal(dumped.includes('88api.ai'), false)
  assert.equal(dumped.includes('用户'), false)
})

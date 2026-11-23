const { test } = require('node:test')
const assert = require('node:assert/strict')
const React = require('react')
const { loadTs } = require('./load-ts.cjs')

function flatten(node) {
  if (!React.isValidElement(node)) return [node]
  const props = node.props || {}
  const nested = [props.children, props.hint, props.label]
  return [node, ...nested.flatMap(item => React.Children.toArray(item).flatMap(flatten))]
}

test('Bailian shows the author referral beside Get API key, and the console link stays primary', () => {
  const links = []
  const tracked = []
  const providers = loadTs('providers.ts', { '../../i18n': { t: text => text } })
  const access = loadTs('providerAccess.ts', { '../../i18n': { t: text => text }, './providers': providers })
  const Fields = loadTs('ProviderFields.tsx', {
    react: { useState: () => [false, () => {}] },
    antd: { Input: Object.assign(() => null, { Password: 'password' }), Select: 'select' },
    '../../i18n': { t: text => text },
    '../../ui': { Btn: 'button', Row: 'row' },
    '../../utils/externalLinks': { openExternalLink: url => links.push(url) },
    '../../analytics/events': { trackSponsorLinkOpened: event => tracked.push(JSON.parse(JSON.stringify(event))) },
    './providers': providers,
    './modelSettingsLogic': { presetKey: connection => connection.provider },
    './providerAccess': access,
    './providerUrl': loadTs('providerUrl.ts', {}),
  }).default
  const preset = providers.PROVIDERS.dashscope
  assert.equal(preset.keyUrl, 'https://bailian.console.aliyun.com/')
  assert.equal(preset.referralUrl, 'https://www.aliyun.com/benefit?userCode=qmyj6jch')
  assert.equal(preset.sponsor, undefined)
  const nodes = flatten(Fields({
    connection: { provider: 'dashscope', api_key: '', base_url: '' },
    placement: 'settings_model',
    onChoose() {},
    onEdit() {},
  }))
  const text = nodes.filter(node => typeof node === 'string').join(' ')
  assert.ok(text.includes('获取 API Key'))
  assert.ok(text.includes('作者推荐链接'))
  assert.equal(text.includes('赞助'), false)
  const referral = nodes.find(node => node?.props?.['data-author-referral'] === '1')
  assert.equal(referral.props.href, preset.referralUrl)
  referral.props.onClick({ preventDefault() {} })
  assert.equal(links.at(-1), preset.referralUrl)
  assert.deepEqual(tracked.at(-1), { sponsor: 'dashscope', target: 'referral', placement: 'settings_model' })
  const keyLink = nodes.find(node => node?.props?.href === preset.keyUrl)
  assert.ok(keyLink)
  keyLink.props.onClick({ preventDefault() {} })
  assert.equal(links.at(-1), 'https://bailian.console.aliyun.com/')

  const comet = providers.PROVIDERS.cometapi
  assert.equal(comet.referralUrl, 'https://www.cometapi.com/?ref=kris')
  assert.equal(comet.cloud.baseUrl, 'https://api.cometapi.com/v1')
  assert.equal(comet.sponsor, undefined)
  const cometNodes = flatten(Fields({
    connection: { provider: 'cometapi', api_key: '', base_url: 'https://api.cometapi.com/v1' },
    placement: 'settings_model',
    onChoose() {},
    onEdit() {},
  }))
  const cometRef = cometNodes.find(node => node?.props?.['data-author-referral'] === '1')
  assert.equal(cometRef.props.href, 'https://www.cometapi.com/?ref=kris')
  cometRef.props.onClick({ preventDefault() {} })
  assert.equal(links.at(-1), 'https://www.cometapi.com/?ref=kris')
  assert.deepEqual(tracked.at(-1), { sponsor: 'cometapi', target: 'referral', placement: 'settings_model' })

  for (const [id, url, base] of [
    ['novita', 'https://novita.ai/?ref=nzvindf&utm_source=affiliate', 'https://api.novita.ai/v3/openai'],
    ['poyo', 'https://poyo.ai/?affiliate_code=christ520482&open_signup=1', 'https://api.poyo.ai/v1'],
  ]) {
    const row = providers.PROVIDERS[id]
    assert.equal(row.referralUrl, url)
    assert.equal(row.cloud.baseUrl, base)
    assert.equal(row.sponsor, undefined)
    const nodesFor = flatten(Fields({
      connection: { provider: id, api_key: '', base_url: base },
      placement: 'settings_model',
      onChoose() {},
      onEdit() {},
    }))
    const ref = nodesFor.find(node => node?.props?.['data-author-referral'] === '1')
    assert.equal(ref.props.href, url)
    ref.props.onClick({ preventDefault() {} })
    assert.equal(links.at(-1), url)
    assert.deepEqual(tracked.at(-1), { sponsor: id, target: 'referral', placement: 'settings_model' })
  }
})

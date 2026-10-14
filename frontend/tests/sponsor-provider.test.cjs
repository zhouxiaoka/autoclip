const { test } = require('node:test')
const assert = require('node:assert/strict')
const React = require('react')
const { loadTs } = require('./load-ts.cjs')
const load = loadTs
const providers = loadTs('providers.ts', { '../../i18n': { t: text => text } })
const plain = value => JSON.parse(JSON.stringify(value))
function flatten(node) {
  if (!React.isValidElement(node)) return [node]
  return [node, ...React.Children.toArray(node.props.children).flatMap(flatten)]
}

test('sponsor selection, offer, registration link and attribution follow the chosen provider', () => {
  const events = [], links = []
  const access = load('providerAccess.ts', { '../../i18n': { t: text => text }, './providers': providers })
  const Fields = load('ProviderFields.tsx', {
    react: { useState: () => [false, () => {}] },
    antd: { Input: { Password: 'password' }, Select: 'select' },
    '../../i18n': { t: text => text }, '../../ui': { Btn: 'button', Row: 'row' },
    '../../utils/externalLinks': { openExternalLink: url => links.push(url) },
    '../../analytics/events': { trackSponsorLinkOpened: event => events.push(plain(event)) },
    './providers': providers, './modelSettingsLogic': { presetKey: c => c.provider },
    './providerAccess': access,
    './providerUrl': load('providerUrl.ts', {}),
  }).default
  const options = providers.providerPickerOptions()
  assert.deepEqual(Array.from(options[0].options, p => p.value), ['api88', 'infistar'])
  for (const placement of ['home_setup', 'settings_model']) {
    for (const provider of ['api88', 'infistar']) {
      const preset = providers.PROVIDERS[provider]
      const nodes = flatten(Fields({ connection: { provider, api_key: '' }, placement, onChoose() {}, onEdit() {} }))
      const text = nodes.filter(n => typeof n === 'string').join(' ')
      assert.ok(text.includes(preset.sponsor.description))
      assert.equal(text.includes('$5'), provider === 'infistar')
      const buttons = nodes.filter(n => n?.type === 'button')
      buttons[0].props.onClick()
      assert.equal(links.at(-1), preset.sponsor.registerUrl)
      assert.deepEqual(events.at(-1), { sponsor: provider, target: 'register', placement })
      buttons[1].props.onClick()
      assert.equal(links.at(-1), preset.sponsor.guideUrl)
      assert.deepEqual(events.at(-1), { sponsor: provider, target: 'guide', placement })
    }
  }
  assert.equal(providers.PROVIDERS.api88.sponsor.registerUrl, 'https://88api.ai/sign-up?aff=2PIc')
  assert.equal(providers.PROVIDERS.api88.cloud.baseUrl, 'https://api.88api.ai/v1')
})

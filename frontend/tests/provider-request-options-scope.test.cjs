const { test } = require('node:test')
const assert = require('node:assert/strict')
const React = require('react')
const { loadTs } = require('./load-ts.cjs')

const i18n = { t: key => key }
const catalog = loadTs('providerCatalogView.ts', { '../../i18n': i18n })
const Fields = loadTs('ProviderFields.tsx', {
  react: { ...React, useState: () => [false, () => {}] },
  antd: { Input: Object.assign(() => null, { Password: 'password' }), Select: 'select' },
  '../../i18n': i18n,
  '../../ui': { Row: 'row', Btn: 'button' },
  '../../utils/externalLinks': { openExternalLink() {} },
  '../../analytics/events': { trackSponsorLinkOpened() {} },
  './CustomRequestOptions': { default: props => React.createElement('request-options', props) },
}).default

function flatten(node) {
  if (node == null || typeof node === 'boolean') return []
  if (Array.isArray(node)) return node.flatMap(flatten)
  if (!React.isValidElement(node)) return [node]
  if (typeof node.type === 'function') return [node, ...flatten(node.type(node.props))]
  return [node, ...flatten(node.props.children)]
}

const connection = extra => ({ id: 'endpoint', name: 'Endpoint', provider: 'compatible', base_url: 'https://fixture-gateway.invalid/v1', image_api: 'auto', image_base_url: '', ...extra })
function render(c) {
  const edits = []
  const before = JSON.stringify(c)
  const tree = Fields({ connection: c, placement: 'settings_model', onChoose() {}, onEdit: patch => edits.push(patch) })
  assert.equal(JSON.stringify(c), before)
  assert.deepEqual(edits, [])
  return flatten(tree).filter(node => node.type === 'request-options')
}

test('standard catalog presets do not expose advanced request controls or alter saved options', () => {
  for (const preset of catalog.catalogProviders()) {
    if (!['compatible', 'needs_endpoint', 'legacy'].includes(catalog.connectKind(preset))) continue
    const c = connection({ provider: catalog.connectKind(preset) === 'legacy' ? preset.id : 'compatible', catalog_provider_id: preset.id, base_url: preset.base_url || 'https://enterprise-endpoint.invalid/v1', has_http_headers: true, reasoning_effort: 'high', extra_body: { provider_options: { mode: 'saved' } } })
    assert.equal(render(c).length, 0, preset.id)
  }
  // A known compatible endpoint remains a preset even without an explicit catalog id.
  for (const id of ['openrouter', 'siliconflow']) {
    const preset = catalog.catalogPreset(id)
    assert.ok(preset?.base_url)
    assert.equal(render(connection({ base_url: preset.base_url })).length, 0, id)
  }
})

test('unmatched custom gateways keep the editor including legacy foreign OpenAI endpoints', () => {
  for (const c of [connection({}), connection({ base_url: '' }), connection({ provider: 'openai' }), connection({ has_http_headers: true, _http_headers_text: '', reasoning_effort: 'medium', extra_body: { provider_options: true } })]) {
    const entries = render(c)
    assert.equal(entries.length, 1)
    assert.equal(entries[0].props.value, c)
  }
  assert.equal(render(undefined).length, 0)
})

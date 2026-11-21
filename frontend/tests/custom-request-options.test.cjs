const { test } = require('node:test')
const assert = require('node:assert/strict')
const { loadTs } = require('./load-ts.cjs')
const plain = value => JSON.parse(JSON.stringify(value))
const options = loadTs('customRequestOptions.ts')
const custom = loadTs('customProvider.ts', { '../../i18n': { t: x => x }, './providers': { PROVIDERS: { compatible: { name: 'Custom' } } } })

const ready = () => custom.addManualModel({ ...custom.emptyDraft(), name: 'Fixture', base_url: 'http://127.0.0.1:12345/v1' }, 'fixture-model').draft

test('valid JSON headers and provider parameters serialize without editor text or secret flags', () => {
  const draft = { ...ready(), _http_headers_text: '{"X-Workspace":"fixture-value"}', _extra_body_text: '{"provider_options":{"thinking":true}}', reasoning_effort: 'high' }
  assert.equal(options.requestOptionsIssue(draft), null)
  assert.equal(custom.draftIssue(draft), null)
  const wire = options.wireRequestOptions(custom.toConnection(draft, 'fixture'))
  assert.deepEqual(plain(wire.http_headers), { 'X-Workspace': 'fixture-value' })
  assert.deepEqual(plain(wire.extra_body), { provider_options: { thinking: true } })
  assert.equal(wire.reasoning_effort, 'high')
  assert.equal('_http_headers_text' in wire, false)
  assert.equal('_extra_body_text' in wire, false)
  assert.equal('has_http_headers' in wire, false)
  assert.equal(draft._http_headers_text, '{"X-Workspace":"fixture-value"}')
})

for (const text of ['bad JSON', '[]', '{"Host":"elsewhere"}', '{"X-Workspace":"a","x-workspace":"b"}', '{"Bad Name":"value"}', '{"X-Workspace":"value\\r\\nInjected: bad"}', '{"X-Workspace":12}']) test(`invalid header draft is blocked: ${text.slice(0, 24)}`, () => {
  const draft = { ...ready(), _http_headers_text: text }
  assert.equal(options.requestOptionsIssue(draft), 'headers')
  assert.equal(custom.draftIssue(draft), 'request_options')
  assert.throws(() => options.wireRequestOptions(draft), /Invalid custom request options/)
})

for (const body of ['[]', '{"model":"other"}', '{"messages":[]}', '{"stream":false}', '{"max_tokens":999999}', '{"timeout":999}', '{"extra_headers":{}}', '{"reasoning_effort":"high"}', '{"response_format":{}}']) test(`provider parameter reserved field is blocked: ${body}`, () => {
  assert.equal(options.requestOptionsIssue({ _extra_body_text: body }), 'body')
})

test('saved headers stay private, blank retains them and empty object clears them', () => {
  const saved = { id: 'fixture', has_http_headers: true }
  assert.equal(options.wireRequestOptions({ ...saved, _http_headers_text: '' }).http_headers, undefined)
  assert.deepEqual(plain(options.wireRequestOptions({ ...saved, _http_headers_text: '{}' }).http_headers), {})
  assert.equal(options.wireRequestOptions(saved).http_headers, undefined)
  assert.equal(options.requestOptionsIssue({ extra_body: { value: Infinity } }), 'body')
  assert.equal(options.requestOptionsIssue({ _extra_body_text: JSON.stringify({ value: 'x'.repeat(16385) }) }), 'body')
})

test('all settings request paths strip drafts and reject malformed options before any HTTP call', async () => {
  const calls = []
  const api = { post: (...args) => { calls.push(args); return Promise.resolve({}) }, put: (...args) => { calls.push(args); return Promise.resolve({}) } }
  const module = loadTs('modelSettingsApi.ts', { '../../services/api': { default: api }, '../../utils/apiConfig': { buildApiUrl: x => x } })
  const connection = custom.toConnection({ ...ready(), _http_headers_text: '{"X-Workspace":"fixture-value"}', _extra_body_text: '{"thinking":{"type":"enabled"}}' }, 'fixture')
  await module.modelSettingsApi.discover(connection)
  await module.modelSettingsApi.fetchList(connection)
  await module.modelSettingsApi.test(connection, 'fixture-model')
  await module.modelSettingsApi.save({ connections: [connection] })
  assert.equal(calls.length, 4)
  for (const [, request] of calls) {
    const sent = request.connection || request.connections[0]
    assert.deepEqual(plain(sent.http_headers), { 'X-Workspace': 'fixture-value' })
    assert.deepEqual(plain(sent.extra_body), { thinking: { type: 'enabled' } })
    assert.equal('_http_headers_text' in sent, false)
  }
  assert.throws(() => module.modelSettingsApi.fetchList({ ...connection, _http_headers_text: 'invalid' }), /Invalid custom request options/)
  assert.equal(calls.length, 4)
})

test('advanced editor events reach the typed gateway settings with a password header input', () => {
  const React = require('react')
  const Password = props => React.createElement('input', { ...props, type: 'password' })
  const module = loadTs('CustomRequestOptions.tsx', {
    antd: { Input: { Password } }, '../../i18n': { t: x => x },
    '../../ui': { Row: props => React.createElement('label', {}, props.children), Btn: props => React.createElement('button', props, props.children) },
  })
  let draft = ready()
  const render = () => module.default({ value: draft, onEdit: patch => { draft = { ...draft, ...patch } } })
  const find = (node, label) => {
    if (!node || typeof node !== 'object') return undefined
    if (node.props?.['aria-label'] === label) return node
    for (const child of React.Children.toArray(node.props?.children)) {
      const found = find(child, label)
      if (found) return found
    }
  }
  const header = find(render(), 'HTTP Headers（JSON）')
  assert.equal(header.type, Password)
  header.props.onChange({ target: { value: '{"X-Workspace":"fixture-value"}' } })
  find(render(), '推理强度').props.onChange({ target: { value: 'high' } })
  find(render(), '附加请求参数（JSON）').props.onChange({ target: { value: '{"provider_options":{"thinking":true}}' } })
  const wire = options.wireRequestOptions(custom.toConnection(draft))
  assert.equal(wire.http_headers['X-Workspace'], 'fixture-value')
  assert.equal(wire.reasoning_effort, 'high')
  assert.deepEqual(plain(wire.extra_body), { provider_options: { thinking: true } })
})

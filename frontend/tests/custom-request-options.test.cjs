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


function editor(initial = ready(), component = 'HeaderEditor', clipboardError = false) {
  const React = require('react')
  const states = []; let index = 0; let draft = initial
  const clips = []
  const Password = 'Password'
  const module = loadTs('CustomRequestOptions.tsx', {
    react: { useState: init => { const i = index++; if (!(i in states)) states[i] = typeof init === 'function' ? init() : init; return [states[i], next => { states[i] = typeof next === 'function' ? next(states[i]) : next }] }, useRef: init => { const i = index++; if (!(i in states)) states[i] = { current: init }; return states[i] } },
    antd: { Input: { Password }, Select: 'Select' }, '../../i18n': { t: x => x },
    '../../ui': { Row: 'Row', Btn: 'Btn', Dialog: 'Dialog', Icon: { Close: 'Close', Plus: 'Plus' } },
    __globals: { navigator: { clipboard: { writeText: async text => { if (clipboardError) throw Error('blocked'); clips.push(text) } } } },
  })
  const render = () => { index = 0; return module[component]({ value: draft, onEdit: patch => { draft = { ...draft, ...patch } } }) }
  const nodes = node => !node || typeof node !== 'object' ? [] : [node, ...React.Children.toArray(node.props?.children).flatMap(nodes)]
  const field = label => nodes(render()).find(node => node.props?.['aria-label'] === label)
  const strings = node => typeof node === 'string' ? node : node && typeof node === 'object' ? React.Children.toArray(node.props?.children).map(strings).join('') : ''
  const button = label => nodes(render()).find(node => node.type === 'Btn' && strings(node) === label)
  return { render, nodes: () => nodes(render()), field, button, draft: () => draft, clips, states }
}

test('advanced settings open a dedicated dialog and keep generation controls wired', () => {
  const x = editor(ready(), 'default')
  assert.equal(x.nodes().some(n => n.type === 'Dialog'), false)
  x.button('高级请求设置').props.onClick()
  assert.equal(x.nodes().find(n => n.type === 'Dialog').props.className, 'ac-request-dialog')
  x.field('推理强度').props.onChange({ target: { value: 'high' } })
  x.field('附加请求参数（JSON）').props.onChange({ target: { value: '{"provider_options":{"thinking":true}}' } })
  const wire = options.wireRequestOptions(custom.toConnection(x.draft()))
  assert.equal(wire.reasoning_effort, 'high')
  assert.deepEqual(plain(wire.extra_body), { provider_options: { thinking: true } })
  x.button('关闭').props.onClick()
  assert.equal(x.nodes().some(n => n.type === 'Dialog'), false)
})

test('header rows serialize name/value changes, mask values and keep stable identities after removal', () => {
  const x = editor()
  x.field('请求头名称 1').props.onChange({ target: { value: 'X-Workspace' } })
  assert.equal(x.field('请求头值 1').type, 'Password')
  x.field('请求头值 1').props.onChange({ target: { value: 'fixture-value' } })
  x.field('请求头名称 2').props.onChange({ target: { value: 'X-Title' } })
  x.field('请求头值 2').props.onChange({ target: { value: 'Fixture' } })
  const before = x.nodes().filter(n => n.props?.className === 'ac-request-header-row').map(n => n.key)
  assert.deepEqual(plain(options.wireRequestOptions(x.draft()).http_headers), { 'X-Workspace': 'fixture-value', 'X-Title': 'Fixture' })
  x.field('删除请求头 1').props.onClick()
  assert.equal(x.nodes().find(n => n.props?.className === 'ac-request-header-row').key, before[1])
  assert.deepEqual(plain(options.wireRequestOptions(x.draft()).http_headers), { 'X-Title': 'Fixture' })
  x.field('删除请求头 1').props.onClick()
  assert.deepEqual(plain(options.wireRequestOptions(x.draft()).http_headers), {})
})

test('blank placeholder edits do not clear opaque saved headers; explicit clear does', () => {
  const x = editor({ has_http_headers: true })
  assert.equal(x.button('复制请求头 JSON').props.disabled, true)
  x.button('添加请求头').props.onClick()
  x.field('删除请求头 1').props.onClick()
  assert.equal(options.wireRequestOptions(x.draft()).http_headers, undefined)
  x.button('清空 HTTP Headers').props.onClick()
  assert.deepEqual(plain(options.wireRequestOptions(x.draft()).http_headers), {})
  assert.equal(x.button('复制请求头 JSON').props.disabled, true)
})

test('common headers do not add duplicates and manual duplicates block every request', () => {
  const x = editor()
  x.field('添加常用请求头').props.onChange('User-Agent')
  x.field('添加常用请求头').props.onChange('User-Agent')
  assert.equal(x.nodes().filter(n => n.props?.className === 'ac-request-header-row').length, 3)
  assert.equal(x.field('添加常用请求头').props.options[0].disabled, true)
  x.field('请求头名称 1').props.onChange({ target: { value: 'User-Agent' } })
  assert.equal(options.requestOptionsIssue(x.draft()), 'headers')
  assert.equal(x.button('复制请求头 JSON').props.disabled, true)
  assert.throws(() => options.wireRequestOptions(x.draft()), /Invalid custom request options/)
  x.field('请求头名称 1').props.onChange({ target: { value: 'user-agent' } })
  assert.equal(options.requestOptionsIssue(x.draft()), 'headers')
})

test('JSON import validates before replacing, copies only local values and handles clipboard denial', async () => {
  const x = editor({ has_http_headers: true })
  x.button('导入 JSON').props.onClick()
  assert.equal(x.field('HTTP Headers（JSON）').type, 'Password')
  for (const text of ['bad JSON', '{"Host":"elsewhere"}', '{"X":"one","X":"two"}']) {
    x.field('HTTP Headers（JSON）').props.onChange({ target: { value: text } })
    assert.equal(x.button('导入并替换').props.disabled, true)
    x.button('导入并替换').props.onClick()
    assert.equal(x.draft()._http_headers_text, undefined)
  }
  x.field('HTTP Headers（JSON）').props.onChange({ target: { value: '{"X-Workspace":"fixture-value"}' } })
  x.button('导入并替换').props.onClick()
  assert.deepEqual(plain(options.wireRequestOptions(x.draft()).http_headers), { 'X-Workspace': 'fixture-value' })
  x.button('复制请求头 JSON').props.onClick(); await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(JSON.parse(x.clips[0]), { 'X-Workspace': 'fixture-value' })
  const denied = editor({ _http_headers_text: '{"X":"fixture"}' }, 'HeaderEditor', true)
  denied.button('复制请求头 JSON').props.onClick(); await new Promise(resolve => setImmediate(resolve))
  assert.ok(denied.nodes().some(n => n.props?.role === 'status'))
})

test('flat header parser preserves escaped strings and duplicates before validation', () => {
  const pairs = [{ name: 'X-Workspace', value: 'quote" brace} comma, colon: backslash\\' }, { name: 'X-Title', value: '' }]
  const text = options.headerEntriesText(pairs)
  assert.deepEqual(plain(options.parseHeaderEntries(text)), pairs)
  for (const text of ['{"X":"a","X":"b"}', '{"X":"a","\\u0058":"b"}', '{"X":12,"X":"b"}']) {
    assert.equal(options.requestOptionsIssue({ _http_headers_text: text }), 'headers')
  }
  assert.equal(options.requestOptionsIssue({ _http_headers_text: '{"X":"fake \\\"X\\\": still a value"}' }), null)
})

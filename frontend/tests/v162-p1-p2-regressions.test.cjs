const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const React = require('react')
const { loadTs } = require('./load-ts.cjs')

function flatten(node) {
  if (node == null || typeof node === 'boolean') return []
  if (Array.isArray(node)) return node.flatMap(flatten)
  if (!React.isValidElement(node)) return [node]
  if (typeof node.type === 'function') return [node, ...flatten(node.type(node.props))]
  return [node, ...flatten(node.props.children)]
}

test('extractImportUrl normalizes bare YouTube/Bilibili links and isVideoFile supports extended formats', () => {
  const paste = require('../src/features/studio/pasteStart.ts')
  assert.equal(
    paste.extractImportUrl('www.youtube.com/watch?v=dQw4w9WgXcQ'),
    'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
  )
  assert.equal(
    paste.extractImportUrl('youtu.be/dQw4w9WgXcQ'),
    'https://youtu.be/dQw4w9WgXcQ',
  )
  assert.equal(
    paste.extractImportUrl('看这个视频 b23.tv/Ab12345！'),
    'https://b23.tv/Ab12345',
  )
  assert.equal(paste.extractImportUrl('example.com/not-supported'), null)

  for (const name of ['clip.m4v', 'stream.flv', 'capture.ts', 'camera.wmv', 'raw.mts']) {
    assert.equal(paste.isVideoFile({ name }), true, `${name} should be recognized as video`)
  }
  assert.equal(paste.isVideoFile({ name: 'notes.txt', type: 'text/plain' }), false)
})

test('resolveLanguage maps zh-TW/zh-Hant and legacy Indonesian in/in-ID', () => {
  const { resolveLanguage } = require('../src/i18n/language.ts')
  assert.equal(resolveLanguage('system', ['zh-TW']), 'zh-TW')
  assert.equal(resolveLanguage('system', ['zh-Hant-TW']), 'zh-TW')
  assert.equal(resolveLanguage('system', ['in']), 'id')
  assert.equal(resolveLanguage('system', ['in-ID']), 'id')
  assert.equal(resolveLanguage('system', ['id-ID']), 'id')
})

test('ProviderDetail renders one-click recharge button on insufficient_quota without duplicating ProviderFields link', () => {
  const opened = []
  const i18n = { t: key => key }
  const ui = { Row: 'row', Btn: 'button', StatusDot: 'status', Icon: { Back: () => null, External: () => null } }
  const mocks = {
    react: { ...React, useState: () => [false, () => {}], useRef: initial => ({ current: initial }) },
    antd: { Input: Object.assign(() => null, { Password: 'password' }), Select: 'select' },
    '../../i18n': i18n,
    '../../ui': ui,
    '../../utils/externalLinks': { openExternalLink: url => opened.push(url) },
    '../../analytics/events': { trackSponsorLinkOpened() {} },
    './CustomRequestOptions': { default: () => null },
  }
  const Fields = loadTs('ProviderFields.tsx', mocks).default
  const Detail = loadTs('ProviderDetail.tsx', {
    ...mocks,
    './ProviderFields': { default: Fields },
    '../../components/SpeechRecognitionConfig': { default: () => null },
    './SenseVoiceConfig': { default: () => null },
    './TrialRunPanel': { default: () => null },
  }).default
  const { getProvider } = loadTs('providerPresets.ts')

  const preset = getProvider('deepseek')
  const conn = {
    id: 'conn-ds',
    provider: 'deepseek',
    name: 'DeepSeek',
    base_url: 'https://api.deepseek.com/v1',
    has_key: true,
    validation_status: 'failed',
    validation_error_type: 'insufficient_quota',
  }
  const store = {
    settings: { connections: [conn], analysis: { connection_id: conn.id, model: 'deepseek-chat' } },
    lists: {},
    busy: {},
    listErrors: {},
    testing: false,
    saving: false,
    keyHints: {},
    loadSession: 1,
    update: () => {},
    editConnection: () => {},
    ensureCatalogProvider: () => conn.id,
    testCatalogProvider: async () => {},
    configureProvider: async () => {},
    cancelTrial: () => {},
    discover: async () => {},
    declareModel: () => {},
    selectLocalAsrProvider: () => {},
    setTranscriptionLocal: () => {},
  }

  const detailNodes = flatten(Detail({ preset, m: store, onBack: () => {} }))
  const rechargeBtns = detailNodes.filter(n => n?.props?.['data-testid'] === 'provider-quota-recharge')
  assert.equal(rechargeBtns.length, 1, 'ProviderDetail should render one-click recharge CTA')
  const dupLinks = detailNodes.filter(n => n?.props?.['data-testid'] === 'provider-fields-quota-recharge')
  assert.equal(dupLinks.length, 0, 'ProviderFields should not duplicate recharge link under settings_model')

  rechargeBtns[0].props.onClick()
  assert.equal(opened.length, 1)
  assert.ok(opened[0].includes('deepseek.com'))

  // In home_setup (first-run dialog), ProviderFields itself renders the recharge link.
  const homeNodes = flatten(Fields({
    connection: conn,
    placement: 'home_setup',
    onChoose: () => {},
    onEdit: () => {},
  }))
  const homeLinks = homeNodes.filter(n => n?.props?.['data-testid'] === 'provider-fields-quota-recharge')
  assert.equal(homeLinks.length, 1)
  assert.ok(homeLinks[0].props.href.includes('deepseek.com'))
})

test('CreativeImport pre-intercepts local_transcription preview even when preview was already fetched', () => {
  const src = fs.readFileSync(
    path.join(__dirname, '../src/features/studio/CreativeImport.tsx'),
    'utf8',
  )
  assert.ok(
    src.includes("const previewNeedsLocalAsr = previewUrlRef.current === nextUrl.trim() && preview?.preview_route === 'local_transcription'"),
    'readyToStart must not bypass Whisper gate when URL preview already requires local transcription',
  )
  assert.ok(
    src.includes("if (source === 'link' && preview?.preview_route === 'local_transcription'"),
    'submit must check local_transcription preview outside the !preview branch',
  )
  assert.ok(
    src.includes('.slice(0, 180)'),
    'CreativeImport must clamp project name length below backend max_length=200',
  )
})

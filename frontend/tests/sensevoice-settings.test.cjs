const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const React = require('react')
const { loadTs } = require('./load-ts.cjs')

function flatten(node) {
  if (node == null || typeof node === 'boolean') return []
  if (Array.isArray(node)) return node.flatMap(flatten)
  if (!React.isValidElement(node)) return [node]
  const type = node.type
  if (typeof type === 'function') {
    try { return [node, ...flatten(type(node.props))] } catch { return [node] }
  }
  return [node, ...flatten(node.props?.children)]
}

function textOf(node) {
  return flatten(node).filter(item => typeof item === 'string' || typeof item === 'number').join('')
}

const i18n = { t: (key, values) => {
  if (!values) return key
  return Object.keys(values).reduce((out, name) => out.replace(`{{${name}}}`, String(values[name])), key)
} }

test('DefaultModels switches local ASR engines without a cloud connection', () => {
  let settings = {
    version: 1, saved: false, connections: [],
    analysis: null, vision: null, cover: null,
    transcription: { provider: 'whisper_local', model: 'small', model_source: 'user' },
    cover_enabled: false, allow_send_frame: true, analysis_mode: 'auto', allow_visual_screening: true,
    chunk_size: 5000, min_score_threshold: .7, max_clips_per_collection: 5,
  }
  const updates = []
  // Force the transcription panel open on first useState call (open purpose id).
  let stateCalls = 0
  const DefaultModels = loadTs('DefaultModels.tsx', {
    react: {
      ...React,
      useState: initial => {
        stateCalls += 1
        // First useState in DefaultModels is `open`; return transcription so PurposePanel mounts.
        if (stateCalls === 1) return ['transcription', () => {}]
        return [typeof initial === 'function' ? initial() : initial, () => {}]
      },
      useEffect: () => {},
      useMemo: fn => fn(),
      useRef: value => ({ current: value }),
    },
    'react-i18next': { useTranslation: () => {} },
    '../../i18n': i18n,
    '../../ui': { Icon: { Check: () => null, Help: () => null } },
  }).default
  const tree = DefaultModels({
    settings,
    lists: {},
    onChange: next => { settings = next; updates.push(next) },
  })
  const buttons = flatten(tree).filter(node => node.type === 'button' && node.props?.className === 'ac-purpose-option')
  const sense = buttons.find(node => textOf(node).includes('本机 SenseVoice'))
  assert.ok(sense, 'SenseVoice option must appear in the transcription purpose panel')
  sense.props.onClick()
  assert.equal(settings.transcription.provider, 'sensevoice_local')
  assert.equal(settings.transcription.model, 'SenseVoiceSmall')
  assert.equal(settings.transcription.model_source, 'user')
  const whisperBase = buttons.find(node => textOf(node).includes('本机 Whisper') && textOf(node).includes('base'))
  assert.ok(whisperBase)
  // Closures capture the initial settings snapshot; applyLocalTranscription still yields a local binding.
  whisperBase.props.onClick()
  assert.equal(settings.transcription.provider, 'whisper_local')
  assert.equal(settings.transcription.model, 'base')
  assert.equal(settings.transcription.model_source, 'user')
  assert.ok(updates.length >= 2)
})

test('overview no longer mounts legacy Vision/Cover/Transcription sections', () => {
  const page = fs.readFileSync('src/features/settings/AIModelSettings.tsx', 'utf8')
  assert.equal(/function TranscriptionSection/.test(page), false)
  assert.equal(/function CoverSection/.test(page), false)
  assert.equal(/function VisionSection/.test(page), false)
  assert.equal(/function CurrentAnalysis/.test(page), false)
  assert.match(page, /data-layout="v6/)
  assert.match(page, /<DefaultModels/)
  assert.equal(/<CurrentAnalysis/.test(page), false)
  assert.equal(/<TranscriptionSection/.test(page), false)
  assert.equal(/<CoverSection/.test(page), false)
})

test('SenseVoice detail reuses LocalModelPrepare instead of a new wizard', () => {
  const page = fs.readFileSync('src/features/settings/AIModelSettings.tsx', 'utf8')
  const detail = fs.readFileSync('src/features/settings/ProviderDetail.tsx', 'utf8')
  const source = fs.readFileSync('src/features/settings/SenseVoiceConfig.tsx', 'utf8')
  assert.equal(/LocalModelPrepare/.test(page), false)
  assert.match(detail, /SenseVoiceConfig/)
  assert.match(source, /LocalModelPrepare/)
  assert.equal(/向导|wizard|clipboard/i.test(source), false)

  const Detail = loadTs('ProviderDetail.tsx', {
    '../../i18n': i18n,
    '../../ui': {
      Btn: ({ children, ...props }) => React.createElement('button', props, children),
      StatusDot: ({ label }) => React.createElement('span', { 'data-status': true }, label),
      Icon: { Back: () => null, External: () => null },
      Row: ({ label, children }) => React.createElement('div', null, label, children),
    },
    '../../utils/externalLinks': { openExternalLink: () => {} },
    '../../components/SpeechRecognitionConfig': { default: () => null },
    './ProviderFields': { default: () => null },
    './EndpointProviderSetup': { default: () => null },
    './SenseVoiceConfig': { default: () => React.createElement('div', { 'data-sensevoice': true }, React.createElement('div', { 'data-prepare': 'LocalModelPrepare' })) },
  }).default
  const view = loadTs('providerCatalogView.ts', { '../../i18n': i18n })
  const tree = Detail({
    preset: view.catalogPreset('sensevoice'),
    m: {
      settings: {
        version: 1, saved: false, connections: [],
        analysis: null, vision: null, cover: null,
        transcription: { provider: 'sensevoice_local', model: 'SenseVoiceSmall' },
        cover_enabled: false, allow_send_frame: true, analysis_mode: 'auto', allow_visual_screening: true,
        chunk_size: 5000, min_score_threshold: .7, max_clips_per_collection: 5,
      },
      lists: {}, busy: {}, listErrors: {}, keyHints: {},
      selectLocalAsrProvider: () => {},
      setTranscriptionLocal: () => {},
    },
    asrReady: { sensevoice: true },
    onBack: () => {},
  })
  assert.ok(flatten(tree).some(node => node.props?.['data-sensevoice']))
  assert.ok(flatten(tree).some(node => node.props?.['data-prepare'] === 'LocalModelPrepare'))
})

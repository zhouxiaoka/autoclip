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
  const Select = () => null
  const DefaultModels = loadTs('DefaultModels.tsx', {
    react: { ...React, useState: initial => [initial, () => {}] },
    antd: { Select },
    'react-i18next': { useTranslation: () => {} },
    '../../i18n': i18n,
    '../../ui': { Icon: { Check: () => null, Help: () => null } },
  }).default
  const tree = DefaultModels({
    settings,
    lists: {},
    onChange: next => { settings = next; updates.push(next) },
  })
  const select = flatten(tree).find(node => node.type === Select && node.props['aria-label'] === '语音转字幕')
  const choose = label => select.props.onChange(select.props.options.find(option => option.label === label).value)
  choose('本机 SenseVoice')
  assert.equal(settings.transcription.provider, 'sensevoice_local')
  assert.equal(settings.transcription.model, 'SenseVoiceSmall')
  assert.equal(settings.transcription.model_source, 'user')
  choose('本机 Whisper · base')
  assert.equal(settings.transcription.provider, 'whisper_local')
  assert.equal(settings.transcription.model, 'base')
  assert.equal(settings.transcription.model_source, 'user')
  assert.ok(updates.length >= 2)
})

test('the cover model card can grant and revoke frame uploads independently of the model', () => {
  const DefaultModels = loadTs('DefaultModels.tsx', {
    react: { ...React, useState: initial => [initial, () => {}] },
    antd: { Select: () => null }, 'react-i18next': { useTranslation() {} }, '../../i18n': i18n,
  }).default
  let settings = { connections: [], cover_enabled: true, allow_send_frame: false, cover: { model: 'fixture-image' } }
  const control = () => flatten(DefaultModels({ settings, lists: {}, onChange(next) { settings = next } }))
    .find(node => node?.type === 'input' && node.props.type === 'checkbox')
  assert.equal(control().props.checked, false)
  control().props.onChange({ target: { checked: true } })
  assert.equal(control().props.checked, true)
  control().props.onChange({ target: { checked: false } })
  assert.equal(control().props.checked, false)
  assert.equal(settings.cover.model, 'fixture-image')
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
    react: { ...React, useRef: current => ({ current }) },
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
    './TrialRunPanel': { default: () => null },
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
      lists: {}, busy: {}, listErrors: {}, lastTrialByConnection: {}, keyHints: {},
      selectLocalAsrProvider: () => {},
      setTranscriptionLocal: () => {},
    },
    asrReady: { sensevoice: true },
    onBack: () => {},
  })
  assert.ok(flatten(tree).some(node => node.props?.['data-sensevoice']))
  assert.ok(flatten(tree).some(node => node.props?.['data-prepare'] === 'LocalModelPrepare'))
})

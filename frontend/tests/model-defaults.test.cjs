const { test } = require('node:test')
const assert = require('node:assert/strict')
const { defaultModel, applyModelDefaults, analysisModels } = require('./load-ts.cjs').loadTs('modelDefaults.ts')
const connection = { id: 'main', provider: 'dashscope' }
const models = [
  { id: 'qwen3.8-max', capability: 'multimodal', analysis: true, image: false },
  { id: 'qwen3.8-flash', capability: 'multimodal', analysis: true, image: false },
  { id: 'wanx2.1-t2i-turbo', image: true, analysis: false },
]
const blank = () => ({ analysis: { connection_id: 'main', model: '', capability: 'auto' }, vision: null, cover: null, cover_enabled: false })
test('first setup chooses the analysis model; covers stay on the free local design', () => {
  const value = applyModelDefaults(blank(), connection, models, true)
  assert.equal(value.analysis.model, 'qwen3.8-flash')
  assert.equal(value.analysis.model_source, 'preset')
  assert.equal(value.cover, null, 'no image service is assumed')
  assert.equal(value.cover_enabled, false)
  const chosen = applyModelDefaults({ ...blank(), cover_enabled: true }, connection, models, false)
  assert.equal(chosen.cover.model, 'wanx2.1-t2i-turbo', 'once the user switches to AI covers, the recommended image model is filled')
  assert.equal(chosen.cover.model_source, 'preset')
})
test('refresh never overrides explicit model or frame-only choice', () => {
  const state = blank(); state.analysis.model = 'my-custom-model'
  const value = applyModelDefaults(state, connection, models, false)
  assert.equal(value.analysis.model, 'my-custom-model')
  assert.equal(value.cover, null)
  assert.equal(value.cover_enabled, false)
})
test('refresh from a different provider cannot fill the active selection', () => {
  assert.equal(applyModelDefaults(blank(), { id: 'other', provider: 'dashscope' }, models, true).analysis.model, '')
})
test('independent cover selection remains unchanged', () => {
  const state = blank(); state.cover = { connection_id: 'image-provider', model: 'custom-image' }; state.cover_enabled = true
  const value = applyModelDefaults(state, connection, models, true)
  assert.equal(value.cover.connection_id, 'image-provider')
  assert.equal(value.cover.model, 'custom-image')
})
test('recommendations only select models returned by the service', () => {
  assert.equal(defaultModel('dashscope', [{ id: 'new-model', analysis: true, capability: 'multimodal' }]), 'new-model')
  assert.equal(defaultModel('dashscope', [{ id: 'new-image-protocol', image: true }], true), '')
  assert.equal(defaultModel('infistar', [], false), '')
})
test('88API and Infistar prefer domestic vision models, then fall back to one the account actually has', () => {
  const listed = [
    { id: 'text-only', analysis: true, capability: 'text' },
    { id: 'qwen3.8-max', analysis: true, capability: 'multimodal' },
    { id: 'qwen3.8-flash', analysis: true, capability: 'multimodal' },
    { id: 'doubao-seed-2-1-pro-260628', analysis: true, capability: 'multimodal' },
    { id: 'doubao-seed-2-1-turbo-260628', analysis: true, capability: 'multimodal' },
    { id: 'gemini-3.8-flash', analysis: true, capability: 'multimodal' },
    { id: 'gemini-3.5-flash-lite', analysis: true, capability: 'multimodal' },
    { id: 'gemini-3.5-flash', analysis: true, capability: 'multimodal' },
  ]
  const without = (...ids) => listed.filter(model => !ids.includes(model.id))
  assert.equal(defaultModel('api88', listed), 'qwen3.8-flash')
  assert.equal(defaultModel('api88', without('qwen3.8-flash')), 'qwen3.8-max')
  assert.equal(defaultModel('api88', without('qwen3.8-flash', 'qwen3.8-max')), 'gemini-3.8-flash')
  assert.equal(defaultModel('infistar', listed), 'doubao-seed-2-1-turbo-260628')
  assert.equal(defaultModel('infistar', without('doubao-seed-2-1-turbo-260628')), 'doubao-seed-2-1-pro-260628')
  assert.equal(defaultModel('infistar', without('doubao-seed-2-1-turbo-260628', 'doubao-seed-2-1-pro-260628')), 'qwen3.8-flash')
  assert.equal(defaultModel('infistar', without('doubao-seed-2-1-turbo-260628', 'doubao-seed-2-1-pro-260628', 'qwen3.8-flash', 'qwen3.8-max')), 'gemini-3.5-flash-lite')
  const withoutRecommendations = [
    { id: 'text-only', analysis: true, capability: 'text' },
    { id: 'account-vision', analysis: true, capability: 'multimodal' },
    { id: 'later-vision', analysis: true, capability: 'multimodal' },
  ]
  assert.equal(defaultModel('api88', withoutRecommendations), 'account-vision')
  assert.equal(defaultModel('infistar', withoutRecommendations), 'account-vision')
  assert.equal(defaultModel('api88', [{ id: 'text-only', analysis: true, capability: 'text' }]), 'text-only')
  const visual = applyModelDefaults({
    ...blank(),
    analysis_mode: 'visual',
    vision: { connection_id: 'main', model: '', capability: 'auto' },
  }, { id: 'main', provider: 'api88' }, withoutRecommendations, false)
  assert.equal(visual.analysis.model, 'account-vision')
  assert.equal(visual.vision.model, 'account-vision')
})
test('APIMart orders live models and does not default to the first multimodal id', () => {
  const listed = [
    { id: 'chatgpt-4o-latest', analysis: true, capability: 'multimodal' },
    { id: 'gpt-4-vision-preview', analysis: true, capability: 'multimodal' },
    { id: 'deepseek-v4-flash', analysis: true, capability: 'text' },
    { id: 'gemini-3.8-flash', analysis: true, capability: 'multimodal' },
    { id: 'qwen3.8-flash', analysis: true, capability: 'multimodal' },
  ]
  assert.equal(defaultModel('apimart', listed), 'qwen3.8-flash')
  assert.equal(defaultModel('apimart', listed, false, 'vision'), 'qwen3.8-flash')
  const applied = applyModelDefaults({
    ...blank(),
    vision: { connection_id: 'main', model: '', capability: 'auto' },
  }, { id: 'main', provider: 'apimart' }, listed, false)
  assert.equal(applied.analysis.model, 'qwen3.8-flash')
  assert.equal(applied.vision.model, 'qwen3.8-flash')
  assert.equal(applied.analysis.model_source, 'preset')
})
test('Infistar recommends newly discovered generation models without a static allowlist', () => {
  assert.equal(defaultModel('infistar', [{ id: 'new-image', image: true }], true), 'new-image')
})
test('analysis recommendations follow the selected input mode', () => {
  const mixed = [...models, { id: 'qwen-plus', capability: 'text', analysis: true }]
  const text = applyModelDefaults({ ...blank(), analysis_mode: 'subtitle' }, connection, mixed, false)
  assert.equal(text.analysis.model, 'qwen3.8-flash')
  const visual = applyModelDefaults({ ...blank(), analysis_mode: 'auto' }, connection, mixed, false)
  assert.equal(visual.analysis.model, 'qwen3.8-flash')
  assert.equal(applyModelDefaults({ ...blank(), analysis_mode: 'subtitle' }, connection, models, false).analysis.model, 'qwen3.8-flash')
})
test('ASR defaults exclude unsupported timestamps and preserve explicit choices', () => {
  const state = { ...blank(), transcription: { provider: 'cloud', connection_id: 'main', model: '' } }
  const entries = [{ id: 'filetrans', asr: true, asr_supported: false }, { id: 'qwen-audio-3.0-asr-flash', asr: true, asr_supported: true }]
  assert.equal(applyModelDefaults(state, connection, entries, false).transcription.model, 'qwen-audio-3.0-asr-flash')
  const both = [...entries, { id: 'qwen-audio-3.1-asr-flash', asr: true, asr_supported: true }]
  assert.equal(applyModelDefaults(state, connection, both, false).transcription.model, 'qwen-audio-3.1-asr-flash')
  state.transcription.model = 'custom'
  assert.equal(applyModelDefaults(state, connection, entries, false).transcription.model, 'custom')
  const local = { ...blank(), transcription: { provider: 'whisper_local', model: 'base', model_source: 'user' } }
  assert.equal(applyModelDefaults(local, connection, both, false).transcription.provider, 'whisper_local')
  assert.equal(applyModelDefaults(local, connection, both, false).transcription.model, 'base')
})

test('subtitle and smart mode accept every analysis model; only explicit visual excludes text-only and unknown', () => {
  const mixed = [...models, { id: 'text-model', capability: 'text', analysis: true }, { id: 'unknown-model', capability: null, analysis: true }]
  assert.deepEqual(Array.from(analysisModels(mixed, 'subtitle'), m => m.id), ['qwen3.8-max', 'qwen3.8-flash', 'text-model', 'unknown-model'])
  assert.deepEqual(Array.from(analysisModels(mixed, 'auto'), m => m.id), ['qwen3.8-max', 'qwen3.8-flash', 'text-model', 'unknown-model'])
  assert.deepEqual(Array.from(analysisModels(mixed, 'visual'), m => m.id), ['qwen3.8-max', 'qwen3.8-flash'])
})

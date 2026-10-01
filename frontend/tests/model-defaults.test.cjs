const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), vm = require('node:vm'), ts = require('typescript'), path = require('node:path')
const exportsForTest = {}
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/features/settings/modelDefaults.ts'), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, { exports: exportsForTest })
const { defaultModel, applyModelDefaults, analysisModels } = exportsForTest
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
  assert.equal(value.cover, null, 'no image service is assumed')
  assert.equal(value.cover_enabled, false)
  const chosen = applyModelDefaults({ ...blank(), cover_enabled: true }, connection, models, false)
  assert.equal(chosen.cover.model, 'wanx2.1-t2i-turbo', 'once the user switches to AI covers, the recommended image model is filled')
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
  state.transcription.model = 'custom'
  assert.equal(applyModelDefaults(state, connection, entries, false).transcription.model, 'custom')
})

test('subtitle and smart mode accept every analysis model; only explicit visual excludes text-only and unknown', () => {
  const mixed = [...models, { id: 'text-model', capability: 'text', analysis: true }, { id: 'unknown-model', capability: null, analysis: true }]
  assert.deepEqual(Array.from(analysisModels(mixed, 'subtitle'), m => m.id), ['qwen3.8-max', 'qwen3.8-flash', 'text-model', 'unknown-model'])
  assert.deepEqual(Array.from(analysisModels(mixed, 'auto'), m => m.id), ['qwen3.8-max', 'qwen3.8-flash', 'text-model', 'unknown-model'])
  assert.deepEqual(Array.from(analysisModels(mixed, 'visual'), m => m.id), ['qwen3.8-max', 'qwen3.8-flash'])
})

const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), ts = require('typescript')

const dir = path.join(__dirname, '../src/features/settings')
function load(file, mocks) {
  const exports = {}
  const code = ts.transpileModule(fs.readFileSync(path.join(dir, file), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
  vm.runInNewContext(code, { exports, require: id => { assert.ok(id in mocks, id); return mocks[id] }, crypto: { randomUUID: () => 'uuid' } })
  return exports
}
const providers = {
  PROVIDERS: {
    dashscope: { name: '阿里云百炼' }, openai: { name: 'OpenAI' }, deepseek: { name: 'DeepSeek' },
    compatible: { name: '自定义' }, ollama: { name: 'Ollama', local: { baseUrl: 'http://localhost:11434/v1' } },
  },
}
const defaults = load('modelDefaults.ts', {})
const logic = load('modelSettingsLogic.ts', { './providers': providers, './modelDefaults': defaults })

const plain = x => JSON.parse(JSON.stringify(x))
const conn = (id, provider, extra = {}) => ({ id, name: provider, provider, base_url: '', api_key: '', image_api: 'auto', image_base_url: '', ...extra })
const fresh = () => ({
  version: 1, saved: false,
  connections: [conn('legacy-analysis', 'dashscope')],
  analysis: { connection_id: 'legacy-analysis', model: 'qwen-plus', capability: 'auto' },
  vision: null, cover: null, transcription: { provider: 'whisper_local', model: 'base' },
  cover_enabled: false, allow_send_frame: false, analysis_mode: 'auto', allow_visual_screening: true,
  chunk_size: 5000, min_score_threshold: .7, max_clips_per_collection: 5,
})
const models = [
  { id: 'qwen3.8-flash', capability: 'multimodal', analysis: true, image: false },
  { id: 'qwen-plus', capability: 'text', analysis: true, image: false },
  { id: 'wanx2.1-t2i-turbo', analysis: false, image: true },
]

test('first run: nothing is pre-selected; choosing a provider fills the recommendation, covers stay local', () => {
  const value = logic.prepareLoaded(fresh())
  assert.equal(logic.needsSetup(value), true)
  assert.deepEqual([value.analysis, value.cover, value.vision], [null, null, null], 'no provider is pre-selected on first run')
  assert.equal(value.analysis_mode, 'auto')
  assert.deepEqual([value.cover_enabled, value.allow_send_frame], [false, true], 'covers are designed locally until the user picks an image model')
  assert.deepEqual(plain(logic.saveIssue(value)), { role: 'analysis', reason: 'provider' })
  const chosen = logic.chooseProvider(value, 'analysis', 'dashscope', {}, true)
  assert.equal(chosen.connection.id, 'legacy-analysis', 'the legacy connection of that provider is reused')
  assert.equal(chosen.settings.analysis.model, '')
  const filled = defaults.applyModelDefaults(chosen.settings, chosen.connection, models, true)
  assert.equal(filled.analysis.model, 'qwen3.8-flash')
  assert.equal(filled.cover_enabled, false)
  assert.equal(filled.cover, null)
})

test('setup is not needed once credentials exist, even before the new document is saved', () => {
  const withKey = { ...fresh(), connections: [conn('legacy-analysis', 'dashscope', { has_key: true })] }
  assert.equal(logic.needsSetup(withKey), false)
  assert.equal(logic.prepareLoaded(withKey).analysis.model, 'qwen-plus')
  const local = { ...fresh(), connections: [conn('legacy-analysis', 'ollama')] }
  assert.equal(logic.needsSetup(local), false)
  const custom = { ...fresh(), connections: [conn('legacy-analysis', 'compatible', { base_url: 'http://gw.local/v1' })] }
  assert.equal(logic.needsSetup(custom), false)
})

test('repairing an invalid legacy analysis keeps valid cover and vision assignments', () => {
  const cover = { connection_id: 'image', model: 'image-model', capability: 'auto' }
  const vision = { connection_id: 'vision', model: 'vision-model', capability: 'multimodal' }
  const value = { ...fresh(), analysis: null, cover, vision, cover_enabled: true,
    migration_warnings: ['analysis_configuration_invalid'] }
  assert.deepEqual(plain(logic.prepareLoaded(value)), plain(value))
})

test('text-only models stay eligible in smart mode; only the explicit visual route needs multimodal', () => {
  assert.deepEqual(defaults.analysisModels(models, 'auto').map(m => m.id), ['qwen3.8-flash', 'qwen-plus'])
  assert.deepEqual(defaults.analysisModels(models, 'subtitle').map(m => m.id), ['qwen3.8-flash', 'qwen-plus'])
  assert.deepEqual(defaults.analysisModels(models, 'visual').map(m => m.id), ['qwen3.8-flash'])
  const deepseek = { ...fresh(), connections: [conn('d', 'deepseek', { api_key: 'k' })], analysis: logic.cleanBinding('d') }
  const filled = defaults.applyModelDefaults(deepseek, deepseek.connections[0], [{ id: 'deepseek-flash', capability: 'text', analysis: true }], false)
  assert.equal(filled.analysis.model, 'deepseek-flash')
  assert.equal(logic.isTextOnly(filled, { d: { models: [{ id: 'deepseek-flash', capability: 'text', analysis: true }] } }), true)
})

test('the frame-analysis switch maps to smart/subtitle mode and never keeps a stale vision binding', () => {
  const on = logic.setVisual({ ...fresh(), analysis_mode: 'subtitle', allow_visual_screening: false, vision: { connection_id: 'x', model: 'm', capability: 'auto' } }, true)
  assert.deepEqual([on.analysis_mode, on.allow_visual_screening, on.vision], ['auto', true, null])
  const off = logic.setVisual(on, false)
  assert.deepEqual([off.analysis_mode, off.allow_visual_screening], ['subtitle', false])
})

test('choosing a provider reuses its saved connection and never moves the analysis key to the cover', () => {
  const state = { ...fresh(), connections: [conn('a', 'dashscope', { has_key: true }), conn('b', 'openai', { has_key: true })], analysis: { connection_id: 'a', model: 'qwen-plus', capability: 'auto' }, cover: { connection_id: 'a', model: 'wanx', capability: 'auto' }, cover_enabled: true }
  const toOpenAI = logic.chooseProvider(state, 'analysis', 'openai', {}, true)
  assert.equal(toOpenAI.changed, true)
  assert.equal(toOpenAI.connection.id, 'b')
  assert.equal(toOpenAI.settings.connections.length, 2)
  assert.deepEqual(plain(toOpenAI.settings.cover), { connection_id: 'b', model: '', capability: 'auto' })
  const separateCover = logic.chooseProvider(toOpenAI.settings, 'cover', 'openai', {}, false, p => conn('new', p))
  assert.equal(separateCover.connection.id, 'new', 'cover must not share the analysis connection')
  const same = logic.chooseProvider(toOpenAI.settings, 'analysis', 'openai', {}, false)
  assert.equal(same.changed, false)
})

test('a cached live list fills the recommendation immediately when switching provider', () => {
  const lists = { b: { models: [{ id: 'gpt-5-mini', capability: 'multimodal', analysis: true }, { id: 'dall-e-3', image: true }], source: 'live', preview: false } }
  const result = logic.chooseProvider({ ...fresh(), connections: [conn('a', 'dashscope'), conn('b', 'openai', { has_key: true })] }, 'analysis', 'openai', lists, true)
  assert.equal(result.settings.analysis.model, 'gpt-5-mini')
  assert.equal(result.settings.cover_enabled, false, 'choosing a text provider never switches AI covers on')
})

test('cover follows or separates from the main connection without nested toggles', () => {
  const lists = { 'legacy-analysis': { models, source: 'live' } }
  const separate = logic.setCoverSeparate(fresh(), true, lists, p => conn('cover', p))
  assert.equal(separate.cover.connection_id, 'cover')
  assert.equal(separate.connections.at(-1).provider, 'dashscope')
  const back = logic.setCoverSeparate(separate, false, lists)
  assert.deepEqual(plain(back.cover), { connection_id: 'legacy-analysis', model: 'wanx2.1-t2i-turbo', capability: 'auto' })
  const enabled = logic.setCoverEnabled(fresh(), true, lists)
  assert.equal(enabled.cover_enabled, true)
  assert.equal(enabled.cover.model, 'wanx2.1-t2i-turbo')
})

test('changing an address drops the stored key so it cannot leak to another endpoint', () => {
  const state = { ...fresh(), connections: [conn('a', 'compatible', { has_key: true, base_url: 'https://old/v1' })] }
  const edited = logic.editConnection(state, 'a', { base_url: 'https://new/v1' })
  assert.deepEqual([edited.connections[0].has_key, edited.connections[0].api_key], [false, ''])
  const keyOnly = logic.editConnection(state, 'a', { api_key: 'sk' })
  assert.equal(keyOnly.connections[0].has_key, true)
})

test('save validation reports the first blocking field in page order and prunes blank custom connections', () => {
  assert.deepEqual(plain(logic.saveIssue(fresh())), { role: 'analysis', reason: 'key' })
  const noModel = { ...fresh(), connections: [conn('a', 'dashscope', { api_key: 'k' })], analysis: logic.cleanBinding('a') }
  assert.deepEqual(plain(logic.saveIssue(noModel)), { role: 'analysis', reason: 'model' })
  const ok = { ...noModel, analysis: { connection_id: 'a', model: 'qwen3.8-flash', capability: 'auto' } }
  assert.equal(logic.saveIssue(ok), null)
  const cover = { ...ok, cover_enabled: true, cover: logic.cleanBinding('a') }
  assert.deepEqual(plain(logic.saveIssue(cover)), { role: 'cover', reason: 'model' })
  const cloud = { ...ok, transcription: { provider: 'cloud', connection_id: 'a', model: '' } }
  assert.deepEqual(plain(logic.saveIssue(cloud)), { role: 'transcription', reason: 'model' })
  const doc = logic.forSave({ ...ok, connections: [...ok.connections, conn('blank', 'compatible')], cover: { connection_id: 'a', model: '', capability: 'auto' } })
  assert.deepEqual(doc.connections.map(c => c.id), ['a'])
  assert.equal(doc.cover, null)
})

test('AI covers fall back to frames only when the service has no image model at all', () => {
  const state = { ...fresh(), cover_enabled: true, cover: null, connections: [conn('legacy-analysis', 'deepseek', { api_key: 'k' })] }
  const textOnly = { 'legacy-analysis': { models: [{ id: 'deepseek-flash', capability: 'text', analysis: true }], source: 'live' } }
  const fallback = logic.coverFallback(state, textOnly)
  assert.deepEqual([fallback.cover_enabled, fallback.cover], [false, null])
  assert.equal(logic.saveIssue({ ...fallback, analysis: { connection_id: 'legacy-analysis', model: 'deepseek-flash', capability: 'auto' } }), null)
  const withImages = { 'legacy-analysis': { models, source: 'live' } }
  assert.equal(logic.coverFallback(state, withImages).cover_enabled, true, 'a missing choice with images available is still reported')
  assert.equal(logic.coverFallback(state, {}).cover_enabled, true, 'no list yet: keep the choice')
  const filled = defaults.applyModelDefaults(state, state.connections[0], models, false)
  assert.equal(filled.cover.model, 'wanx2.1-t2i-turbo', 'cover switched on before the list arrived is filled without the first-run flag')
})

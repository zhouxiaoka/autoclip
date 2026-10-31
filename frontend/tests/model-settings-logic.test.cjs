const { test } = require('node:test')
const assert = require('node:assert/strict')
const { loadTs } = require('./load-ts.cjs')
const providers = {
  PROVIDERS: {
    dashscope: { name: '阿里云百炼' }, openai: { name: 'OpenAI' }, deepseek: { name: 'DeepSeek' },
    compatible: { name: '自定义' }, ollama: { name: 'Ollama', local: { baseUrl: 'http://localhost:11434/v1' } },
  },
}
const i18n = { t: (x, v) => (v && v.name ? x.replace('{{name}}', v.name) : x) }
const defaults = loadTs('modelDefaults.ts')
const access = loadTs('providerAccess.ts', {
  '../../i18n': i18n,
  './providers': providers,
})
const urls = loadTs('providerUrl.ts')
const logic = loadTs('modelSettingsLogic.ts', {
  './providers': providers,
  './modelDefaults': defaults,
  './providerAccess': access,
  './providerUrl': urls,
})

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

test('Infistar gateway address survives save and validation without switching domains', () => {
  for (const host of ['infistar.ai', 'www.infistar.ai', 'infistar.cc', 'www.infistar.cc']) {
    const url = `https://${host}/v1`
    const value = { ...fresh(), connections: [conn('legacy-analysis', 'infistar', { base_url: url, api_key: 'fixture' })] }
    const validated = logic.applyValidation(value, 'legacy-analysis', { success: true, normalized_base_url: url })
    assert.equal(logic.forSave(validated).connections[0].base_url, url)
    assert.equal(access.normalizeCompatibleUrl(url, 'infistar').warnings.length, 0)
    assert.equal(access.isConsoleHost(host), false)
  }
})

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

test('vision follow marks a text-only model red without blocking save', () => {
  const lists = { d: { models: [{ id: 'deepseek-flash', capability: 'text', analysis: true }], source: 'live' } }
  const text = {
    ...fresh(),
    connections: [conn('d', 'deepseek', { api_key: 'k' })],
    analysis: { connection_id: 'd', model: 'deepseek-flash', capability: 'auto' },
    analysis_mode: 'auto',
  }
  assert.equal(logic.visionFollowLacksCapability(text, lists), false, 'D7: auto + text does not lack')
  assert.equal(logic.saveIssue(text), null)
  const off = logic.setVisual(text, false)
  assert.equal(logic.visionFollowLacksCapability(off, lists), false)
  assert.equal(logic.visionFollowLacksCapability({ ...text, analysis_mode: 'visual' }, lists), true)
  const visualUnknown = {
    ...fresh(),
    connections: [conn('a', 'compatible', { api_key: 'k', base_url: 'https://gw.example/v1' })],
    analysis: { connection_id: 'a', model: 'alias-x', capability: 'auto' },
    analysis_mode: 'visual',
  }
  assert.equal(logic.visionFollowLacksCapability(visualUnknown, {}), true)
  const multimodal = {
    ...text,
    analysis: { connection_id: 'd', model: 'gpt-4o', capability: 'multimodal' },
  }
  assert.equal(logic.visionFollowLacksCapability(multimodal, lists), false)
  const followVision = {
    ...multimodal,
    vision: { connection_id: 'd', model: 'deepseek-flash', capability: 'text' },
  }
  assert.equal(logic.visionFollowLacksCapability(followVision, lists), false, 'D7: auto + dedicated text vision does not lack')
  assert.equal(logic.visionFollowLacksCapability({ ...followVision, analysis_mode: 'visual' }, lists), true)
  const unresolvedAuto = {
    ...fresh(),
    connections: [conn('o', 'openai', { api_key: 'k' })],
    analysis: { connection_id: 'o', model: 'o3-mini', capability: 'auto' },
    analysis_mode: 'auto',
  }
  assert.equal(logic.visionFollowLacksCapability(unresolvedAuto, {}), false)
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

test('B2: the frame-analysis switch preserves explicit bindings and follow analysis', () => {
  for (const vision of [null, { connection_id: 'legacy-analysis', model: 'my-vision', capability: 'multimodal', model_source: 'user' }]) {
    const state = { ...fresh(), vision, cover: { connection_id: 'legacy-analysis', model: 'my-cover', capability: 'auto', model_source: 'user' }, cover_enabled: true }
    const off = logic.setVisual(state, false)
    assert.deepEqual([off.analysis_mode, off.allow_visual_screening], ['subtitle', false])
    const on = logic.setVisual(off, true)
    assert.deepEqual([on.analysis_mode, on.allow_visual_screening], ['auto', true])
    for (const value of [off, on, logic.forSave(off), logic.forSave(on)]) {
      assert.deepEqual(plain(value.vision), plain(vision))
      assert.deepEqual(plain(value.cover), plain(state.cover))
    }
  }
})

test('choosing a provider reuses its saved connection and preserves an explicit cover binding', () => {
  const state = { ...fresh(), connections: [conn('a', 'dashscope', { has_key: true }), conn('b', 'openai', { has_key: true })], analysis: { connection_id: 'a', model: 'qwen-plus', capability: 'auto' }, cover: { connection_id: 'a', model: 'wanx', capability: 'auto', model_source: 'user' }, cover_enabled: true, cover_follows_analysis: false }
  const toOpenAI = logic.chooseProvider(state, 'analysis', 'openai', {}, true)
  assert.equal(toOpenAI.changed, true)
  assert.equal(toOpenAI.connection.id, 'b')
  assert.equal(toOpenAI.settings.connections.length, 2)
  assert.deepEqual(plain(toOpenAI.settings.cover), plain(state.cover))
  const separateCover = logic.chooseProvider(toOpenAI.settings, 'cover', 'openai', {}, false, p => conn('new', p))
  assert.equal(separateCover.connection.id, 'new', 'cover must not share the analysis connection')
  const same = logic.chooseProvider(toOpenAI.settings, 'analysis', 'openai', {}, false)
  assert.equal(same.changed, false)
})

test('B2: legacy analysis switching keeps explicit vision and cover even on the old analysis connection', () => {
  for (const bindingId of ['a', 'independent']) {
    for (const cover_enabled of [true, false]) {
      const state = { ...fresh(), connections: [conn('a', 'dashscope', { has_key: true }), conn('b', 'openai', { has_key: true }), conn('independent', 'dashscope', { has_key: true })],
        analysis: { connection_id: 'a', model: 'qwen-plus', capability: 'auto' },
        vision: { connection_id: bindingId, model: 'my-vision', capability: 'multimodal', model_source: 'user' },
        cover: { connection_id: bindingId, model: 'my-cover', capability: 'auto', model_source: 'user' }, cover_enabled, cover_follows_analysis: false }
      const switched = logic.chooseProvider(state, 'analysis', 'openai', {}, false).settings
      assert.equal(switched.analysis.connection_id, 'b')
      for (const value of [switched, logic.forSave(logic.setVisual(logic.setVisual(switched, false), true))]) {
        assert.deepEqual(plain(value.vision), plain(state.vision))
        assert.deepEqual(plain(value.cover), plain(state.cover))
      }
      const followed = logic.chooseProvider({ ...state, vision: null }, 'analysis', 'openai', {}, false).settings
      assert.equal(followed.vision, null)
      assert.equal(logic.followedVisionBinding(followed).connection_id, 'b')
    }
  }
})

test('a cached live list fills the recommendation immediately when switching provider', () => {
  const lists = { b: { models: [{ id: 'gpt-5-mini', capability: 'multimodal', analysis: true }, { id: 'dall-e-3', image: true }], source: 'live', preview: false } }
  const result = logic.chooseProvider({ ...fresh(), connections: [conn('a', 'dashscope'), conn('b', 'openai', { has_key: true })] }, 'analysis', 'openai', lists, true)
  assert.equal(result.settings.analysis.model, 'gpt-5-mini')
  assert.equal(result.settings.cover_enabled, false, 'choosing a text provider never switches AI covers on')
})

for (const entry of ['legacy', 'catalog']) {
  for (const cached of [false, true]) {
    for (const follow of [true, false]) {
    test(`X1: ${entry} analysis switch: ${follow ? 'following cover moves' : 'independent cover stays'}, bound vision stays (${cached ? 'cached' : 'delayed'} models)`, () => {
      const view = loadTs('providerCatalogView.ts', { './modelSettingsLogic': logic, './providers': providers, '../../i18n': i18n })
      const connections = [conn('old', 'dashscope', { has_key: true }), conn('new', 'openai', { has_key: true })]
      const oldLists = { old: { models, source: 'live', preview: false } }
      const newModels = [{ id: 'gpt-5-mini', capability: 'multimodal', analysis: true }, { id: 'dall-e-3', image: true }]
      const lists = cached ? { ...oldLists, new: { models: newModels, source: 'live', preview: false } } : oldLists
      for (const source of ['preset', undefined]) {
        for (const enabled of [true, false]) {
          const initial = { ...fresh(), connections, saved: true, analysis: { ...logic.cleanBinding('old'), model: 'qwen-plus' } }
          const state = logic.setCoverEnabled(initial, true, oldLists)
          assert.equal(state.cover_follows_analysis, true, 'turning AI covers on binds a following cover')
          assert.equal(state.cover.model, 'wanx2.1-t2i-turbo')
          state.cover = { ...state.cover, model_source: source }
          state.cover_follows_analysis = follow
          state.vision = { connection_id: 'old', model: 'qwen3.8-flash', capability: 'multimodal', model_source: source }
          state.cover_enabled = enabled
          let switched = entry === 'legacy'
            ? logic.chooseProvider(state, 'analysis', 'openai', lists, false).settings
            : view.assignAnalysis(state, connections[1])
          assert.deepEqual(plain(switched.vision), plain(state.vision))
          if (!cached && follow) assert.equal(switched.cover.connection_id, 'new')
          switched = defaults.applyModelDefaults(switched, connections[1], newModels, false)
          // A late response for the old provider must not move anything back.
          switched = defaults.applyModelDefaults(switched, connections[0], models, false)
          const saved = logic.forSave(logic.setVisual(logic.setVisual(switched, false), true))
          assert.equal(saved.analysis.connection_id, 'new')
          assert.deepEqual(plain(saved.vision), plain(state.vision))
          assert.equal(logic.followedVisionBinding(saved).connection_id, 'old')
          assert.equal(saved.cover_enabled, enabled)
          assert.equal(saved.cover_follows_analysis, follow)
          if (follow) {
            assert.deepEqual(plain(saved.cover), { connection_id: 'new', model: 'dall-e-3', capability: 'auto', model_source: 'preset' })
          } else {
            assert.deepEqual(plain(saved.cover), plain(state.cover))
          }
          assert.equal(state.cover.connection_id, 'old', 'the input settings are unchanged')
        }
      }
    })
    }
  }
}

test('cover follow flag: separate switch, own-provider choice and model pick keep the flag honest', () => {
  const lists = { a: { models, source: 'live' } }
  const base = { ...fresh(), connections: [conn('a', 'dashscope', { has_key: true })], analysis: { ...logic.cleanBinding('a'), model: 'qwen-plus' } }
  const on = logic.setCoverEnabled(base, true, lists)
  assert.equal(on.cover_follows_analysis, true)
  const separate = logic.setCoverSeparate(on, true, lists, p => conn('c', p))
  assert.equal(separate.cover_follows_analysis, false)
  assert.equal(logic.setCoverSeparate(separate, false, lists).cover_follows_analysis, true)
  assert.equal(logic.chooseProvider(on, 'cover', 'openai', {}, false, p => conn('o', p)).settings.cover_follows_analysis, false)
  // E1: an explicit cover model pick is independent even when the cover was following.
  assert.equal(logic.setCoverModel(on, 'a', 'wanx').cover_follows_analysis, false)
  assert.equal(logic.setCoverModel({ ...on, cover_follows_analysis: false }, 'a', 'wanx').cover_follows_analysis, false)
  assert.equal(logic.setCoverModel(separate, 'c', 'wanx').cover_follows_analysis, false)
  // Documents older than the flag: a cover on the analysis connection was the old "follow".
  const legacy = { ...on, cover_follows_analysis: undefined }
  assert.equal(logic.coverFollowsAnalysis(legacy), true)
  assert.equal(logic.coverFollowsAnalysis({ ...legacy, cover: { ...legacy.cover, connection_id: 'c' } }), false)
})

test('cover follows or separates from the main connection without nested toggles', () => {
  const lists = { 'legacy-analysis': { models, source: 'live' } }
  const separate = logic.setCoverSeparate(fresh(), true, lists, p => conn('cover', p))
  assert.equal(separate.cover.connection_id, 'cover')
  assert.equal(separate.connections.at(-1).provider, 'dashscope')
  const back = logic.setCoverSeparate(separate, false, lists)
  assert.deepEqual(plain(back.cover), { connection_id: 'legacy-analysis', model: 'wanx2.1-t2i-turbo', capability: 'auto', model_source: 'preset' })
  const enabled = logic.setCoverEnabled(fresh(), true, lists)
  assert.equal(enabled.cover_enabled, true)
  assert.equal(enabled.cover.model, 'wanx2.1-t2i-turbo')
})

test('edit and save strip surrounding spaces and newlines from the API key', () => {
  const state = { ...fresh(), connections: [conn('a', 'openai', { api_key: '  sk-live  \n' })], analysis: { connection_id: 'a', model: 'gpt-4o-mini', capability: 'auto' } }
  assert.equal(logic.forSave(state).connections[0].api_key, 'sk-live')
  const edited = logic.editConnection(state, 'a', { api_key: '  sk-new  \n' })
  assert.equal(edited.connections[0].api_key, 'sk-new')
  const blank = logic.editConnection(state, 'a', { api_key: '   ' })
  assert.equal(blank.connections[0].api_key, '')
})

test('edit collapses URL spaces; save adds or dedupes /v1 without rejecting', () => {
  const state = { ...fresh(), connections: [conn('a', 'compatible', { base_url: 'https://gw.example' })], analysis: { connection_id: 'a', model: 'gpt-4o-mini', capability: 'auto' } }
  assert.equal(logic.forSave(state).connections[0].base_url, 'https://gw.example/v1')
  const spaced = logic.editConnection(state, 'a', { base_url: '  https://gw.example /v1/  ' })
  assert.equal(spaced.connections[0].base_url, 'https://gw.example/v1/')
  assert.equal(logic.forSave(spaced).connections[0].base_url, 'https://gw.example/v1')
  const dashscope = {
    ...fresh(),
    connections: [conn('b', 'dashscope', { base_url: 'https://llm-x.cn-beijing.maas.aliyuncs.com' })],
    analysis: { connection_id: 'b', model: 'qwen-plus', capability: 'auto' },
  }
  assert.equal(logic.forSave(dashscope).connections[0].base_url, 'https://llm-x.cn-beijing.maas.aliyuncs.com')
})

test('changing an address drops the stored key so it cannot leak to another endpoint', () => {
  const state = { ...fresh(), connections: [conn('a', 'compatible', { has_key: true, base_url: 'https://old/v1' })] }
  const edited = logic.editConnection(state, 'a', { base_url: 'https://new/v1' })
  assert.deepEqual([edited.connections[0].has_key, edited.connections[0].api_key], [false, ''])
  const keyOnly = logic.editConnection(state, 'a', { api_key: 'sk' })
  assert.equal(keyOnly.connections[0].has_key, true)
})

test('save strips key spaces, normalizes a compatible URL, and records a failed check', () => {
  const ok = { ...fresh(), connections: [conn('a', 'compatible', { api_key: '  sk-live  ', base_url: 'https://gw.example' })], analysis: { connection_id: 'a', model: 'gpt-4o-mini', capability: 'auto' } }
  const saved = logic.forSave(ok)
  assert.equal(saved.connections[0].api_key, 'sk-live')
  assert.equal(saved.connections[0].base_url, 'https://gw.example/v1')
  const trimmed = logic.editConnection(ok, 'a', { api_key: '  sk-new  \n' })
  assert.equal(trimmed.connections[0].api_key, 'sk-new')
  assert.equal(trimmed.connections[0].validation_status, 'unchecked')
  const failed = logic.applyValidation(ok, 'a', { success: false, error_type: 'insufficient_quota', normalized_base_url: 'https://gw.example/v1' })
  assert.equal(failed.connections[0].validation_status, 'failed')
  assert.equal(failed.connections[0].validation_error_type, 'insufficient_quota')
  const passed = logic.applyValidation(ok, 'a', { success: true, result: 'ok' })
  assert.equal(passed.connections[0].validation_status, 'ok')
  assert.equal(passed.connections[0].validation_error_type, '')
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
  const browsed = logic.forSave({
    ...ok,
    connections: [
      ...ok.connections,
      conn('sf', 'compatible', { base_url: 'https://api.siliconflow.cn/v1' }),
      conn('ds', 'deepseek'),
    ],
  })
  assert.equal(browsed.connections.map(c => c.id).join(','), 'a,sf')
  const extraKey = logic.forSave({
    ...ok,
    connections: [...ok.connections, conn('ds', 'deepseek', { has_key: true })],
  })
  assert.equal(extraKey.connections.map(c => c.id).includes('ds'), true)
  const local = logic.forSave({
    ...ok,
    connections: [...ok.connections, conn('ollama', 'ollama')],
  })
  assert.equal(local.connections.map(c => c.id).includes('ollama'), true)
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

test('new connections are preset; editing the URL marks user; defaults only fill empty slots as preset', () => {
  assert.equal(logic.newConnection('dashscope').base_url_source, 'preset')
  assert.equal(logic.newConnection('compatible').base_url_source, 'user')
  assert.equal(logic.cleanBinding('a').model_source, 'preset')
  const state = { ...fresh(), connections: [conn('a', 'dashscope', { api_key: 'k', base_url_source: 'preset' })], analysis: logic.cleanBinding('a') }
  const filled = defaults.applyModelDefaults(state, state.connections[0], models, false)
  assert.equal(filled.analysis.model, 'qwen3.8-flash')
  assert.equal(filled.analysis.model_source, 'preset')
  filled.analysis = { ...filled.analysis, model: 'my-pick', model_source: 'user' }
  const again = defaults.applyModelDefaults(filled, filled.connections[0], models, false)
  assert.equal(again.analysis.model, 'my-pick')
  assert.equal(again.analysis.model_source, 'user')
  const edited = logic.editConnection(state, 'a', { base_url: 'https://proxy.example/v1' })
  assert.equal(edited.connections[0].base_url_source, 'user')
  const restored = logic.editConnection(edited, 'a', { base_url: '' })
  assert.equal(restored.connections[0].base_url_source, 'preset')
})

test('separate vision requires a provider, model and credentials before save', () => {
  const state={...fresh(),connections:[conn('a','openai',{api_key:'k'}),conn('v','openai')],analysis:{connection_id:'a',model:'gpt-4o',capability:'auto'}}
  assert.equal(logic.saveIssue(state),null,'follow analysis needs no separate check')
  assert.deepEqual(plain(logic.saveIssue({...state,vision:{connection_id:'missing',model:'gpt-4o'}})),{role:'vision',reason:'provider'})
  assert.deepEqual(plain(logic.saveIssue({...state,vision:{connection_id:'v',model:''}})),{role:'vision',reason:'model'})
  assert.deepEqual(plain(logic.saveIssue({...state,vision:{connection_id:'v',model:'gpt-4o'}})),{role:'vision',reason:'key'})
})

test('D1: setCoverModel on null cover is independent even on analysis connection', () => {
  const state = {
    ...fresh(),
    connections: [conn('a', 'dashscope', { has_key: true }), conn('b', 'openai', { has_key: true })],
    analysis: { connection_id: 'a', model: 'qwen-plus', capability: 'auto' },
    cover: null,
    cover_enabled: false,
    cover_follows_analysis: undefined,
  }
  const picked = logic.setCoverModel(state, 'a', 'wanx')
  assert.equal(picked.cover_follows_analysis, false, 'first cover model pick must not invent follow')
  assert.equal(picked.cover.connection_id, 'a')
  // After save-reopen style: keep independent, switch analysis
  const reopened = { ...picked, cover_follows_analysis: false }
  const switched = defaults.syncFollowingCover(reopened, {
    ...reopened,
    analysis: { connection_id: 'b', model: 'gpt-4o', capability: 'auto' },
  })
  assert.equal(switched.cover.connection_id, 'a')
  assert.equal(switched.cover_follows_analysis, false)
})

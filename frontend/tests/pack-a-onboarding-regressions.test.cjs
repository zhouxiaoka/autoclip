const { test } = require('node:test')
const assert = require('node:assert/strict')
const { loadTs } = require('./load-ts.cjs')

const providers = {
  PROVIDERS: {
    dashscope: { name: '阿里云百炼' }, openai: { name: 'OpenAI' }, deepseek: { name: 'DeepSeek' },
    kimi: { name: 'Kimi' }, compatible: { name: '自定义' },
  },
}
const i18n = { t: (x, v) => (v && v.name ? x.replace('{{name}}', v.name) : x) }
const defaults = loadTs('modelDefaults.ts')
const access = loadTs('providerAccess.ts', { '../../i18n': i18n, './providers': providers })
const urls = loadTs('providerUrl.ts')
const logic = loadTs('modelSettingsLogic.ts', {
  './providers': providers,
  './modelDefaults': defaults,
  './providerAccess': access,
  './providerUrl': urls,
})

test('applyValidation keeps connection ok and analysis unblocked when vision_unsupported occurs on analysis probe in auto mode', () => {
  const settings = {
    version: 1, saved: false,
    connections: [{ id: 'c1', name: 'Kimi', provider: 'kimi', base_url: 'https://api.moonshot.cn/v1', api_key: 'sk-test', image_api: 'auto', image_base_url: '' }],
    analysis: { connection_id: 'c1', model: 'kimi-k3', capability: 'multimodal' },
    vision: null, cover: null, transcription: { provider: 'whisper_local', model: 'base' },
    cover_enabled: false, allow_send_frame: false, analysis_mode: 'auto', allow_visual_screening: true,
    chunk_size: 5000, min_score_threshold: 0.7, max_clips_per_collection: 5,
  }
  const next = logic.applyValidation(
    settings,
    'c1',
    { ok: false, success: false, result: 'failed', error_type: 'vision_unsupported', error_code: 'vision_unsupported' },
    'kimi-k3',
    'analysis',
    true,
  )
  const conn = next.connections[0]
  assert.equal(conn.validation_status, 'ok', 'text analysis probe passed so connection must be ok')
  assert.deepEqual(JSON.parse(JSON.stringify(conn.failed_model_checks)), [{ purpose: 'vision', model: 'kimi-k3' }])
  assert.equal(logic.hasFailedSelection(next), false, 'auto mode must not block analysis when only vision is unsupported')
  assert.equal(logic.hasFailedSelection({ ...next, analysis_mode: 'visual' }), true, 'visual mode still blocks')
})

test('offerPastedKey allows pasting into custom compatible relay after dismissCurrentOffer', async () => {
  const bus = loadTs('keyGuideBus.ts')
  const guide = loadTs('keyGuide.ts')
  const watch = loadTs('keyGuideWatch.ts', {
    './keyGuide': guide,
    './keyGuideBus': bus,
    '../../utils/desktop': { isDesktopMode: async () => false },
  })
  watch.setKeyGuideTargets([{ id: 'openai', hosts: ['api.openai.com'] }])
  const key = 'sk-proj-abcdefghijklmnopqrstuvwxyz1234'

  assert.equal(watch.offerPastedKey(key, 'compatible', 'https://my-relay.example.com/v1'), true)
  await watch.dismissCurrentOffer(key)
  bus.clearOffer()
  assert.equal(
    watch.offerPastedKey(key, 'compatible', 'https://my-relay.example.com/v1'),
    false,
    'dismissed key must not keep blocking paste into custom compatible relay',
  )
})

test('keyGuideBus suppresses clipboard offers while FirstRunSetup connect step is active', () => {
  const bus = loadTs('keyGuideBus.ts')
  assert.equal(typeof bus.setClipboardBannerSuppressed, 'function')
  bus.setClipboardBannerSuppressed(true)
  bus.publishOffer({ key: 'sk-generic-1234567890abcdef', source: 'clipboard', hintedProviderId: null, baseUrl: '', conflict: false })
  assert.equal(bus.currentOffer(), null)
  bus.setClipboardBannerSuppressed(false)
})

test('pickRecommendedTestModel prefers preset analysis candidates over raw models[0]', () => {
  const setup = loadTs('providerModelSetup.ts', {
    './modelKind': loadTs('modelKind.ts'),
    './providerPresets': {
      getProvider: id => id === 'apimart'
        ? { candidates: { analysis: ['deepseek-v4-flash', 'qwen3.8-flash'], vision: [], asr: [], image: [] } }
        : undefined,
    },
  })
  assert.equal(typeof setup.pickRecommendedTestModel, 'function')
  const picked = setup.pickRecommendedTestModel(
    { id: 'c1', provider: 'apimart', catalog_provider_id: 'apimart' },
    {
      source: 'live',
      models: [
        { id: 'legacy-expensive-preview', analysis: true, image: false },
        { id: 'qwen3.8-flash', analysis: true, image: false },
        { id: 'deepseek-v4-flash', analysis: true, image: false },
      ],
    },
  )
  assert.equal(picked, 'deepseek-v4-flash')
})

const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

const providers = {
  PROVIDERS: {
    compatible: { name: '自定义' },
    dashscope: { name: '阿里云百炼' },
  },
}
const urls = loadTs('providerUrl.ts')
const defaults = loadTs('modelDefaults.ts')
const access = loadTs('providerAccess.ts', { '../../i18n': { t: x => x }, './providers': providers })
const logic = loadTs('modelSettingsLogic.ts', { './providers': providers, './modelDefaults': defaults, './providerAccess': access, './providerUrl': urls })
const custom = loadTs('customProvider.ts', { './providerUrl': urls, './modelSettingsLogic': logic, './providerAccess': access })

const fresh = () => ({
  version: 1, saved: false,
  connections: [],
  analysis: null, vision: null, cover: null,
  transcription: { provider: 'whisper_local', model: 'base' },
  cover_enabled: false, allow_send_frame: true, analysis_mode: 'auto', allow_visual_screening: true,
  chunk_size: 5000, min_score_threshold: .7, max_clips_per_collection: 5,
})

test('custom provider is OpenAI-compatible only and needs name, url, and an enabled model', () => {
  assert.equal(custom.CUSTOM_PROTOCOL, 'openai_compatible')
  const blank = custom.emptyDraft()
  assert.equal(blank.protocol, 'openai_compatible')
  assert.equal(custom.draftIssue(blank), 'name')
  const named = { ...blank, name: 'Office' }
  assert.equal(custom.draftIssue(named), 'url')
  const withUrl = { ...named, base_url: 'https://gw.example/v1' }
  assert.equal(custom.draftIssue(withUrl), 'models')
  const ready = custom.addManualModel(withUrl, 'office-llm').draft
  assert.equal(custom.draftIssue(ready), null)
  assert.equal(custom.addManualModel(ready, 'office-llm').issue, 'duplicate')
  assert.equal(custom.addManualModel(ready, '   ').issue, 'model_id')
})

test('scenario checkboxes follow model type and vision', () => {
  const language = custom.emptyOffer('gpt-x')
  assert.equal(custom.scenarioAllowed(language.types, false, 'analysis'), true)
  assert.equal(custom.scenarioAllowed(language.types, false, 'vision'), false)
  assert.equal(custom.scenarioAllowed(language.types, true, 'vision'), true)
  assert.equal(custom.scenarioAllowed(['asr'], false, 'transcription'), true)
  assert.equal(custom.scenarioAllowed(['asr'], false, 'analysis'), false)
  assert.equal(custom.scenarioAllowed(['image'], false, 'cover'), true)
  const stripped = custom.constrainOffer({
    id: 'img', display_name: 'Pic', types: ['image'], vision: true, scenarios: ['analysis', 'cover', 'vision'], enabled: true,
  })
  assert.equal(stripped.vision, false)
  assert.equal(stripped.scenarios.join(','), 'cover')
})

test('discover merge keeps manual models; apply writes a compatible connection without touching existing analysis', () => {
  const started = custom.addManualModel({ ...custom.emptyDraft(), name: 'Office', base_url: 'https://gw.example' }, 'keep-me').draft
  const merged = custom.mergeDiscovered(started, [
    { id: 'keep-me', analysis: true, image: false, capability: 'text' },
    { id: 'new-llm', analysis: true, image: false, capability: 'multimodal' },
  ])
  assert.equal(merged.models.find(m => m.id === 'keep-me').enabled, true)
  assert.equal(merged.models.find(m => m.id === 'new-llm').enabled, false)
  const enabled = custom.toggleModel(merged, 'new-llm', true)
  const applied = custom.applyCustomProvider(fresh(), enabled, 'custom-1')
  assert.equal(applied.connections[0].provider, 'compatible')
  assert.equal(applied.connections[0].name, 'Office')
  assert.equal(applied.connections[0].base_url, 'https://gw.example/v1')
  assert.equal(applied.connections[0].base_url_source, 'user')
  assert.equal(applied.connections[0].custom_models[0].id, 'keep-me')
  assert.equal(applied.analysis.connection_id, 'custom-1')
  assert.equal(applied.analysis.model, 'keep-me')
  assert.equal(applied.analysis.model_source, 'user')
  const already = { ...fresh(), connections: [{ id: 'old', name: 'old', provider: 'dashscope', base_url: '', api_key: 'k', image_api: 'auto', image_base_url: '' }], analysis: { connection_id: 'old', model: 'qwen-plus', capability: 'auto' } }
  const added = custom.applyCustomProvider(already, enabled, 'custom-2')
  assert.equal(added.analysis.connection_id, 'old')
  assert.equal(added.connections.at(-1).id, 'custom-2')
})

test('chat completions suffixes and invalid URLs are rejected before fetch', () => {
  assert.equal(custom.normalizedDraftUrl('https://gw.example/v1/chat/completions'), 'https://gw.example/v1')
  for (const url of ['https://infistar.ai/v1', 'https://generativelanguage.googleapis.com/v1beta', 'https://gw.example/v2/chat/completions', 'https://gw.example/v1/v1']) {
    assert.equal(custom.normalizedDraftUrl(url), urls.normalizeProviderBaseUrl(url, 'compatible'))
  }
  assert.equal(custom.draftUrlIssue(''), 'empty')
  assert.equal(custom.draftUrlIssue('not-a-url'), 'invalid')
  assert.equal(custom.draftUrlIssue('https://gw.example/v1'), null)
})

test('custom base URLs reject console hosts and embedded credentials', () => {
  assert.equal(custom.draftUrlIssue('https://user:pass@gw.example/v1'), 'invalid')
  assert.equal(custom.draftUrlIssue('https://user@gw.example/v1'), 'invalid')
  assert.equal(custom.draftUrlIssue('https://platform.openai.com/v1'), 'invalid')
  assert.equal(custom.draftUrlIssue('https://platform.openai.com/api-keys'), 'invalid')
  assert.equal(custom.draftUrlIssue('https://bailian.console.aliyun.com'), 'invalid')
  assert.equal(custom.draftUrlIssue('https://aistudio.google.com'), 'invalid')
  assert.equal(custom.draftUrlIssue('https://api.openai.com/v1'), null)
  assert.equal(custom.draftUrlIssue('https://gw.example/v1'), null)
})

test('custom dialog and first-run source have no clipboard-paste control', () => {
  const files = [
    'AddCustomProviderDialog.tsx',
    'FirstRunSetup.tsx',
    'customProvider.ts',
    'firstRunGuidance.ts',
  ]
  for (const name of files) {
    const source = fs.readFileSync(path.join(__dirname, '../src/features/settings', name), 'utf8')
    assert.equal(/从剪贴板粘贴|pasteFromClipboard|navigator\.clipboard/i.test(source), false, name)
  }
})

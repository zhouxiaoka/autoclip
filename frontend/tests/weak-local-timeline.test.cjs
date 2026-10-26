const { test } = require('node:test')
const assert = require('node:assert/strict')
const React = require('react')
const { loadTs } = require('./load-ts.cjs')

const { isKnownWeakLocalTimelineModel, analysisUsesWeakLocalTimelineModel } = loadTs('weakLocalTimeline.ts')

const cases = [
  ['ollama', 'qwen2.5:7b', 'http://127.0.0.1:11434/v1', true],
  ['Ollama', 'Qwen2.5-7B-Instruct', null, true],
  ['lmstudio', 'llama3.1:8b', null, true],
  ['ollama', 'phi3:mini', null, true],
  ['compatible', 'qwen2.5:7b', 'http://localhost:8000/v1', true],
  ['openai', 'qwen2.5:7b', 'http://192.168.1.8:11434/v1', true],
  ['ollama', 'qwen2.5:14b', null, false],
  ['ollama', 'qwen2.5:32b', null, false],
  ['ollama', 'nomic-embed-text', null, false],
  ['dashscope', 'qwen2.5:7b', 'https://dashscope.aliyuncs.com/compatible-mode/v1', false],
  ['openai', 'gpt-4o-mini', 'https://api.openai.com/v1', false],
  ['compatible', 'qwen2.5:7b', 'https://example.com/v1', false],
  ['ollama', 'mixtral:8x7b', null, false],
]
for (const [provider, model, baseUrl, weak] of cases) {
  test(`${provider} ${model || '(empty)'} weak=${weak}`, () => {
    assert.equal(isKnownWeakLocalTimelineModel(provider, model, baseUrl), weak)
  })
}

function flatten(node) {
  if (node == null || typeof node === 'boolean') return []
  if (Array.isArray(node)) return node.flatMap(flatten)
  if (!React.isValidElement(node)) return [node]
  if (typeof node.type === 'function') {
    try { return [node, ...flatten(node.type(node.props))] } catch { return [node] }
  }
  return [node, ...flatten(node.props?.children)]
}
function textOf(node) {
  return flatten(node).filter(item => typeof item === 'string' || typeof item === 'number').join('')
}

function settingsFor(provider, model, baseUrl) {
  return {
    version: 1, saved: true,
    connections: [{ id: 'main', name: provider, provider, base_url: baseUrl || '' }],
    analysis: { connection_id: 'main', model, capability: 'text', model_source: 'user' },
    vision: null, cover: null, transcription: null,
    cover_enabled: false, allow_send_frame: false, analysis_mode: 'subtitle', allow_visual_screening: false,
    chunk_size: 5000, min_score_threshold: 0.7, max_clips_per_collection: 5,
  }
}

function renderModels(settings) {
  const DefaultModels = loadTs('DefaultModels.tsx', {
    react: { ...React, useState: initial => [initial, () => {}], useEffect: () => {}, useMemo: fn => fn(), useRef: value => ({ current: value }) },
    'react-i18next': { useTranslation: () => {} },
    '../../i18n': { t: key => key },
    '../../ui': { Icon: { Check: () => null, Help: () => null } },
  }).default
  return DefaultModels({ settings, lists: {}, onChange() {} })
}

test('the analysis slot warns for qwen2.5:7b and still leaves the model selectable', () => {
  const tree = renderModels(settingsFor('ollama', 'qwen2.5:7b', 'http://127.0.0.1:11434/v1'))
  const text = textOf(tree)
  assert.match(text, /这个本地模型往往剪不出片段，建议换更大的或云端模型/)
  assert.doesNotMatch(text, /结构化时间区间/)
  const card = flatten(tree).find(node => node?.props?.className === 'ac-purpose-card' && textOf(node).includes('精彩片段分析'))
  assert.ok(card)
  assert.equal(card.props.disabled, undefined)
  assert.equal(analysisUsesWeakLocalTimelineModel(settingsFor('ollama', 'qwen2.5:32b')), false)
  assert.doesNotMatch(textOf(renderModels(settingsFor('ollama', 'qwen2.5:32b'))), /往往剪不出片段/)
  assert.doesNotMatch(textOf(renderModels(settingsFor('dashscope', 'qwen2.5:7b', 'https://dashscope.aliyuncs.com/compatible-mode/v1'))), /往往剪不出片段/)
})

test('a connected cloud model is the one home-card replacement; a lone 7b is not', () => {
  const { recommendTimelineReplacement } = loadTs('timelineReplacement.ts', { '../../i18n': { t: key => key } })
  const base = {
    version: 1, saved: true, vision: null, cover: null, transcription: null,
    cover_enabled: false, allow_send_frame: false, analysis_mode: 'subtitle', allow_visual_screening: false,
    chunk_size: 5000, min_score_threshold: 0.7, max_clips_per_collection: 5,
  }
  const onlySmall = recommendTimelineReplacement({
    ...base,
    connections: [{ id: 'ollama', name: 'Ollama', provider: 'ollama', base_url: 'http://127.0.0.1:11434/v1' }],
    analysis: { connection_id: 'ollama', model: 'qwen2.5:7b', capability: 'text', model_source: 'user' },
  })
  assert.equal(onlySmall, null)
  const cloud = recommendTimelineReplacement({
    ...base,
    connections: [
      { id: 'ollama', name: 'Ollama', provider: 'ollama', base_url: 'http://127.0.0.1:11434/v1' },
      { id: 'ds', name: 'DeepSeek', provider: 'deepseek', base_url: 'https://api.deepseek.com', has_key: true, validation_status: 'ok' },
    ],
    analysis: { connection_id: 'ollama', model: 'qwen2.5:7b', capability: 'text', model_source: 'user' },
  })
  assert.equal(cloud.displayName, 'DeepSeek')
  assert.equal(cloud.model, 'deepseek-flash')
  assert.equal(cloud.connectionId, 'ds')
  const larger = recommendTimelineReplacement({
    ...base,
    connections: [{
      id: 'ollama', name: 'Ollama', provider: 'ollama', base_url: 'http://127.0.0.1:11434/v1',
      enabled_model_ids: ['qwen2.5:7b', 'qwen2.5:32b', 'qwen2.5:14b'],
    }],
    analysis: { connection_id: 'ollama', model: 'qwen2.5:7b', capability: 'text', model_source: 'user' },
  })
  assert.equal(larger.displayName, 'qwen2.5:14b')
  assert.equal(larger.model, 'qwen2.5:14b')
  const unchecked = recommendTimelineReplacement({
    ...base,
    connections: [
      { id: 'ollama', name: 'Ollama', provider: 'ollama', base_url: 'http://127.0.0.1:11434/v1' },
      { id: 'ds', name: 'DeepSeek', provider: 'deepseek', base_url: 'https://api.deepseek.com', has_key: true, validation_status: 'unchecked' },
    ],
    analysis: { connection_id: 'ollama', model: 'qwen2.5:7b', capability: 'text', model_source: 'user' },
  })
  assert.equal(unchecked, null)
})

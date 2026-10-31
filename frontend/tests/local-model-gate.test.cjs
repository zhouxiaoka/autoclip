const { test } = require('node:test')
const assert = require('node:assert/strict')
const { loadTs } = require('./load-ts.cjs')

const i18n = { t: (x, v) => {
  if (!v) return x
  return Object.keys(v).reduce((s, k) => s.replace(`{{${k}}}`, String(v[k])), x)
}}
const gate = loadTs('localModelGate.ts')
const providers = loadTs('providers.ts', { '../../i18n': i18n })

test('belowLocalAnalysisGate uses params and context floors', () => {
  assert.equal(gate.belowLocalAnalysisGate({ params_b: 3, context_tokens: 8192 }), true)
  assert.equal(gate.belowLocalAnalysisGate({ params_b: 7, context_tokens: 4096 }), true)
  assert.equal(gate.belowLocalAnalysisGate({ params_b: 7, context_tokens: 8192 }), false)
  assert.equal(gate.belowLocalAnalysisGate({ id: 'tinyllama:1.1b' }), true)
  assert.equal(gate.belowLocalAnalysisGate({ id: 'qwen2.5:14b' }), false)
})

test('localModelSizeLabel shows 未知 for LM Studio without size', () => {
  assert.equal(gate.localModelSizeLabel({ id: 'mystery-chat' }, 'lmstudio'), '未知')
  assert.match(gate.localModelSizeLabel({ id: 'qwen2.5:7b', context_tokens: 32768 }, 'ollama'), /7B/)
  assert.match(gate.localModelSizeLabel({ id: 'qwen2.5:7b', context_tokens: 32768 }, 'ollama'), /32k/)
})

test('contextHintFor cites params and context when known', () => {
  const warn = providers.contextHintFor('ollama', 'http://127.0.0.1:11434/v1', { params_b: 3.8, context_tokens: 4096 })
  assert.match(warn, /3\.8B/)
  assert.match(warn, /大概率解析失败/)
  const ok = providers.contextHintFor('ollama', 'http://127.0.0.1:11434/v1', { params_b: 14, context_tokens: 32768 })
  assert.match(ok, /14B/)
  assert.match(ok, /≥7B/)
})

test('legacy contextHintFor without size still returns preset hint', () => {
  assert.match(providers.contextHintFor('ollama'), /16384/)
})

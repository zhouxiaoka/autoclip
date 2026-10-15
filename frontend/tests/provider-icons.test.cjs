const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

test('catalog maps major providers to OhMyGame-style SVG icons', () => {
  const source = fs.readFileSync(path.join(__dirname, '../src/features/settings/providerIcons.ts'), 'utf8')
  for (const id of ['openai', 'deepseek', 'gemini', 'grok', 'ollama', 'lmstudio', 'openrouter', 'siliconflow', 'dashscope', 'azure-openai', 'kimi', 'glm', 'seed']) {
    assert.match(source, new RegExp(`['"]?${id}['"]?\\s*:`), id)
  }
  const dir = path.join(__dirname, '../src/assets/providers')
  const files = fs.readdirSync(dir).filter(f => f.endsWith('.svg'))
  assert.ok(files.length >= 20, `expected many svgs, got ${files.length}`)
  assert.ok(files.includes('openai.svg'))
  assert.ok(files.includes('deepseek.svg'))
})

test('ProviderCatalog renders img mark when icon exists', () => {
  const source = fs.readFileSync(path.join(__dirname, '../src/features/settings/ProviderCatalog.tsx'), 'utf8')
  assert.match(source, /providerIcon/)
  assert.match(source, /function ProviderMark/)
  assert.match(source, /has-icon/)
})

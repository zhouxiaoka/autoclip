const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { runInSandbox } = require('./vm-sandbox.cjs')
const ts = require('typescript')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')

function renderCard(status, error, progressMessage, extra = {}, navigate = () => {}, props = {}) {
  const stubs = {
    '../i18n': { t: (key, values) => values ? String(key).replace(/\{\{\s*(\w+)\s*\}\}/g, (_, name) => values[name] == null ? '' : String(values[name])) : key },
    'react-i18next': { useTranslation: () => ({}) },
    'react-router-dom': { useNavigate: () => navigate },
    '../services/api': { projectApi: {} },
    '../features/studio/api': { studioApi: {} },
    './UnifiedStatusBar': { UnifiedStatusBar: () => null },
    './FeedbackDialog': { __esModule: true, default: () => null },
    '../stores/useSimpleProgressStore': {
      useSimpleProgressStore: (select) => select({ getProgress: () => ({ message: progressMessage }) }),
    },
    '../ui': { Btn: ({ children, onClick }) => { if (extra.onButton) extra.onButton(children, onClick); return React.createElement('button', {}, children) }, Dialog: () => null, StatusDot: ({ label }) => React.createElement('span', {}, label), Icon: { Play: () => null, Refresh: () => null, Trash: () => null } },
  }
  function load(file) {
    const module = { exports: {} }
    const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, esModuleInterop: true },
    }).outputText
    runInSandbox(code, {
      module, exports: module.exports, console: { log() {} },
      require: (id) => {
        if (id in stubs) return stubs[id]
        if (id === '@event-catalog' || id === '@failure-messages') {
          const data = JSON.parse(fs.readFileSync(path.join(__dirname, id === '@event-catalog' ? '../../backend/core/event_catalog.json' : '../../backend/core/failure_messages.json'), 'utf8'))
          return { default: data, __esModule: true }
        }
        if (id.startsWith('.')) return load(path.resolve(path.dirname(file), `${id}.ts`))
        return require(id)
      },
    })
    return module.exports
  }
  const Card = load(path.join(__dirname, '../src/components/ProjectCard.tsx')).default
  return renderToStaticMarkup(React.createElement(Card, {
    project: { id: 'test', name: 'Example', status, error_message: error, created_at: '2026-09-30', ...(extra.project || {}) },
    onDelete() {},
    ...props,
  }))
}

const WEAK = '当前本地模型无法返回可用时间线'
const LEGACY = '时间线模型回复没有有效时间区间（82 个话题，14 个字幕块）。 这个模型经常无法返回可用的时间线，自动重试已经用完。请改用云端模型，或更大、能返回结构化时间区间的模型。这一步尚未进入评分或最短时长筛选。'

test('#428 home card with a replacement stays on the card and offers switch-and-retry', () => {
  const visited = []
  const buttons = {}
  const switched = []
  const html = renderCard('failed', WEAK, null, {
    project: { error_code: 'invalid_response', name: '马大帅访谈' },
    onButton: (label, onClick) => { buttons[label] = onClick },
  }, to => visited.push(to), { replacement: { displayName: 'DeepSeek' }, onSwitchAndRetry: id => switched.push(id) })
  assert.match(html, /失败/)
  assert.match(html, /当前本地模型无法返回可用时间线/)
  assert.match(html, /建议换用/)
  assert.match(html, /<strong>DeepSeek<\/strong>/)
  assert.doesNotMatch(html, /82|话题|字幕块|自动重试|经常无法/)
  assert.equal(html.includes('href="/project/'), false)
  buttons['切换并重试']()
  assert.deepEqual(switched, ['test'])
  buttons['其他模型']()
  assert.deepEqual(visited, ['/settings?section=analysis'])
})

test('#428 home card without a replacement offers configure, and does not open the project', () => {
  const visited = []
  const buttons = {}
  const html = renderCard('failed', LEGACY, null, {
    project: { error_code: 'invalid_response' },
    onButton: (label, onClick) => { buttons[label] = onClick },
  }, to => visited.push(to))
  assert.match(html, /当前本地模型无法返回可用时间线/)
  assert.doesNotMatch(html, /82|话题|字幕块/)
  assert.equal(buttons['切换并重试'], undefined)
  buttons['去配置模型']()
  assert.deepEqual(visited, ['/settings?section=analysis'])
  assert.equal(typeof buttons['重试'], 'function')
})

test('a generic invalid timeline does not add model settings on the project card', () => {
  const buttons = {}
  const error = '时间线模型回复没有有效时间区间（1 个话题，1 个字幕块）。 请换用能稳定返回结构化时间线的模型后重试；本地模型需支持当前字幕长度。这一步尚未进入评分或最短时长筛选。'
  renderCard('failed', error, null, {
    project: { error_code: 'invalid_response' },
    onButton: (label, onClick) => { buttons[label] = onClick },
  })
  assert.equal(buttons['模型设置'], undefined)
})

test('a quota failure is not rewritten into an invalid-key prompt', () => {
  const messages = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../backend/core/failure_messages.json'), 'utf8'))
  const html = renderCard('failed', messages.insufficient_quota, null, {
    project: { error_code: 'llm_auth_invalid', upstream_error_type: 'insufficient_quota' },
  })
  assert.match(html, /充值或更换令牌/)
  assert.doesNotMatch(html, /API Key 无效/)
})

test('failed project shows the persisted reason even after progress state is lost', () => {
  const html = renderCard('error', 'Whisper 模型文件缺失或不完整。')
  assert.match(html, /role="alert"/)
  assert.match(html, /Whisper 模型文件缺失或不完整。/)
})

test('progress failure remains visible before project refresh and is escaped', () => {
  const html = renderCard('failed', null, 'failed <script>alert(1)</script>')
  assert.match(html, /failed &lt;script&gt;/)
  assert.doesNotMatch(html, /<script>/)
})

test('successful retry does not show a stale failure', () => {
  const html = renderCard('completed', 'stale failure', 'old progress')
  assert.doesNotMatch(html, /stale failure|old progress|role="alert"/)
})

test('restart-interrupted automatic project shows its reason and regenerates from the project page (RC156 #13)', async () => {
  const visited = []
  const buttons = {}
  const restart = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../backend/core/failure_messages.json'), 'utf8')).service_restarted
  const html = renderCard('failed', restart, null, {
    project: { error_code: 'service_restarted', settings: { smart_import: { auto_start: true }, studio_generation_status: 'failed' } },
    onButton: (label, onClick) => { buttons[label] = onClick },
  }, (to) => visited.push(to))
  assert.match(html, /role="alert"/)
  assert.ok(html.includes(restart))
  assert.match(html, />重新生成</)
  await buttons['重新生成']()
  assert.deepEqual(visited, ['/project/test'])
})

test('managed project without a finished generation still reopens import review', async () => {
  const visited = []
  const buttons = {}
  renderCard('failed', '导入失败', null, {
    project: { settings: { smart_import: { auto_start: false } } },
    onButton: (label, onClick) => { buttons[label] = onClick },
  }, (to) => visited.push(to))
  await buttons['重试']()
  assert.deepEqual(visited, ['/import/test'])
})

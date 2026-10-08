const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')

function renderCard(status, error, progressMessage, extra = {}, navigate = () => {}) {
  const stubs = {
    '../i18n': { t: (key) => key },
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
    vm.runInNewContext(code, {
      module, exports: module.exports, console: { log() {} },
      require: (id) => {
        if (id in stubs) return stubs[id]
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
  }))
}

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
  const html = renderCard('failed', '服务已重启，请重新生成', null, {
    project: { error_code: 'service_restarted', settings: { smart_import: { auto_start: true }, studio_generation_status: 'failed' } },
    onButton: (label, onClick) => { buttons[label] = onClick },
  }, (to) => visited.push(to))
  assert.match(html, /role="alert"/)
  assert.match(html, /服务已重启，请重新生成/)
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

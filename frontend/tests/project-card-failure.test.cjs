const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { runInSandbox } = require('./vm-sandbox.cjs')
const ts = require('typescript')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')

function renderCard(status, error, progressMessage, extra = {}, navigate = () => {}, props = {}) {
  const opened = []
  const stubs = {
    '../i18n': { t: (key, values) => values ? String(key).replace(/\{\{\s*(\w+)\s*\}\}/g, (_, name) => values[name] == null ? '' : String(values[name])) : key },
    'react-i18next': { useTranslation: () => ({}) },
    'react-router-dom': { useNavigate: () => navigate },
    '../services/api': { projectApi: {} },
    '../features/studio/api': { studioApi: {} },
    '../utils/externalLinks': { openExternalLink: (url) => { opened.push(url); if (extra.onExternal) extra.onExternal(url) } },
    './UnifiedStatusBar': { UnifiedStatusBar: () => null },
    './FeedbackDialog': { __esModule: true, default: () => null },
    '../features/studio/SwitchModelDialog': { __esModule: true, default: () => null },
    '../stores/useSimpleProgressStore': {
      useSimpleProgressStore: (select) => select({ getProgress: () => ({ message: progressMessage }) }),
    },
    '../ui': { Btn: ({ children, onClick, variant }) => { if (extra.onButton) extra.onButton(children, onClick, variant); return React.createElement('button', {}, children) }, Dialog: () => null, StatusDot: ({ label }) => React.createElement('span', {}, label), Icon: { Play: () => null, Refresh: () => null, Trash: () => null } },
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
        if (id === '@event-catalog' || id === '@failure-messages' || id === '@provider-presets' || id === '@provider-quality') {
          const file = id === '@event-catalog' ? '../../backend/core/event_catalog.json'
            : id === '@failure-messages' ? '../../backend/core/failure_messages.json'
            : id === '@provider-presets' ? '../../backend/presets/provider_presets.json'
            : '../../backend/presets/provider_quality.json'
          const data = JSON.parse(fs.readFileSync(path.join(__dirname, file), 'utf8'))
          return { default: data, __esModule: true }
        }
        if (id.startsWith('.')) {
          const base = path.resolve(path.dirname(file), id)
          const candidate = [base, `${base}.ts`, `${base}.tsx`, `${base}.js`].find(p => fs.existsSync(p))
          if (!candidate) throw new Error('cannot resolve ' + id + ' from ' + file)
          return load(candidate)
        }
        return require(id)
      },
    })
    return module.exports
  }
  const Card = load(path.join(__dirname, '../src/components/ProjectCard.tsx')).default
  if (extra) extra.opened = opened
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

test('B2 home card: whisper gate codes lead with 安装转写 and keep retry secondary', () => {
  for (const code of ['whisper_not_installed', 'whisper_install_failed', 'whisper_model_missing', 'whisper_model_failed']) {
    const visited = []
    const buttons = {}
    renderCard('failed', '本地转写还没装好', null, {
      project: { error_code: code },
      onButton: (label, onClick, variant) => { buttons[label] = { onClick, variant } },
    }, to => visited.push(to))
    assert.equal(buttons['安装转写'].variant, 'cta', code)
    assert.equal(buttons['重试'].variant, 'text', code)
    assert.equal(buttons['转写设置'], undefined, code)
    buttons['安装转写'].onClick()
    assert.deepEqual(visited, ['/settings?section=speech'])
  }
  const buttons = {}
  renderCard('failed', '请求超时', null, {
    project: { error_code: 'timeout' },
    onButton: (label, onClick, variant) => { buttons[label] = { onClick, variant } },
  })
  assert.equal(buttons['安装转写'], undefined)
  assert.equal(buttons['重试'].variant, 'text')
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


test('X2 home card: whisper gates lead with install_asr CTA 安装转写', () => {
  for (const code of ['whisper_not_installed', 'whisper_install_failed', 'whisper_model_missing', 'whisper_model_failed']) {
    const visited = []
    const buttons = {}
    renderCard('failed', '本地转写还没装好', null, {
      project: { error_code: code },
      onButton: (label, onClick, variant) => { buttons[label] = { onClick, variant } },
    }, to => visited.push(to))
    assert.equal(buttons['安装转写'].variant, 'cta', code)
    assert.equal(buttons['换模型重试'], undefined, code)
    buttons['安装转写'].onClick()
    assert.deepEqual(visited, ['/settings?section=speech'])
  }
})

test('X2 home card: switchable upstream + ≥2 connections offers 换模型重试', () => {
  const switched = []
  const buttons = {}
  const options = [
    { connectionId: 'c1', model: 'm1', displayName: 'A', providerId: 'api88', success_rate: 0.9 },
    { connectionId: 'c2', model: 'm2', displayName: 'B', providerId: 'infistar', success_rate: 0.8 },
  ]
  renderCard('failed', '请求过多', null, {
    project: { error_code: 'rate_limited', upstream_error_type: 'rate_limited' },
    onButton: (label, onClick, variant) => { buttons[label] = { onClick, variant } },
  }, () => {}, {
    connectionCount: 2,
    switchOptions: options,
    onSwitchAndRetry: (id, choice) => { switched.push({ id, choice }) },
  })
  assert.equal(buttons['换模型重试'].variant, 'cta')
  assert.equal(typeof buttons['重试'].onClick, 'function')
  // Without a real dialog stub capturing open, openSwitchDialog sets switchOpen;
  // SwitchModelDialog is stubbed null so confirm path is covered via onSwitchAndRetry with choice in HomePage.
  buttons['换模型重试'].onClick()
})

test('X2 home card: switchable upstream + 1 connection offers 去设置 (add provider)', () => {
  const visited = []
  const buttons = {}
  renderCard('failed', '上游超时', null, {
    project: { error_code: 'timeout', upstream_error_type: 'timeout' },
    onButton: (label, onClick, variant) => { buttons[label] = { onClick, variant } },
  }, to => visited.push(to), { connectionCount: 1 })
  assert.equal(buttons['去设置'].variant, 'cta')
  assert.equal(buttons['换模型重试'], undefined)
  buttons['去设置'].onClick()
  assert.deepEqual(visited, ['/settings?section=analysis'])
})

test('X2/X3 home card: insufficient_quota + sponsor offers 去 88API 充值', () => {
  const visited = []
  const buttons = {}
  const extra = {
    project: { error_code: 'provider_error', upstream_error_type: 'insufficient_quota' },
    onButton: (label, onClick, variant) => { buttons[label] = { onClick, variant } },
  }
  renderCard('failed', '余额不足', null, extra, to => visited.push(to), { analysisProvider: 'api88' })
  assert.equal(buttons['去 88API 充值'].variant, 'cta')
  buttons['去 88API 充值'].onClick()
  assert.deepEqual(visited, [])
  assert.ok(extra.opened.some(url => url.includes('88api.ai')))
})


test('failed card with empty/bare message still shows step-level human copy (#491 tip soft)', () => {
  const messages = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../backend/core/failure_messages.json'), 'utf8'))
  for (const [error, code] of [[null, 'service_restarted'], ['', 'timeout'], ['错误', 'provider_error'], ['失败', null]]) {
    const html = renderCard('failed', error, null, { project: { error_code: code } })
    assert.match(html, /role="alert"/, String(error))
    assert.match(html, /[下载转写分析制作]：/, String(error))
    assert.doesNotMatch(html, /role="alert"[^>]*>\s*<span[^>]*>错误<\/span>/, String(error))
    if (code === 'service_restarted') assert.ok(html.includes(messages.service_restarted))
  }
})

test('failed card with catalog message keeps step prefix without rewriting the reason', () => {
  const messages = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../backend/core/failure_messages.json'), 'utf8'))
  const html = renderCard('failed', messages.timeout, null, {
    project: { error_code: 'timeout', processing_config: { failure_stage: 'highlight' } },
  })
  assert.match(html, /分析：/)
  assert.ok(html.includes(messages.timeout))
})


test('failed card with billable_calls_before_failure shows 本次已消耗 (#491 tip soft)', () => {
  const html = renderCard('failed', '错误', null, {
    project: {
      error_code: 'provider_error',
      processing_config: { billable_calls_before_failure: 3, failure_stage: 'analyze' },
    },
  })
  assert.match(html, /分析：/)
  assert.match(html, /ac-project-billing/)
  assert.match(html, /本次已消耗 3 次请求/)
  const quiet = renderCard('failed', '错误', null, {
    project: { error_code: 'provider_error', processing_config: { billable_calls_before_failure: 0 } },
  })
  assert.doesNotMatch(quiet, /本次已消耗/)
  const viaSettings = renderCard('failed', '错误', null, {
    project: { error_code: 'provider_error', settings: { billable_calls_before_failure: 2 } },
  })
  assert.match(viaSettings, /本次已消耗 2 次请求/)
})

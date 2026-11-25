const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('path')
const { runInSandbox } = require('./vm-sandbox.cjs')
const ts = require('typescript')

const readiness = (() => {
  const file = path.join(__dirname, '../src/features/studio/importReadiness.ts')
  const exports = {}
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText
  runInSandbox(code, { exports, require: () => ({}) })
  return exports
})()

function loadUrlPreview() {
  const file = path.join(__dirname, '../src/features/studio/UrlPreview.tsx')
  const exports = {}
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText
  runInSandbox(code, {
    exports,
    require: (name) => {
      if (name === '../../i18n') return { t: (s) => s }
      if (name === '../../ui') return { Btn: Object.assign(function Btn() { return null }, { displayName: 'Btn' }) }
      if (name === 'react/jsx-runtime') {
        return {
          jsx: (t, p) => ({ t: typeof t === 'function' ? (t.displayName || t.name || 'fn') : t, p }),
          jsxs: (t, p) => ({ t: typeof t === 'function' ? (t.displayName || t.name || 'fn') : t, p }),
          Fragment: 'fragment',
        }
      }
      if (name === './etaModel') return { estimate: () => ({ etaMin: 2, optimistic: false, initialMin: 2, errorRatio: null }) }
      if (name === './planningCopy') return { VISUAL_SOURCE_TOO_LONG_MESSAGE: 'x' }
      if (name === './importReadiness') return readiness
      if (name === './types') return { FIRST_WINDOW_END_SEC: 1800 }
      return {}
    },
  })
  return exports
}

function walk(node, visit) {
  if (!node || typeof node !== 'object') return
  visit(node)
  const kids = node.p && node.p.children
  if (Array.isArray(kids)) kids.forEach((k) => walk(k, visit))
  else if (kids) walk(kids, visit)
}

const preview = loadUrlPreview()

test('B2: returning users pasting >30m local_transcription URL see tip and 30m quick option', () => {
  let partialClicks = 0
  let confirmClicks = 0
  const tree = preview.default({
    preview: {
      title: '1h podcast without subtitles',
      duration: 3600,
      preview_route: 'local_transcription',
    },
    suggestFirstWindow: false,
    onConfirm: () => { confirmClicks += 1 },
    onConfirmFirstWindow: () => { partialClicks += 1 },
  })
  const tips = []
  const buttons = []
  walk(tree, (node) => {
    if (node.p && node.p['data-testid'] === 'long-local-asr-tip') tips.push(node)
    if (node.t === 'Btn') buttons.push(node.p)
  })
  assert.equal(tips.length, 1)
  const partialBtn = buttons.find((b) => b['data-testid'] === 'long-local-window-partial')
  assert.ok(partialBtn, 'expected 30-min quick button for returning user')
  partialBtn.onClick()
  assert.equal(partialClicks, 1)
  const fullBtn = buttons.find((b) => b.children === '确认并开始下载')
  assert.ok(fullBtn)
  fullBtn.onClick()
  assert.equal(confirmClicks, 1)
})

test('B2: long platform_subtitle or short local_transcription URLs do not show long local ASR warning', () => {
  for (const sample of [
    { title: '1h captioned', duration: 3600, preview_route: 'platform_subtitle' },
    { title: '20m local', duration: 1200, preview_route: 'local_transcription' },
  ]) {
    const tree = preview.default({
      preview: sample,
      suggestFirstWindow: false,
      onConfirm: () => {},
      onConfirmFirstWindow: () => {},
    })
    const tips = []
    walk(tree, (node) => {
      if (node.p && node.p['data-testid'] === 'long-local-asr-tip') tips.push(node)
    })
    assert.equal(tips.length, 0, sample.title)
  }
})

test('B1: StudioResults and HomePage wire partial/interrupted resume affordances and all 13 locales carry keys', () => {
  const resultsSrc = fs.readFileSync(path.join(__dirname, '../src/features/studio/StudioResults.tsx'), 'utf8')
  const homeSrc = fs.readFileSync(path.join(__dirname, '../src/pages/HomePage.tsx'), 'utf8')
  const apiSrc = fs.readFileSync(path.join(__dirname, '../src/features/studio/api.ts'), 'utf8')
  assert.ok(resultsSrc.includes('data-testid="partial-render-resume"'))
  assert.ok(resultsSrc.includes('studioApi.retryFailedVariants'))
  assert.ok(homeSrc.includes('data-testid="interrupted-projects-resume"'))
  assert.ok(homeSrc.includes("error_code === 'service_restarted'"))
  assert.ok(apiSrc.includes("scope: 'failed_variants'"))

  const localesDir = path.join(__dirname, '../src/i18n/locales')
  const files = fs.readdirSync(localesDir).filter((f) => f.endsWith('.json'))
  assert.ok(files.length >= 13)
  const required = [
    '继续渲染未完成版本',
    '继续渲染剩余版本',
    '还有 {{count}} 条未完成版本，已完成成片已保留。',
    '上次重启中断的制作',
    '正在恢复…',
    '视频超过 30 分钟且需要本地转写，低配电脑耗时较长；可先处理前 30 分钟，或在设置中改用 base 模型 / 云端转写。',
  ]
  for (const f of files) {
    const data = JSON.parse(fs.readFileSync(path.join(localesDir, f), 'utf8'))
    for (const key of required) {
      assert.ok(typeof data[key] === 'string' && data[key].trim().length > 0, `${f} missing ${key}`)
    }
  }
})

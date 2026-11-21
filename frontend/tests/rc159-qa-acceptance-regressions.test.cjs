const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

const slots = loadTs('defaultModelSlots.ts', { '../../i18n': { t: text => text } })
const logic = loadTs('modelSettingsLogic.ts', { '../../i18n': { t: text => text } })

const conn = (id, provider, extra = {}) => ({
  id, name: provider, provider, base_url: '', api_key: 'k', has_key: true,
  image_api: 'auto', image_base_url: '', validation_status: 'ok', ...extra,
})

const baseSettings = (extra = {}) => ({
  version: 1, saved: true,
  connections: [conn('ds', 'dashscope')],
  analysis: { connection_id: 'ds', model: 'qwen4-max', capability: 'multimodal', model_source: 'user' },
  vision: null, cover: null,
  transcription: { provider: 'cloud', connection_id: 'ds', model: 'qwen-audio-3.1-asr-flash', model_source: 'user' },
  cover_enabled: false, cover_design_mode: 'crop_grade_text_only', allow_send_frame: true,
  analysis_mode: 'auto', allow_visual_screening: true,
  chunk_size: 5000, min_score_threshold: .7, max_clips_per_collection: 5,
  ...extra,
})

test('selecting a cover model switches cover_design_mode to editorial_edit while respecting explicit allow_send_frame opt-out', () => {
  const fixed = slots.applyFixedSelection(baseSettings(), 'cover', 'qwen-image-2.1-pro', 'ds')
  assert.equal(fixed.cover_enabled, true)
  assert.equal(fixed.prefer_local_cover, false)
  assert.equal(fixed.cover_design_mode, 'editorial_edit')
  assert.equal(fixed.allow_send_frame, true)

  const smart = slots.applySmartSelection(baseSettings(), 'cover', 'qwen-image-2.1-pro', 'ds')
  assert.equal(smart.cover_design_mode, 'editorial_edit')

  const optedOut = slots.applyFixedSelection(baseSettings({ allow_send_frame: false }), 'cover', 'qwen-image-2.1-pro', 'ds')
  assert.equal(optedOut.cover_design_mode, 'editorial_edit')
  assert.equal(optedOut.allow_send_frame, false, 'explicit user opt-out of reference frame must be preserved')

  const direct = logic.setCoverModel(baseSettings(), 'ds', 'qwen-image-2.1-pro')
  assert.equal(direct.cover_design_mode, 'editorial_edit')
})

test('DefaultModels clarifies cover-only frame consent scope and warns when cover model will not be called', () => {
  const src = fs.readFileSync(path.resolve(__dirname, '../src/features/settings/DefaultModels.tsx'), 'utf8')
  assert.match(src, /允许向封面生图模型上传参考帧/)
  assert.match(src, /当前为「原帧排版」，不会调用所选生图模型/)
  assert.match(src, /已关闭向封面生图模型上传参考帧/)
})

test('DraftResultCard exposes distinct title-scoped accessible labels and testids for pending export and edit actions', () => {
  const src = fs.readFileSync(path.resolve(__dirname, '../src/features/studio/DraftResultCard.tsx'), 'utf8')
  assert.match(src, /data-draft-id=\{draft\.id\}/)
  assert.match(src, /data-draft-status=\{status\}/)
  assert.match(src, /data-testid="draft-export-btn"/)
  assert.match(src, /data-testid="draft-edit-btn"/)
  assert.match(src, /aria-label=\{`\$\{t\(status === 'failed' \? '重试导出' : '导出成片'\)\} · \$\{draft\.title\}`\}/)
  assert.match(src, /aria-label=\{`\$\{t\('预览与修改'\)\} · \$\{draft\.title\}`\}/)
})

const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

const ROOT = path.resolve(__dirname, '..')

test('safeStudioProperties allowlists rating_trigger and issue_tags and drops unknown tags', () => {
  const wf = loadTs(path.join(ROOT, 'src/analytics/workflow.ts'), {
    './posthog': { captureBusinessEvent: () => {}, isAnalyticsEnabled: () => true },
    './failureCodes': { ERROR_CODE: /^[a-z0-9_]+$/ },
  })
  const clean = wf.safeStudioProperties({
    output_rating: 'unusable',
    rating_trigger: 'card_dislike',
    issue_tags: ['text_overlap', 'cover_text', 'evil_free_text', 'text_overlap'],
    template: 'editorial',
    strategy_id: 'xiaohongshu',
  })
  assert.equal(clean.output_rating, 'unusable')
  assert.equal(clean.rating_trigger, 'card_dislike')
  assert.equal(clean.issue_tags, 'text_overlap,cover_text')
  assert.equal(clean.template, 'editorial')
  assert.equal(clean.strategy_id, 'xiaohongshu')

  const invalid = wf.safeStudioProperties({
    rating_trigger: 'unknown_trigger',
    issue_tags: ['not_a_real_tag'],
  })
  assert.equal(invalid.rating_trigger, undefined)
  assert.equal(invalid.issue_tags, undefined)
})

test('OutputVariantCard wires card dislike button and all 20 locales carry feedback keys', () => {
  const card = fs.readFileSync(path.join(ROOT, 'src/features/studio/OutputVariantCard.tsx'), 'utf8')
  assert.match(card, /studio-card-dislike-btn/)
  assert.match(card, /Icon\.ThumbsDown/)
  assert.match(card, /trigger=\{feedbackMode\}/)

  const keys = [
    '效果不好？点此反馈',
    '哪里不够理想？（可多选）',
    '字幕/标题叠字',
    '封面文字有误',
    '画面裁切不当',
    '切片选段不准',
    '字幕/音画问题',
    '补充一句具体问题（选填）',
    '不含视频与字幕内容',
    '提交反馈',
    '已收到反馈，将用于优化模板与剪辑策略',
  ]
  const localesDir = path.join(ROOT, 'src/i18n/locales')
  const files = fs.readdirSync(localesDir).filter(f => f.endsWith('.json'))
  assert.equal(files.length, 20)
  for (const file of files) {
    const data = JSON.parse(fs.readFileSync(path.join(localesDir, file), 'utf8'))
    for (const key of keys) {
      assert.ok(data[key] && data[key].trim(), `${file} missing translation for "${key}"`)
    }
  }
})

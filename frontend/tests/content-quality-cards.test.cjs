const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const { loadTs } = require('./load-ts.cjs')
const root = path.resolve(__dirname, '../src/features/studio')
let catalog = {}
const empty = { default: () => null }
const mocks = {
  'react-router-dom': { useNavigate: () => () => {} },
  'react-i18next': { useTranslation: () => ({ t: s => catalog[s] || s }) },
  '../../i18n': { t: s => catalog[s] || s, getLocale: () => 'en' },
  '../../ui': { Btn: p => React.createElement('button', null, p.children), fmtDuration: () => '20s', Row: p => React.createElement('div', null, p.children), Segmented: () => null },
  'antd': { Switch: () => null },
  '../../analytics/studio': {},
  '../../analytics/flags': { useFlag: () => false, flagAssigned: () => false },
  './StudioDownloadLink': empty, './OutputFeedback': empty, './PublishKit': empty,
  './api': { studioApi: { video: () => '/video.mp4', thumbnail: () => '/thumb.jpg' } },
  './outputShare': {}, './platformLabel': { platformLabel: () => 'Douyin' }, './quick-output.css': {},
}
const VariantCard = loadTs(path.join(root, 'OutputVariantCard.tsx'), mocks).default
const DraftCard = loadTs(path.join(root, 'DraftResultCard.tsx'), mocks).default
const pack = { template: 'interview_zh', source_language: 'en', audience_language: 'zh', fallback: true,
  cues: [{ text: '译文', original: 'Original' }], translation_status: 'partial' }
const draft = { id: 'draft', revision: 1, title: 'Original title', hook: '', language: 'source', origin: 'auto-content',
  scenes: [{ start: 0, end: 20, evidence: '' }], subtitles: true, packaging: pack, ending_review_required: true }
const job = { job_id: 'j', draft_id: 'draft', revision: 1, status: 'completed', created_at: '2026-11-16', result: { duration: 20 } }
const variant = { id: 'v', status: 'completed', strategy_id: 'douyin', render_job_id: 'j', branding: { outro_enabled: false } }
const escaped = text => renderToStaticMarkup(React.createElement('span', null, text)).slice(6, -7)
function cards(value) {
  return [renderToStaticMarkup(React.createElement(VariantCard, { projectId: 'p', variant, draft: value, job })),
    renderToStaticMarkup(React.createElement(DraftCard, { projectId: 'p', draft: value, jobs: [job] }))]
}

test('both result surfaces disclose incomplete translation and unresolved endings in eight locales', () => {
  for (const locale of ['zh', 'en', 'ja', 'ko', 'fr', 'es', 'pt', 'ru']) {
    catalog = require('../src/i18n/locales/' + locale + '.json')
    for (const html of cards(draft)) {
      for (const key of ['字幕翻译尚未完成，请检查后再发布', '片尾完整性需要复核，请预览最后一段']) {
        assert.ok(catalog[key], locale + key)
        assert.ok(html.includes(escaped(catalog[key])), locale + key)
      }
      assert.ok(!html.includes(escaped(catalog['访谈式 · 中英字幕'])))
    }
  }
})

test('resolved ending and complete translation do not keep stale failure hints', () => {
  catalog = require('../src/i18n/locales/en.json')
  for (const html of cards({ ...draft, ending_review_required: false, packaging: { ...pack, translation_status: 'complete' } })) {
    assert.ok(html.includes(escaped(catalog['字幕翻译已完成，使用简化包装'])))
    assert.ok(!html.includes(escaped(catalog['字幕翻译尚未完成，请检查后再发布'])))
    assert.ok(!html.includes(escaped(catalog['片尾完整性需要复核，请预览最后一段'])))
  }
})

test('caption-only recovery is available for incomplete enabled translations', () => {
  const Settings = loadTs(path.join(root, 'PackagingSettings.tsx'), mocks).default
  catalog = require('../src/i18n/locales/en.json')
  const show = value => renderToStaticMarkup(React.createElement(Settings, {
    draft: { ...value, packaging: { title_lines: [], tags: [], ...value.packaging } }, patch() {}, onRetryTranslation() {},
  }))
  const label = escaped(catalog['只重试字幕翻译'])
  assert.ok(show(draft).includes(label))
  assert.ok(!show({ ...draft, packaging: { ...pack, captions_enabled: false } }).includes(label))
  assert.ok(!show({ ...draft, packaging: { ...pack, translation_status: 'complete' } }).includes(label))
})

test('caption-only recovery sends the current edit without starting generation or export', async () => {
  const { setup } = require('./helpers/studio-harness.cjs')
  const seen = []
  const harness = setup({ post: async (url, body) => { seen.push({ url, body }); return { ...pack, translation_status: 'complete' } } })
  const reply = await harness.studioApi.retryTranslation('project', draft)
  assert.deepEqual(seen, [{ url: '/studio/project/retry-translation', body: draft }])
  assert.equal(reply.translation_status, 'complete')
  assert.equal(harness.events.length, 0) // a caption repair is not a new generation success denominator
})

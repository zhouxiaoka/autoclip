// preview, export confirm and subtitle_enabled telemetry read one effective state.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path')
const { loadTs } = require('./load-ts.cjs')
const studio = path.join(__dirname, '../src/features/studio')
const read = f => fs.readFileSync(path.join(studio, f), 'utf8')

test('effective subtitle state: packaging captions_enabled, else draft.subtitles', () => {
  const { effectiveSubtitles } = loadTs(path.join(studio, 'subtitleState.ts'))
  assert.equal(effectiveSubtitles({ subtitles: true }), true)
  assert.equal(effectiveSubtitles({ subtitles: false }), false)
  assert.equal(effectiveSubtitles({ subtitles: true, packaging: { captions_enabled: false } }), false)
  assert.equal(effectiveSubtitles({ subtitles: true, packaging: { captions_enabled: true } }), true)
  assert.equal(effectiveSubtitles({ subtitles: true, packaging: {} }), true) // older drafts
  // with packaging, captions_enabled decides (backend ignores draft.subtitles there).
  assert.equal(effectiveSubtitles({ subtitles: false, packaging: { captions_enabled: true } }), true)
  assert.equal(effectiveSubtitles(undefined), false)
})

test('subtitle_enabled telemetry follows the template captions switch', () => {
  const api = read('api.ts')
  assert.match(api, /subtitle_enabled: draft \? effectiveSubtitles\(draft\) : undefined/)
  assert.doesNotMatch(api, /subtitle_enabled: draft\?\.subtitles/)
})

test('StudioEditor preview overlay and export confirm use the effective state', () => {
  const editor = read('StudioEditor.tsx')
  assert.match(editor, /const subtitlesOn = effectiveSubtitles\(draft\)/)
  assert.match(editor, /!showRendered && subtitlesOn && activeCue/)
  assert.match(editor, /<Row label=\{t\("字幕"\)\}>\{subtitlesOn\?/)
  assert.doesNotMatch(editor, /draft\.subtitles/)
})

test('fallback hints use the effective state too', () => {
  assert.match(read('OutputVariantCard.tsx'), /packagingFallbackHint\(packaging, job\?\.result\?\.warnings, effectiveSubtitles\(draft\)\)/)
  assert.match(read('PackagingSettings.tsx'), /packagingFallbackHint\(packaging, \[\], effectiveSubtitles\(draft\)\)/)
})

test('R11: source burned-in subtitles + different-language packaging follow captions_enabled', () => {
  const { effectiveSubtitles } = loadTs(path.join(studio, 'subtitleState.ts'))
  const pack = { captions_enabled: false, burned_captions: true, source_language: 'en', fallback: true,
    cues: [{ start: 0, end: 1, text: '你好', original: 'hello' }] }
  assert.equal(effectiveSubtitles({ subtitles: true, language: 'zh', packaging: pack }), false)
  assert.equal(effectiveSubtitles({ subtitles: false, language: 'zh', packaging: { ...pack, captions_enabled: true } }), true)
})

test('R11: with subtitles off the fallback hint never says captions were kept', () => {
  const { packagingFallbackHint } = loadTs(path.join(studio, 'packagingLabel.ts'), { '../../i18n': { t: s => s } })
  const pack = { fallback: true, burned_captions: true, cues: [{ start: 0, end: 1, text: 'x', original: 'x' }] }
  for (const warnings of [[], ['包装未能完整生成，已使用原字幕']]) {
    assert.ok(!packagingFallbackHint(pack, warnings, false).includes('已保留可用字幕'))
  }
  assert.equal(packagingFallbackHint(pack, [], true), '包装未能完整生成，已保留可用字幕')
})

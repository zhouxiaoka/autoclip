// R10 #396: preview, export confirm and subtitle_enabled telemetry read one effective state.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path')
const { loadTs } = require('./load-ts.cjs')
const studio = path.join(__dirname, '../src/features/studio')
const read = f => fs.readFileSync(path.join(studio, f), 'utf8')

test('effective subtitle state: draft switch AND template captions switch', () => {
  const { effectiveSubtitles } = loadTs(path.join(studio, 'subtitleState.ts'))
  assert.equal(effectiveSubtitles({ subtitles: true }), true)
  assert.equal(effectiveSubtitles({ subtitles: false }), false)
  assert.equal(effectiveSubtitles({ subtitles: true, packaging: { captions_enabled: false } }), false)
  assert.equal(effectiveSubtitles({ subtitles: true, packaging: { captions_enabled: true } }), true)
  assert.equal(effectiveSubtitles({ subtitles: true, packaging: {} }), true) // older drafts
  assert.equal(effectiveSubtitles({ subtitles: false, packaging: { captions_enabled: true } }), false)
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

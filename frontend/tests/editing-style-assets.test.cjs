const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const src = path.join(__dirname, '../src')
const read = rel => fs.readFileSync(path.join(src, rel), 'utf8')
const STYLES = ['editorial', 'street', 'classic']

test('every style poster and preview (webm + mp4) is a local bundled asset', () => {
  const media = read('features/studio/editingStyleMedia.ts')
  assert.equal(/https?:\/\//.test(media), false, 'no remote URLs')
  for (const id of STYLES) {
    for (const file of [`${id}.poster.webp`, `${id}.preview.webm`, `${id}.preview.mp4`]) {
      assert.ok(media.includes(`../../assets/editing-style/${file}`), file)
      assert.ok(fs.statSync(path.join(src, 'assets/editing-style', file)).size > 0, file)
    }
  }
})

test('picker keeps a static poster under the video and hides the video on load error', () => {
  const picker = read('features/studio/EditingStylePicker.tsx')
  assert.ok(picker.includes('<img src={STYLE_POSTERS[id]}'))
  assert.ok(picker.includes('poster={STYLE_POSTERS[id]}'))
  const onError = picker.slice(picker.indexOf('onError='), picker.indexOf('onPlaying='))
  assert.ok(onError.includes("classList.remove('is-playing')"))
  assert.ok(onError.includes('trackTemplatePreviewFailed'))
  const css = read('features/studio/quick-output.css')
  assert.match(css, /\.studio-style-thumb video \{\s*opacity: 0;/)
  assert.match(css, /\.studio-style-thumb video\.is-playing \{\s*opacity: 1;/)
})

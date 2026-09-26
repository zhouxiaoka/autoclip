const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('fs')
const path = require('path')

// react-player@2.13 FilePlayer.canPlay — extension required, forceVideo does not help.
const VIDEO_EXTENSIONS = /\.(mp4|og[gv]|webm|mov|m4v)(#t=[,\d+]+)?($|\?)/i

const root = path.join(__dirname, '../src/components')

test('react-player will not mount a file player for extension-less clip URLs', () => {
  const url = 'http://127.0.0.1:56101/api/v1/projects/project/clips/clip'
  assert.equal(VIDEO_EXTENSIONS.test(url), false)
  assert.equal(VIDEO_EXTENSIONS.test(`${url}.mp4`), true)
})

test('clip previews use a native video element, not react-player', () => {
  const files = ['ClipCard.tsx', 'CollectionPreviewModal.tsx', 'ClipVideo.tsx']
  for (const name of files) {
    const source = fs.readFileSync(path.join(root, name), 'utf8')
    assert.doesNotMatch(source, /from ['"]react-player['"]/, name)
  }
  const player = fs.readFileSync(path.join(root, 'ClipVideo.tsx'), 'utf8')
  assert.match(player, /<video/)
  assert.match(player, /src=\{url\}/)
  assert.match(player, /这个切片当前播放器无法解码/)
  for (const name of ['ClipCard.tsx', 'CollectionPreviewModal.tsx']) {
    const source = fs.readFileSync(path.join(root, name), 'utf8')
    assert.match(source, /<ClipVideo/, name)
  }
})

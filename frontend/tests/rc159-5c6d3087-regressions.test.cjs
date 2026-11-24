const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

const read = rel => fs.readFileSync(path.join(__dirname, '..', rel), 'utf8')

test('ExportCover maps frame_sending_disabled to opt-out notice instead of image failure', () => {
  const src = read('src/features/studio/ExportCover.tsx')
  assert.match(src, /export function coverWarningMessage\(/)
  const mod = loadTs(path.join(__dirname, '../src/features/studio/ExportCover.tsx'), {
    react: {},
    antd: { message: {} },
    '../../i18n': { t: s => s },
    '../../publish/coverApi': { coverApi: {} },
    '../../services/api': { default: { defaults: { baseURL: '' } } },
    '../../ui': { Btn: () => null, Dialog: () => null },
    './api': { exportCoverSlot: () => 'douyin', studioApi: {} },
    './nativeDownload': { isDesktopDownload: () => false, saveLocalFile: async () => {} },
  })
  assert.equal(mod.coverWarningMessage('frame_sending_disabled'), '已关闭上传参考帧，当前使用本地排版封面')
  assert.ok(!mod.coverWarningMessage('frame_sending_disabled').includes('生图失败'))
  assert.equal(mod.coverWarningMessage('needs_source_validation'), '当前是截帧封面')
  assert.equal(mod.coverWarningMessage('text_mismatch'), '生图标题校对未通过，已改成本地排版')
  assert.equal(mod.coverWarningMessage('image_service_unavailable'), '生图失败，已改成本地排版或截帧')
  assert.equal(mod.coverWarningMessage(undefined), '')
})

test('StudioEditor exported dialog does not duplicate old and new already-rendered descriptions', () => {
  const editorSrc = read('src/features/studio/StudioEditor.tsx')
  assert.match(editorSrc, /当前版本已渲染完成，可直接下载已有成片，或重新渲染新版本。/)
  assert.doesNotMatch(editorSrc, /当前版本已渲染完成，可以直接下载。/)
})

test('StudioResults keeps same-source remake entry after leaving or restarting', () => {
  const resultsSrc = read('src/features/studio/StudioResults.tsx')
  assert.doesNotMatch(resultsSrc, /const showMorePlatform = viewedProject === project\.id/)
  assert.match(resultsSrc, /const showMorePlatform = automatic && genDone && !bannerDismissed && !morePlatformBannerSeen\(\)/)
  assert.match(resultsSrc, /canRemake && <Btn[^>]+onClick=\{\(\) => openRemake\([^\n]+\)\}>\{t\('重做'\)\}/)
})

test('StudioResults displays completed export count on 导出记录 button when multiple versions exist', () => {
  const resultsSrc = read('src/features/studio/StudioResults.tsx')
  assert.match(resultsSrc, /const completedExportCount = \(workspace\.jobs \|\| \[\]\)\.filter\(j => j\.status === 'completed'\)\.length/)
  assert.match(resultsSrc, /\{t\("导出记录"\)\}\{completedExportCount > 0 && <> <span className="ac-mono">\{completedExportCount\}<\/span><\/>\}/)
})

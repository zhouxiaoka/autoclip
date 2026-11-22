const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

const studioDir = path.resolve(__dirname, '../src/features/studio')
const srcDir = path.resolve(__dirname, '../src')
const tauriLib = path.resolve(__dirname, '../../src-tauri/src/lib.rs')

const failureAction = loadTs(path.join(studioDir, 'failureAction.ts'))
const failurePresentation = loadTs(path.join(studioDir, 'failurePresentation.ts'), {
  './failureAction': failureAction,
  './transcriptionRecovery': loadTs(path.join(studioDir, 'transcriptionRecovery.ts')),
  './browserCookieRecovery': loadTs(path.join(studioDir, 'browserCookieRecovery.ts')),
})

test('presentFailure routes bad_endpoint to settings instead of infinite retry', () => {
  const badEp = failurePresentation.presentFailure({
    error_code: 'bad_endpoint',
    failure_stage: 'analyze',
    connectionCount: 1,
  })
  assert.equal(badEp.primary.id, 'settings', 'bad_endpoint must go to settings, not retry')
})

test('StudioResults renders failure summary on taskFailed (including generation.status===failed) and hides empty banner while failed/rendering', () => {
  const src = fs.readFileSync(path.join(studioDir, 'StudioResults.tsx'), 'utf8')
  assert.match(src, /taskFailed\s*&&\s*<div className="ac-failure-summary"/)
  assert.match(src, /!taskFailed&&workspace\.generation\?\.status!=='rendering'/)
})

test('SettingsPage retains return_project on tab switches', () => {
  const settingsSrc = fs.readFileSync(path.join(srcDir, 'pages/SettingsPage.tsx'), 'utf8')
  assert.match(settingsSrc, /return_project/)
})

test('QuitGuard Esc dismisses without hiding to tray, and Tauri lib.rs handles macOS RunEvent::Reopen', () => {
  const quitSrc = fs.readFileSync(path.join(studioDir, 'quitGuard.tsx'), 'utf8')
  assert.doesNotMatch(quitSrc, /onClose=\{\(\)\s*=>\s*choose\('background'\)\}/)
  assert.match(quitSrc, /onClose=\{\(\)\s*=>\s*setOpen\(false\)\}/)
  const rustSrc = fs.readFileSync(tauriLib, 'utf8')
  assert.match(rustSrc, /RunEvent::Reopen/)
})

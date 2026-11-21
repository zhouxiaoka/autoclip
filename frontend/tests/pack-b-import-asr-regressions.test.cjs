const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

const studioDir = path.resolve(__dirname, '../src/features/studio')
const errMod = loadTs(path.join(studioDir, 'errorText.ts'))
const cookieMod = loadTs(path.join(studioDir, 'browserCookieRecovery.ts'))
const pasteMod = loadTs(path.join(studioDir, 'pasteStart.ts'))

test('errorCode reads both detail.code and detail.error_code (for /studio/inspect-url 422)', () => {
  assert.equal(errMod.errorCode({ response: { data: { detail: { code: 'whisper_not_installed' } } } }), 'whisper_not_installed')
  assert.equal(
    errMod.errorCode({ response: { data: { detail: { error_code: 'source_blocked', message: 'blocked' } } } }),
    'source_blocked',
  )
})

test('cookieAssistFromLocation detects focus=browser-cookies inside HashRouter hash', () => {
  assert.equal(cookieMod.cookieAssistFromLocation('?focus=browser-cookies', ''), true)
  assert.equal(cookieMod.cookieAssistFromLocation('', '#/?focus=browser-cookies'), true)
  assert.equal(cookieMod.cookieAssistFromLocation('', '#/?foo=1&focus=browser-cookies'), true)
  assert.equal(cookieMod.cookieAssistFromLocation('', '#/?focus=other'), false)
})

test('extractImportUrl extracts Bilibili/YouTube share text and upgrades http links', () => {
  assert.equal(typeof pasteMod.extractImportUrl, 'function')
  assert.equal(
    pasteMod.extractImportUrl('【Bill Gates 精彩访谈】 https://b23.tv/Ab12345'),
    'https://b23.tv/Ab12345',
  )
  assert.equal(
    pasteMod.extractImportUrl('http://www.bilibili.com/video/BV1xx411c7mu'),
    'https://www.bilibili.com/video/BV1xx411c7mu',
  )
  assert.equal(
    pasteMod.extractImportUrl('Check this out: https://youtu.be/dQw4w9WgXcQ'),
    'https://youtu.be/dQw4w9WgXcQ',
  )
  assert.equal(pasteMod.extractImportUrl('just random text without link'), null)
  assert.equal(pasteMod.extractImportUrl('https://b23.tv/a and https://youtu.be/b'), null)
})

test('CreativeImport wires HashRouter hash into cookieAssistFromLocation and tolerates inspect-url timeout', () => {
  const src = fs.readFileSync(path.join(studioDir, 'CreativeImport.tsx'), 'utf8')
  assert.match(src, /cookieAssistFromLocation\([\s\S]*?window\.location\?\.hash/)
  assert.match(src, /inspectTimedOut/)
})

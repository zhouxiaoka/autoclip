const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const root = path.resolve(__dirname, '../..')

test('the first-use diagnostics notice is mounted at the app root and a dismiss does not save', () => {
  const app = fs.readFileSync(path.join(root, 'frontend/src/App.tsx'), 'utf8')
  const notice = fs.readFileSync(path.join(root, 'frontend/src/features/diagnostics/DiagnosticsNotice.tsx'), 'utf8')
  assert.match(app, /<DiagnosticsNotice \/>/)
  assert.match(notice, /onClose=\{\(\) => \{\}\}/)
  assert.match(notice, /diagnosticsApi\.setConsent/)
  assert.doesNotMatch(notice, /onClose=\{\(\) => void save/)
})

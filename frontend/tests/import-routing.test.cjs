const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), ts = require('typescript')
const exportsObject = {}
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/features/studio/importRouting.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText, { exports: exportsObject })
const { needsImportConfirmation } = exportsObject

for (const field of ['settings', 'processing_config']) {
  test(`${field}: automatic screening and interrupted older saves stay on results`, () => {
    assert.equal(needsImportConfirmation({ [field]: { import_staging: true, smart_import: { auto_start: true } } }), false)
  })
  test(`${field}: manual imports still require confirmation`, () => {
    assert.equal(needsImportConfirmation({ [field]: { import_staging: true, smart_import: { auto_start: false } } }), true)
    assert.equal(needsImportConfirmation({ [field]: { import_staging: true } }), true)
  })
}
test('completed legacy projects do not reopen import confirmation', () => {
  assert.equal(needsImportConfirmation({ settings: {}, processing_config: { import_staging: false } }), false)
})
test('a malformed auto-start value cannot bypass manual confirmation', () => {
  assert.equal(needsImportConfirmation({ processing_config: { import_staging: true, smart_import: { auto_start: 'false' } } }), true)
})

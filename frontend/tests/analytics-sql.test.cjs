const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { spawnSync } = require('node:child_process')

test('saved analytics SQL accepts legacy and current frontend terminal outcomes', () => {
  const python = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3')
  const result = spawnSync(python, [path.join(__dirname, 'analytics_sql_fixture.py')], {
    encoding: 'utf8',
  })
  assert.ifError(result.error)
  assert.equal(result.status, 0, result.stderr)
})

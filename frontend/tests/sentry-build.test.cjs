const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const path = require('node:path')
const test = require('node:test')

const frontend = path.resolve(__dirname, '..')
const env = {
  ...process.env,
  SENTRY_AUTH_TOKEN: '',
  SENTRY_UPLOAD_SOURCEMAPS: 'false',
  VITE_PUBLIC_SENTRY_DSN: '',
}

function preflight(overrides) {
  return spawnSync(process.execPath, ['../scripts/check_sentry_build.mjs'], {
    cwd: frontend, env: { ...env, ...overrides }, encoding: 'utf8',
  })
}

test('unconfigured forks can build without Sentry credentials', () => {
  assert.equal(preflight({}).status, 0)
})

test('monitored CI builds fail early when upload credentials are missing', () => {
  const result = preflight({ VITE_PUBLIC_SENTRY_DSN: 'https://public@example.invalid/1' })
  assert.equal(result.status, 1)
  assert.match(result.stderr, /SENTRY_AUTH_TOKEN is missing/)
})

test('preflight reports presence without printing credentials', () => {
  const token = 'test-token-never-print'
  const result = preflight({ VITE_PUBLIC_SENTRY_DSN: 'https://public@example.invalid/1', SENTRY_AUTH_TOKEN: token })
  assert.equal(result.status, 0)
  assert.ok(!(result.stdout + result.stderr).includes(token))
})

function config(overrides, command = 'build') {
  const script = `
    import { loadConfigFromFile } from 'vite';
    const result = await loadConfigFromFile({command: ${JSON.stringify(command)}, mode: 'production'}, './vite.config.ts');
    const c = result.config;
    console.log(JSON.stringify({sourcemap: c.build.sourcemap, define: c.define, plugins: c.plugins.flat().map(p => p.name)}));
  `
  return spawnSync(process.execPath, ['--input-type=module', '-e', script], {
    cwd: frontend, env: { ...env, VITE_APP_VERSION: '1.3.1-test', ...overrides }, encoding: 'utf8',
  })
}

test('ordinary local build does not emit maps and has an explicit SDK version', () => {
  const result = config({})
  assert.equal(result.status, 0, result.stderr)
  const data = JSON.parse(result.stdout.trim().split('\n').at(-1))
  assert.equal(data.sourcemap, false)
  assert.equal(data.define['import.meta.env.VITE_APP_VERSION'], '"1.3.1-test"')
})

test('required upload cannot silently skip when the token is empty', () => {
  const result = config({ SENTRY_UPLOAD_SOURCEMAPS: 'true' })
  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /SENTRY_AUTH_TOKEN is required/)
})

test('upload build emits hidden maps without exposing its token in client definitions', () => {
  const token = 'test-token-never-bundle'
  const result = config({ SENTRY_UPLOAD_SOURCEMAPS: 'true', SENTRY_AUTH_TOKEN: token })
  assert.equal(result.status, 0, result.stderr)
  const data = JSON.parse(result.stdout.trim().split('\n').at(-1))
  assert.equal(data.sourcemap, 'hidden')
  assert.ok(data.plugins.some(name => name.startsWith('sentry-')))
  assert.ok(!JSON.stringify(data.define).includes(token))
})

test('dev server does not upload even when release credentials are available', () => {
  const result = config({ SENTRY_UPLOAD_SOURCEMAPS: 'true', SENTRY_AUTH_TOKEN: 'test-token' }, 'serve')
  assert.equal(result.status, 0, result.stderr)
  const data = JSON.parse(result.stdout.trim().split('\n').at(-1))
  assert.equal(data.sourcemap, false)
  assert.ok(data.plugins.every(name => !name.startsWith('sentry-')))
})

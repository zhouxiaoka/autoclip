const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const path = require('node:path')

const html = fs.readFileSync(path.join(__dirname, 'publish/index.html'), 'utf8')
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1]
const start = script.indexOf('  var T =')
const end = script.indexOf('  var LANG_ATTR')
const c = {}
vm.runInNewContext(script.slice(start, end), c)
const langs = ['zh', 'en', 'ja', 'ko', 'es', 'pt', 'ru', 'fr']

test('publish guide catalogs cover every translated node and keep the same links', () => {
  const keys = Object.keys(c.T.en).sort()
  for (const lang of langs) {
    assert.deepEqual(Object.keys(c.T[lang]).sort(), keys, lang)
    for (const [, key] of html.matchAll(/data-i18n(?:-html)?="([^"]+)"/g)) {
      assert.ok(c.T[lang][key], `${lang}: ${key}`)
    }
    for (const key of ['s1.2', 's2.1', 's2.2', 's2.3', 's3.1']) {
      const links = (s) => [...s.matchAll(/href="([^"]+)"/g)].map((m) => m[1]).sort()
      assert.deepEqual(links(c.T[lang][key]), links(c.T.en[key]), `${lang}: ${key}`)
    }
  }
})

test('the guide page asks for the three Bilibili cookies in Application', () => {
  assert.match(c.T.zh['s3.3'], /SESSDATA/)
  assert.match(c.T.zh['s3.3'], /bili_jct/)
  assert.match(c.T.zh['s3.3'], /DedeUserID/)
  assert.match(c.T.zh['s3.2'], /Application/)
  assert.match(c.T.zh['s2.4'], /仅自己/)
})

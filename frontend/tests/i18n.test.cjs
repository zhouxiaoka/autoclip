const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')
const { createInstance } = require('i18next')
const root = path.join(__dirname, '../src/i18n')
const langs = ['zh','en','ja','ko','es','pt','ru','fr']
const catalogs = Object.fromEntries(langs.map(l => [l, JSON.parse(fs.readFileSync(path.join(root, 'locales', l + '.json'), 'utf8'))]))
function loadResolver(storage) {
  const code = ts.transpileModule(fs.readFileSync(path.join(root, 'language.ts'), 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS}}).outputText
  const module = {exports:{}}
  vm.runInNewContext(code, {module, exports:module.exports, localStorage:storage})
  return module.exports
}
test('locale detection respects saved preference, regional variants and ordered system languages', () => {
  const {resolveLanguage} = loadResolver({getItem:()=>null})
  assert.equal(resolveLanguage('fr', ['es-MX']), 'fr')
  for (const tag of ['es-MX','es-419','es-ES']) assert.equal(resolveLanguage('system', [tag]), 'es')
  for (const tag of ['pt-BR','pt-PT']) assert.equal(resolveLanguage(null, [tag]), 'pt')
  assert.equal(resolveLanguage(null, ['ar-SA', 'ru-RU', 'en']), 'ru')
  assert.equal(resolveLanguage('__proto__', ['zh-TW']), 'zh')
  assert.equal(resolveLanguage(null, ['de-DE']), 'en')
})
test('unavailable or corrupt storage falls back to system language', () => {
  assert.equal(loadResolver({getItem:()=>{throw Error('denied')}}).readPreference(), 'system')
  assert.equal(loadResolver({getItem:()=> 'unknown'}).readPreference(), 'system')
  assert.equal(loadResolver({getItem:()=> 'ko'}).readPreference(), 'ko')
})
test('every catalog covers exactly the same messages and preserves interpolation variables', () => {
  const keys = Object.keys(catalogs.zh).sort()
  const placeholders = s => [...s.matchAll(/{{\s*([^}]+)\s*}}/g)].map(m=>m[1]).sort()
  for (const lang of langs) {
    assert.deepEqual(Object.keys(catalogs[lang]).sort(), keys, lang)
    for (const key of keys) {
      assert.ok(catalogs[lang][key].trim(), `${lang}: ${key}`)
      assert.deepEqual(placeholders(catalogs[lang][key]), placeholders(catalogs.zh[key]), `${lang}: ${key}`)
    }
  }
})
test('language changes update lookups without changing interpolated user content', async () => {
  const instance=createInstance()
  await instance.init({resources:Object.fromEntries(langs.map(l=>[l,{translation:catalogs[l]}])),lng:'en',fallbackLng:'en',keySeparator:false,nsSeparator:false,interpolation:{escapeValue:false}})
  assert.equal(instance.t('我的项目'), 'My projects')
  const userTitle='<img src=x> 原始标题 & título'
  for (const lang of langs) {
    await instance.changeLanguage(lang)
    assert.equal(instance.t('我的项目'), catalogs[lang]['我的项目'])
    assert.ok(instance.t('已删除 {{value1}}', {value1:userTitle}).includes(userTitle))
    for (const count of [0,1,2,5,21]) assert.ok(instance.t('切片数量',{count}).includes(String(count)))
  }
})
test('every static translation call has a catalog entry', () => {
  const scan = dir => fs.readdirSync(dir, {withFileTypes:true}).flatMap(e => e.isDirectory() ? scan(path.join(dir,e.name)) : /\.tsx?$/.test(e.name) ? [path.join(dir,e.name)] : [])
  for(const file of scan(path.join(__dirname,'../src'))) {
    const source=ts.createSourceFile(file,fs.readFileSync(file,'utf8'),ts.ScriptTarget.Latest,true)
    function visit(node){
      if(ts.isCallExpression(node)&&node.expression.getText(source)==='t'&&node.arguments.length&&ts.isStringLiteral(node.arguments[0])){
        const key=node.arguments[0].text
        assert.ok(Object.hasOwn(catalogs.zh,key),file+': '+key)
      }
      ts.forEachChild(node,visit)
    }
    visit(source)
  }
})

test('Studio result states translate on language changes while retaining titles and version numbers', async () => {
  const instance=createInstance()
  await instance.init({resources:Object.fromEntries(langs.map(l=>[l,{translation:catalogs[l]}])),lng:'en',fallbackLng:'en',keySeparator:false,nsSeparator:false,interpolation:{escapeValue:false}})
  const sourceTitle='贴壁过弯 <V2> & café'
  const states=['草稿 · 待导出','排队中','正在导出','已导出 · 可下载','导出失败','已修改 · 需重新导出','导出记录','发布这版成片']
  for(const lang of langs) {
    await instance.changeLanguage(lang)
    for(const state of states) {
      assert.ok(Object.hasOwn(catalogs[lang],state), `${lang}: ${state}`)
      assert.equal(instance.t(state),catalogs[lang][state])
      if(lang!=='zh') assert.notEqual(instance.t(state),state)
    }
    assert.ok(instance.t('预览 {{title}}',{title:sourceTitle}).includes(sourceTitle))
    assert.ok(instance.t('当前 V{{revision}} 成片画面',{revision:12}).includes('V12'))
    assert.ok(instance.t('{{count}} 段',{count:3}).includes('3'))
  }
})

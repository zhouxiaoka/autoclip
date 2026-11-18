const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { runInSandbox } = require('./vm-sandbox.cjs')
const ts = require('typescript')
const { createInstance } = require('i18next')
const root = path.join(__dirname, '../src/i18n')
const langs = ['zh','en','ja','ko','es','pt','ru','fr']
const catalogs = Object.fromEntries(langs.map(l => [l, JSON.parse(fs.readFileSync(path.join(root, 'locales', l + '.json'), 'utf8'))]))
test('locale JSON objects have no duplicate keys', () => {
  for (const lang of langs) {
    const source = ts.parseJsonText(lang + '.json', fs.readFileSync(path.join(root, 'locales', lang + '.json'), 'utf8'))
    function visit(node) {
      if (ts.isObjectLiteralExpression(node)) {
        const keys = node.properties.map(property => property.name.text)
        assert.equal(new Set(keys).size, keys.length, `${lang}: duplicate JSON keys`)
      }
      ts.forEachChild(node, visit)
    }
    visit(source)
  }
})
function loadResolver(storage) {
  const code = ts.transpileModule(fs.readFileSync(path.join(root, 'language.ts'), 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS}}).outputText
  const module = {exports:{}}
  runInSandbox(code, {module, exports:module.exports, localStorage:storage})
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

test('Studio UI has no untranslated static Chinese JSX or template strings', () => {
  const studio=path.join(__dirname,'../src/features/studio')
  for(const name of fs.readdirSync(studio).filter(n=>n.endsWith('.tsx'))) {
    const file=path.join(studio,name), source=ts.createSourceFile(file,fs.readFileSync(file,'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
    function visit(node) {
      if(ts.isJsxText(node)) assert.ok(!/[\u4e00-\u9fff]/.test(node.text),`${name}: untranslated JSX ${node.text}`)
      if(ts.isJsxAttribute(node)&&node.initializer&&ts.isStringLiteral(node.initializer)) assert.ok(!/[\u4e00-\u9fff]/.test(node.initializer.text),`${name}: untranslated attribute ${node.initializer.text}`)
      if(ts.isTemplateExpression(node)) assert.ok(!/[\u4e00-\u9fff]/.test(node.head.text+node.templateSpans.map(s=>s.literal.text).join('')),`${name}: use interpolation for translated templates`)
      ts.forEachChild(node,visit)
    }
    visit(source)
  }
})

test('Studio dynamic label maps and validation messages have translations in all eight catalogs', () => {
  for(const name of ['types.ts','titlePresets.ts','PlanSummary.tsx']) {
    const file=path.join(__dirname,'../src/features/studio',name),source=ts.createSourceFile(file,fs.readFileSync(file,'utf8'),ts.ScriptTarget.Latest,true)
    function visit(node) {
      if(ts.isStringLiteral(node)&&/[\u4e00-\u9fff]/.test(node.text)&&!['简体中文','日本語'].includes(node.text)) {
        for(const lang of langs) {
          assert.ok(Object.hasOwn(catalogs[lang],node.text),`${name}: ${lang}: ${node.text}`)
          if(lang!=='zh') assert.notEqual(catalogs[lang][node.text],node.text,`${lang}: ${node.text}`)
        }
      }
      ts.forEachChild(node,visit)
    }
    visit(source)
  }
})

test('feedback dialog discloses developer delivery in every locale', () => {
  const key = '内容和联系方式会发送给开发者，用于回复和创建 GitHub Issue。'
  for (const lang of langs) {
    assert.ok(Object.hasOwn(catalogs[lang], key), `${lang}: ${key}`)
    assert.ok(catalogs[lang][key].trim(), `${lang}: ${key}`)
  }
  assert.ok(catalogs.zh[key].includes('GitHub Issue'))
  assert.ok(catalogs.en[key].includes('GitHub Issue'))
})

test('reverted caption-correction copy stays out while diagnostics copy stays in every locale', () => {
  const kept = [
    '帮助改进 AutoClip',
    '失败后在后台上传脱敏诊断，只用于排查问题并改进产品，不会用于训练模型。默认关闭。不含 API 密钥、字幕正文、项目名或个人路径。未配置上传地址时不会发送。关闭后会停掉尚未完成的上传。',
    '允许附带失败任务的片段',
    '在已开启改进诊断后，可额外上传该任务开头的短片段。短片段可能复现不了片尾才出现的超时。默认仍然关闭。',
    '允许附带完整原片',
    '需要单独同意。完整原片体积大，只在你明确允许后才会上传，并且受大小上限约束。',
    '提交诊断',
    '看看将要发送的内容。素材默认不包含，需要逐项勾选。用于排查和改进，不会用于训练模型。',
    '短片段（从片头截取，可能复现不了片尾的超时）',
    '完整原片（单独同意）',
    '字幕文本（默认不发送）',
    '保存到本机',
    '没有配置上传地址，已改为保存到本机。',
    '诊断已排队',
    '诊断没有提交',
    '已取消上传',
    '删除已上传的诊断',
    '以后的失败也自动发送脱敏诊断',
    '只对打开这项之后的新失败生效，不会补传以前的失败。',
    '关闭改进后，新的失败不会再自动上传。',
    '我将对照清单再提交',
    '这次失败没有可关联的尝试编号，仍然可以写下反馈。',
    '将随诊断一起发送的字段',
    '不含 API 密钥、字幕正文、项目名或个人路径。未配置上传地址时不会发送。',
    '诊断设置没有保存，请重试。',
  ]
  const removed = [
    '字幕翻译尚未完成，请检查后再发布',
    '字幕翻译已完成，使用简化包装',
    '片尾完整性需要复核，请预览最后一段',
    '只重试字幕翻译',
    '补译后请保存并重新导出，已有成片保留。',
    '逐句校对',
    '译文覆盖完整不代表意思正确。修改后请保存并重新导出。',
    '选择字幕句子',
    '原句',
    '修改此句字幕',
    '字幕不能为空',
    '人工修改将随草稿保存，补译其他句子时保留。',
    '试听原句',
    '重译此句',
    '草稿已修改，未应用迟到的翻译结果，请重试',
    '原字幕或选段已变化，请核对人工修改后再重试',
    '字幕句子不存在',
    '此句重译未完成，原有字幕已保留，请稍后重试',
  ]
  for (const lang of langs) {
    for (const key of kept) assert.ok(Object.hasOwn(catalogs[lang], key) && catalogs[lang][key].trim(), `${lang}: ${key}`)
    for (const key of removed) assert.equal(Object.hasOwn(catalogs[lang], key), false, `${lang}: ${key}`)
  }
})

test('feedback disclosure tells every locale that send goes through PostHog', () => {
  const keys = [
    '已收到。这句话会先到 PostHog，再公开出现在 GitHub。',
    '发送后会先到 PostHog，再公开到 GitHub；邮箱不会公开。',
    '联系方式（可选，邮箱，只经 PostHog 送达，不会公开）',
    '在应用内写一句话即可。会先经 PostHog 送达；故障进 GitHub Issue，想法进 Discussions。',
  ]
  for (const key of keys) {
    for (const lang of langs) {
      assert.ok(Object.hasOwn(catalogs[lang], key), `${lang}: ${key}`)
      assert.ok(catalogs[lang][key].includes('PostHog'), `${lang}: ${key}`)
    }
  }
})

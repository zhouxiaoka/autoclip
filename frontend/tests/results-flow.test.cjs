const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

function load(relative, extra = {}) {
  const file = path.join(__dirname, relative)
  const exports = {}
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText
  vm.runInNewContext(code, { exports, URL, require: id => extra[id] || {} })
  return exports
}

const workflow = load('../src/analytics/workflow.ts')
const reason = load('../src/features/studio/clipReason.ts')
const pack = load('../src/features/studio/publishPack.ts', {
  '../../i18n': { t: value => value },
  './outputShare': { REPO_URL: 'https://github.com/zhouxiaoka/autoclip' },
})

function tracker() {
  const events = []
  const store = new Map()
  const storage = { getItem: key => store.get(key) ?? null, setItem: (key, value) => store.set(key, value), removeItem: key => store.delete(key) }
  const current = new workflow.WorkflowTracker(storage, () => true, (name, props) => { events.push({ name, props }); return true })
  return { current, events }
}

test('a clip reason stays on the card and never becomes an event property', () => {
  assert.equal(reason.clipReason({ evidence: '完整讲完一个例子', framing: 'speaker' }).evidence, '完整讲完一个例子')
  assert.equal(reason.clipReason({ evidence: '  ', framing: 'speaker' }).key, '已按说话人重新取景')
  assert.equal(reason.clipReason({}).key, '按内容完整度选出这段')
  const props = workflow.safeStudioProperties({ evidence: '完整讲完一个例子', title: '私人标题', share_target: 'copy_and_save', artifact_type: 'cover_3x4', ttfc_ms: 1200 })
  assert.equal(JSON.stringify(props).includes('完整'), false)
  assert.equal(JSON.stringify(props).includes('私人'), false)
  assert.equal(props.share_target, 'copy_and_save')
  assert.equal(props.artifact_type, 'cover_3x4')
  assert.equal(props.ttfc_ms, 1200)
})

test('the combined caption adds a credit line without replacing the post', () => {
  const text = pack.captionWithCredit('标题\n\n简介', 'xiaohongshu')
  assert.match(text, /^标题/)
  assert.match(text, /用 AutoClip 剪的/)
  assert.match(pack.captionWithCredit('Title', 'tiktok'), /Made with AutoClip/)
  assert.equal(pack.coverArtifact('xiaohongshu'), 'cover_3x4')
  assert.equal(pack.coverArtifact('douyin'), null)
})

test('saving a pack records combined, and the 3:4 cover only for Xiaohongshu', async () => {
  const calls = []
  await pack.savePublishPack({
    desktop: true,
    strategyId: 'xiaohongshu',
    hasCover: true,
    saveVideo: async () => { calls.push('video') },
    saveCover: async () => { calls.push('cover') },
    requestDownload: artifact => calls.push(`request:${artifact}`),
    observeDownload: async (action, artifact) => { await action(); calls.push(`saved:${artifact}`) },
    openBrowser: kind => calls.push(`browser:${kind}`),
  })
  assert.deepEqual(calls, ['video', 'saved:combined', 'cover', 'saved:cover_3x4'])

  const other = []
  await pack.savePublishPack({
    desktop: true,
    strategyId: 'douyin',
    hasCover: true,
    saveVideo: async () => { other.push('video') },
    saveCover: async () => { other.push('cover') },
    requestDownload: () => other.push('request'),
    observeDownload: async (action, artifact) => { await action(); other.push(`saved:${artifact}`) },
    openBrowser: () => other.push('browser'),
  })
  assert.deepEqual(other, ['video', 'cover', 'saved:combined'])

  const browser = []
  const mode = await pack.savePublishPack({
    desktop: false,
    strategyId: 'xiaohongshu',
    hasCover: true,
    saveVideo: async () => browser.push('video'),
    saveCover: async () => browser.push('cover'),
    requestDownload: artifact => browser.push(`request:${artifact}`),
    observeDownload: async () => browser.push('observe'),
    openBrowser: kind => browser.push(`browser:${kind}`),
  })
  assert.equal(mode, 'browser')
  assert.deepEqual(browser, ['request:combined', 'request:cover_3x4', 'browser:video', 'browser:cover'])
})

test('first-clip time uses the backend finish time and stays quiet until the flag is assigned', () => {
  const snapshot = {
    generation: { created_at: '2026-10-09T00:00:00Z', status: 'rendering' },
    drafts: [{ id: 'd1', title: '不要上传', packaging: { template: 'interview_zh' } }],
    jobs: [{ job_id: 'j1', status: 'completed', finished_at: '2026-10-09T00:01:30Z', duration_ms: 40000 }],
    output_variants: [{ id: 'v1', draft_id: 'd1', render_job_id: 'j1', strategy_id: 'xiaohongshu', status: 'completed' }],
  }
  const ready = workflow.firstClipReady(snapshot)
  assert.equal(ready.ttfc_ms, 90000)
  assert.equal(ready.strategy_id, 'xiaohongshu')
  assert.equal(ready.template, 'interview_zh')
  assert.equal(ready.stage_ms_render, 40000)
  assert.equal(JSON.stringify(ready).includes('不要上传'), false)
  assert.equal(workflow.firstClipReady({ ...snapshot, jobs: [{ job_id: 'j1', status: 'completed', duration_ms: 10 }] }), null)

  const { current, events } = tracker()
  current.watch('studio-generation', 'p1')
  const watch = current.list().find(item => item.kind === 'studio-generation')
  current.noteFirstClip(watch, snapshot, false)
  assert.equal(events.length, 0)
  current.noteFirstClip(watch, snapshot, true)
  current.noteFirstClip(watch, snapshot, true)
  assert.equal(events.filter(item => item.name === 'studio_first_clip_ready').length, 1)
  assert.equal(events[0].props.ttfc_ms, 90000)
  assert.equal(events[0].props.strategy_id, 'xiaohongshu')
})

test('the result flags stay off in the card source until their treatment is on', () => {
  const kit = fs.readFileSync(path.join(__dirname, '../src/features/studio/PublishKit.tsx'), 'utf8')
  const card = fs.readFileSync(path.join(__dirname, '../src/features/studio/OutputVariantCard.tsx'), 'utf8')
  assert.match(kit, /useFlag\('publish_pack_v2'\) === 'combined'/)
  assert.match(kit, /copyText\(postCaption\(post\)\)/)
  assert.match(kit, /t\('复制文案并保存视频和封面'\)/)
  assert.match(kit, /studio-post-cover--note/)
  assert.match(card, /useFlag\('clip_reasons'\) === true/)
  assert.match(card, /share_target: 'copy_and_save'/)
  assert.match(card, /flagAssigned\('publish_pack_v2'\)/)
})

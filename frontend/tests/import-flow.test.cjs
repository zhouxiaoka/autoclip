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

function plain(value) {
  return JSON.parse(JSON.stringify(value))
}

const memory = load('../src/features/studio/platformMemory.ts')
const paste = load('../src/features/studio/pasteStart.ts')
const readiness = load('../src/features/studio/importReadiness.ts')
const legacy = load('../src/features/studio/legacyEntrypoints.ts')
const preferences = load('../src/features/studio/importPreferencesStore.ts', { './types': { defaultImportOptions: { goal: 'auto', language: 'source', aspect: null, duration: null, instruction: '', portrait_style: 'auto' } } })
const workflow = load('../src/analytics/workflow.ts')

function storage() {
  const data = new Map()
  return { getItem: key => data.get(key) ?? null, setItem: (key, value) => { data.set(key, value) }, removeItem: key => { data.delete(key) } }
}

test('platforms stay on the current default until remembering is turned on', () => {
  const box = storage()
  memory.bindPlatformStorage(box)
  assert.deepEqual(plain(memory.resolvePlatforms(false, 'zh-CN', null)), { platforms: ['douyin'], source: 'user' })
  assert.deepEqual(plain(memory.resolvePlatforms(true, 'zh-CN', null).platforms), ['xiaohongshu', 'douyin'])
  assert.equal(memory.resolvePlatforms(true, 'zh-CN', null).source, 'locale')
  assert.deepEqual(plain(memory.resolvePlatforms(true, 'en', null).platforms), ['tiktok'])
  memory.writeRememberedPlatforms(['bilibili', 'not-a-platform', 'bilibili'])
  assert.deepEqual(plain(memory.readRememberedPlatforms()), ['bilibili'])
  assert.equal(memory.resolvePlatforms(true, 'zh-CN').source, 'remembered')
  assert.equal(memory.resolvePlatforms(false, 'zh-CN').source, 'user')
})

test('only an https bilibili or youtube link autostarts, and undo stays open for three seconds', () => {
  assert.equal(paste.importUrlKind('https://www.youtube.com/watch?v=abc'), 'youtube')
  assert.equal(paste.importUrlKind('https://b23.tv/abc'), 'bilibili')
  assert.equal(paste.importUrlKind('http://youtube.com/watch?v=abc'), null)
  assert.equal(paste.importUrlKind('https://example.com/video'), null)
  assert.equal(paste.importUrlKind('https://user:pass@youtube.com/watch?v=abc'), null)
  assert.equal(paste.shouldAutoStart('autostart', 'paste'), true)
  assert.equal(paste.shouldAutoStart('autostart', 'button'), false)
  assert.equal(paste.shouldAutoStart('button', 'paste'), false)
  assert.equal(paste.UNDO_MS, 3000)
  const deadline = paste.undoDeadline(1_000)
  assert.equal(paste.undoOpen(deadline, 3_999), true)
  assert.equal(paste.undoOpen(deadline, 4_000), false)
  assert.equal(paste.isVideoFile({ name: 'clip.MP4', type: '' }), true)
  assert.equal(paste.isVideoFile({ name: 'notes.txt', type: 'text/plain' }), false)
  paste.resetBackgroundWhisperInstall()
  assert.equal(paste.shouldBackgroundInstallWhisper(false, 'whisper_not_installed'), false)
  assert.equal(paste.shouldBackgroundInstallWhisper(true, 'whisper_not_installed'), true)
  assert.equal(paste.claimBackgroundWhisperInstall(), true)
  assert.equal(paste.claimBackgroundWhisperInstall(), false)
})

test('a link can skip whisper while a file import and an attached subtitle keep the old gate', () => {
  const missing = {
    analysis_mode: 'auto', ready: false,
    checks: {
      analysis: { ok: true, code: 'configured', repair: 'none' },
      transcription: { ok: false, code: 'whisper_not_installed', repair: 'install_whisper' },
      visual: { ok: true, code: 'optional', repair: 'none' },
      ffmpeg: { ok: true, code: 'available', repair: 'none' },
    },
  }
  const allow = { allowLinkWithoutWhisper: true }
  assert.equal(readiness.submissionBlock(missing, false, true, { ...allow, source: 'link' }), null)
  assert.equal(readiness.submissionBlock(missing, false, true, { ...allow, source: 'file' }), 'transcription')
  assert.equal(readiness.submissionBlock(missing, false, true), 'transcription')
  assert.equal(readiness.visibleIssues(missing, false, { ...allow, source: 'link' }).length, 0)
  assert.equal(readiness.transcriptionRoute({ hasSubtitle: true, skippedWhisper: true, code: 'whisper_not_installed' }), 'srt')
  assert.equal(readiness.transcriptionRoute({ hasSubtitle: false, skippedWhisper: true, code: 'whisper_not_installed' }), 'platform_subs')
  assert.equal(readiness.transcriptionRoute({ hasSubtitle: false, skippedWhisper: false, code: 'cloud_configured' }), 'cloud')
  assert.equal(readiness.transcriptionRoute({ hasSubtitle: false, skippedWhisper: false, code: 'whisper_installed' }), 'whisper')
})

test('legacy entry points hide only inside a smart project when the flag is on', () => {
  assert.equal(legacy.legacyEntrypointsHidden(false, true), false)
  assert.equal(legacy.legacyEntrypointsHidden(true, false), false)
  assert.equal(legacy.legacyEntrypointsHidden(true, true), true)
})

test('stored import preferences drop unknown fields', () => {
  const box = storage()
  preferences.bindImportPreferenceStorage(box)
  preferences.writeImportPreferences({ goal: 'highlight', language: 'zh', aspect: 'portrait', duration: 45, instruction: 'secret title', portrait_style: 'podcast' })
  const stored = preferences.readImportPreferences()
  assert.equal(stored.goal, 'highlight')
  assert.equal(stored.duration, null)
  assert.equal(stored.instruction, 'secret title')
  assert.equal(stored.portrait_style, 'podcast')
})

test('one-click properties stay inside the enum contract and never keep a url', () => {
  const props = workflow.safeStudioProperties({
    trigger: 'paste', platform_source: 'locale', transcription_route: 'platform_subs', platform_count: 2,
    has_subtitle: false, flow_id: 't-importflow-aaaaaaaa', url: 'https://youtube.com/watch?v=private', title: 'private',
    field: 'platform', stage: 'pre_import', legacy_action: 'plan_adjust',
  })
  assert.equal(props.trigger, 'paste')
  assert.equal(props.platform_source, 'locale')
  assert.equal(props.transcription_route, 'platform_subs')
  assert.equal(props.field, 'platform')
  assert.equal(props.legacy_action, 'plan_adjust')
  assert.equal(JSON.stringify(props).includes('youtube'), false)
  assert.equal(JSON.stringify(props).includes('private'), false)
  assert.equal(workflow.safeStudioProperties({ trigger: 'sometimes', platform_source: 'guess' }).trigger, undefined)
})

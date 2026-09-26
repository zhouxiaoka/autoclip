const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

function loadClassifier() {
  const file = path.join(__dirname, '../src/utils/subtitleFailure.ts')
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText
  const module = { exports: {} }
  vm.runInNewContext(code, { module, exports: module.exports })
  return module.exports
}

const { classifySubtitleFailure } = loadClassifier()

const LEGACY = '没有字幕可分析：视频不带字幕，且本地转写没有生成结果。 到「设置 → 转写」安装 Whisper 模型让 AutoClip 自动转写，或导入 .srt 字幕后重试。'

test('classifies structured codes and the four user-facing cases', () => {
  assert.equal(classifySubtitleFailure('anything', 'whisper_not_installed'), 'whisper_not_installed')
  assert.equal(classifySubtitleFailure('anything', 'whisper_install_failed'), 'whisper_install_failed')
  assert.equal(classifySubtitleFailure('anything', 'transcription_empty'), 'transcription_empty')
  assert.equal(classifySubtitleFailure('显卡失败', 'subtitle_setup'), 'subtitle_setup')
  assert.equal(classifySubtitleFailure(LEGACY), 'subtitle_unknown')
  assert.equal(
    classifySubtitleFailure('没有字幕可分析：视频不带字幕，且本地 Whisper 还没安装。到「设置 → 转写」安装。'),
    'whisper_not_installed',
  )
  assert.equal(
    classifySubtitleFailure('没有字幕可分析：视频不带字幕，且 Whisper 上次安装没有成功。'),
    'whisper_install_failed',
  )
  assert.equal(
    classifySubtitleFailure('没有字幕可分析：Whisper 已安装，但这次转写没有生成可用字幕。'),
    'transcription_empty',
  )
  assert.equal(classifySubtitleFailure('字幕文件不存在'), 'subtitle_unknown')
})

test('does not treat unrelated failures as a transcription settings problem', () => {
  assert.equal(classifySubtitleFailure('没有可用的 LLM 提供商。请到「设置 → 模型」检查。'), null)
  assert.equal(classifySubtitleFailure('没有片段通过评分筛选。到「设置 → 模型 → 最低评分阈值」调低后重试。'), null)
  const timeline = '时间线提取为空：4 个话题在对齐并按时长筛选后没有留下可用片段。 短视频里的片段常被最短时长滤掉（短片约 20 秒起），或模型给出的时间戳对不上字幕。换一条更长、口播更完整的素材后再试。'
  assert.equal(classifySubtitleFailure(timeline), null)
  assert.equal(classifySubtitleFailure(timeline, 'timeline_empty'), null)
  assert.equal(classifySubtitleFailure(''), null)
  assert.equal(classifySubtitleFailure(null, 'not_a_code'), null)
})

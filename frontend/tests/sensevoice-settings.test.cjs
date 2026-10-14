const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const ts = require('typescript')

function loadSection() {
  const jsx = (type, props) => ({ type, props })
  const modules = {
    react: { useEffect() {}, useState: value => [value, () => {}] },
    'react/jsx-runtime': { jsx, jsxs: jsx },
    'react-i18next': { useTranslation() {} },
    antd: { Select: 'Select', Switch: 'Switch' },
    '../../i18n': { t: s => s },
    '../../ui': { Btn: 'Btn', Row: 'Row', Section: 'Section', Segmented: 'Segmented', StatusDot: 'StatusDot' },
    '../../components/SpeechRecognitionConfig': { default: 'WhisperConfig' },
    './providers': { PROVIDERS: {}, providerPickerOptions: () => [] },
    './useModelSettings': {},
    './modelSettingsLogic': { connectionOf: () => undefined, mainConnection: () => undefined },
    './ProviderFields': {}, './ModelPicker': {}, '../../services/api': {},
    './AddCustomProviderDialog': { default: () => null },
    './SenseVoiceConfig': { default: 'SenseVoiceConfig' },
    './customProvider': {},
  }
  const source = fs.readFileSync('src/features/settings/AIModelSettings.tsx', 'utf8') + '\nexport const testSection = TranscriptionSection;'
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText
  const module = { exports: {} }
  vm.runInNewContext(code, { module, exports: module.exports, require: name => modules[name] || assert.fail(name) })
  return module.exports.testSection
}
function walk(node, visit) {
  if (!node || typeof node !== 'object') return null
  if (typeof node.type === 'function') {
    try { return walk(node.type(node.props || {}), visit) } catch { return null }
  }
  const hit = visit(node)
  if (hit) return hit
  const children = node.props?.children
  for (const child of Array.isArray(children) ? children.flat(5) : [children]) {
    const found = walk(child, visit)
    if (found) return found
  }
  return null
}
function findSelect(node) {
  return walk(node, n => n.type === 'Select' ? n : null)
}
test('the actual transcription selector offers SenseVoice and switches local engines without a cloud connection', () => {
  const Section = loadSection()
  let settings = { connections: [], transcription: { provider: 'whisper_local', model: 'small' } }
  const m = { settings, lists: {}, busy: {}, listErrors: {},
    update: patch => { settings = { ...settings, ...patch } },
    setTranscriptionLocal: model => { settings.transcription = { provider: 'whisper_local', model } },
    chooseProvider: () => assert.fail('must not route a local engine to a cloud provider') }
  let select = findSelect(Section({ m }))
  assert.ok(select.props.options[0].options.some(x => x.value === 'sensevoice_local'))
  select.props.onChange('sensevoice_local')
  assert.deepEqual(JSON.parse(JSON.stringify(settings.transcription)), { provider: 'sensevoice_local', model: 'SenseVoiceSmall' })
  m.settings = settings
  select = findSelect(Section({ m }))
  assert.equal(select.props.value, 'sensevoice_local')
  select.props.onChange('whisper_local')
  assert.deepEqual(settings.transcription, { provider: 'whisper_local', model: 'base' })
})

function findType(node, type) {
  return walk(node, n => n.type === type ? n : null)
}

test('SenseVoice first enable reuses the Whisper prepare row instead of a new wizard', () => {
  const page = fs.readFileSync('src/features/settings/AIModelSettings.tsx', 'utf8')
  const source = fs.readFileSync('src/features/settings/SenseVoiceConfig.tsx', 'utf8')
  assert.match(page, /SenseVoiceConfig/)
  assert.equal(/LocalModelPrepare/.test(page), false)
  assert.match(source, /LocalModelPrepare/)
  assert.equal(/向导|wizard|clipboard/i.test(source), false)
  const Section = loadSection()
  const settings = { connections: [], transcription: { provider: 'sensevoice_local', model: 'SenseVoiceSmall' } }
  const tree = Section({ m: { settings, lists: {}, busy: {}, listErrors: {}, update() {}, setTranscriptionLocal() {}, chooseProvider() {} } })
  assert.ok(findType(tree, 'SenseVoiceConfig'))
  assert.equal(findType(tree, 'Dialog'), null)
})

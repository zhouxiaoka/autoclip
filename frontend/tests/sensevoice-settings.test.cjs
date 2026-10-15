const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const ts = require('typescript')

function loadSection(section = 'TranscriptionSection') {
  const jsx = (type, props) => ({ type, props })
  const modules = {
    react: { useEffect() {}, useState() {} },
    'react/jsx-runtime': { jsx, jsxs: jsx },
    'react-i18next': { useTranslation() {} },
    antd: { Select: 'Select', Switch: 'Switch' },
    '../../i18n': { t: s => s },
    '../../ui': { Btn: 'Btn', Row: 'Row', Section: 'Section', Segmented: 'Segmented', StatusDot: 'StatusDot' },
    '../../components/SpeechRecognitionConfig': { default: 'WhisperConfig' },
    './providers': { PROVIDERS: {}, providerPickerOptions: () => [] },
    './useModelSettings': {},
    './modelSettingsLogic': {
      connectionOf: (s, role) => s.connections.find(c => c.id === s[role]?.connection_id),
      mainConnection: s => s.connections.find(c => c.id === s.analysis?.connection_id),
      presetKey: c => c.provider,
    },
    './ProviderFields': { default: 'ProviderFields' }, './ModelPicker': { default: 'ModelPicker' }, '../../services/api': {},
    './SenseVoiceConfig': { default: 'SenseVoiceConfig' },
    './ProviderCatalog': { default: 'ProviderCatalog' },
    './ProviderDetail': { default: 'ProviderDetail' },
    './providerCatalogView': { catalogPreset: () => undefined },
    './DefaultModels': { default: 'DefaultModels' },
  }
  const source = fs.readFileSync('src/features/settings/AIModelSettings.tsx', 'utf8') + `\nexport const testSection = ${section};`
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText
  const module = { exports: {} }
  vm.runInNewContext(code, { module, exports: module.exports, require: name => modules[name] || assert.fail(name) })
  return module.exports.testSection
}
function findSelect(node, type = 'Select') {
  if (!node || typeof node !== 'object') return null
  if (node.type === type) return node
  const children = node.props?.children
  for (const child of Array.isArray(children) ? children.flat(5) : [children]) {
    const found = findSelect(child, type)
    if (found) return found
  }
  return null
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
  assert.deepEqual(JSON.parse(JSON.stringify(settings.transcription)), { provider: 'sensevoice_local', model: 'SenseVoiceSmall', model_source: 'user' })
  m.settings = settings
  select = findSelect(Section({ m }))
  assert.equal(select.props.value, 'sensevoice_local')
  select.props.onChange('whisper_local')
  assert.deepEqual(settings.transcription, { provider: 'whisper_local', model: 'base' })
})

test('vision overview action and cover/ASR model rows test their own role', () => {
  for (const [section, role] of [['VisionSection', 'vision'], ['CoverSection', 'cover'], ['TranscriptionSection', 'transcription']]) {
    const calls = []
    const settings = {
      connections: [{ id: 'a', provider: 'openai' }, { id: 'separate', provider: 'openai' }],
      analysis: { connection_id: 'a', model: 'chat' },
      [role]: { connection_id: 'separate', model: 'selected', provider: 'cloud' },
      cover_enabled: true,
    }
    const m = { settings, lists: {}, busy: {}, listErrors: {}, keyHints: {}, test: role => calls.push(role) }
    const tree = loadSection(section)({ m })
    const action = role === 'vision' ? findSelect(tree, 'Btn') : findSelect(tree, 'ModelPicker')?.props.actions
    assert.ok(action)
    assert.notEqual(action.props.disabled, true)
    action.props.onClick()
    assert.deepEqual(calls, [role])
  }
})

const fs = require('node:fs')
const path = require('node:path')
const { runInSandbox } = require('./vm-sandbox.cjs')
const ts = require('typescript')

const SETTINGS = path.join(__dirname, '../src/features/settings')
const PRESETS = path.join(__dirname, '../../backend/presets/provider_presets.json')
const EVENT_CATALOG = path.join(__dirname, '../../backend/core/event_catalog.json')
const FAILURE_MESSAGES = path.join(__dirname, '../../backend/core/failure_messages.json')
function jsonModule(file) {
  const data = JSON.parse(fs.readFileSync(file, 'utf8'))
  return { default: data, __esModule: true }
}

function loadTs(file, mocks = {}, fromDir = SETTINGS) {
  // Tests that run effects pass `window` / `document` via mocks.__globals. It is not a module.
  const globals = mocks.__globals || {}
  const localMocks = mocks.__globals ? { ...mocks } : mocks
  if (localMocks !== mocks) delete localMocks.__globals
  const abs = path.isAbsolute(file) ? file : path.join(fromDir, file)
  const source = fs.readFileSync(abs, 'utf8')
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
    fileName: abs,
  })
  const exports = {}
  const requireImpl = (id) => {
    if (id in localMocks) return localMocks[id]
    if (id === '@provider-presets') return jsonModule(PRESETS)
    if (id === '@event-catalog') return jsonModule(EVENT_CATALOG)
    if (id === '@failure-messages') return jsonModule(FAILURE_MESSAGES)
    if (id === 'react/jsx-runtime' || id === 'react') return require(id)
    if (id.startsWith('.')) {
      const resolved = path.join(path.dirname(abs), id)
      // Static assets (OhMyGame-style provider icons): expose a string URL for <img src>.
      if (/\.(svg|png|jpe?g|webp|gif)(\?.*)?$/i.test(id)) {
        const asset = resolved.split('?')[0]
        if (!fs.existsSync(asset)) throw new Error(id)
        return asset
      }
      const hit = ['', '.ts', '.tsx', '.json'].map(ext => resolved + ext).find(candidate => fs.existsSync(candidate))
      if (!hit) throw new Error(id)
      if (hit.endsWith('.json')) return JSON.parse(fs.readFileSync(hit, 'utf8'))
      return loadTs(hit, mocks, path.dirname(hit))
    }
    throw new Error(id)
  }
  // console is passed explicitly so a console.error inside the module reaches the strict setup (#299).
  // URLSearchParams, Event, timers and AbortController stay explicit: setup only fills URL / URLSearchParams (#272).
  runInSandbox(outputText, { exports, URL, URLSearchParams, Event, console, ...globals, require: requireImpl, crypto: { randomUUID: () => 'uuid' }, Map, Set, setTimeout, clearTimeout, AbortController })
  return exports
}

module.exports = { loadTs, PRESETS }

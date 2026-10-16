const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

const SETTINGS = path.join(__dirname, '../src/features/settings')
const PRESETS = path.join(__dirname, '../../backend/presets/provider_presets.json')

function loadTs(file, mocks = {}, fromDir = SETTINGS) {
  const abs = path.isAbsolute(file) ? file : path.join(fromDir, file)
  const source = fs.readFileSync(abs, 'utf8')
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
    fileName: abs,
  })
  const exports = {}
  const requireImpl = (id) => {
    if (id in mocks) return mocks[id]
    if (id === '@provider-presets') {
      const data = JSON.parse(fs.readFileSync(PRESETS, 'utf8'))
      return { default: data, __esModule: true }
    }
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
  vm.runInNewContext(outputText, { exports, URL, require: requireImpl, crypto: { randomUUID: () => 'uuid' }, Map, Set })
  return exports
}

module.exports = { loadTs, PRESETS }

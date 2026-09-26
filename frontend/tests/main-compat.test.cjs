// Run the upstream TypeScript regressions with the same compiler as the app,
// including CI's Node version without relying on experimental type stripping.
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const ts = require('typescript')
const cache = new Map()
function load(file) {
  if (cache.has(file)) return cache.get(file).exports
  const compiled = new Module(file, module)
  compiled.paths = Module._nodeModulePaths(path.dirname(file))
  cache.set(file, compiled)
  const originalRequire = compiled.require.bind(compiled)
  compiled.require = id => id.endsWith('.ts') && id.startsWith('.')
    ? load(path.resolve(path.dirname(file), id)) : originalRequire(id)
  compiled._compile(ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
  }).outputText, file)
  return compiled.exports
}
load(path.resolve(__dirname, '../processingStatusPoll.test.ts'))
load(path.resolve(__dirname, '../scripts/video-categories.test.ts'))

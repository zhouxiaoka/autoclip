// Loader hook for tests/setup.cjs (#301): lets the strict setup patch happy-dom when a test loads it
// with a native import(), which never goes through Module._load.
const ENTRY = /\/happy-dom\/lib\/index\.js$/
export async function load(url, context, nextLoad) {
  const result = await nextLoad(url, context)
  if (!ENTRY.test(url) || result.format !== 'module' || result.source == null) return result
  const source = String(result.source) +
    "\n;globalThis[Symbol.for('autoclip.test.happyDomLoaded')]?.({ BrowserWindow, PropertySymbol });\n"
  return { ...result, source }
}

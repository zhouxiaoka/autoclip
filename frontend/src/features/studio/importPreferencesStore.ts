import { defaultImportOptions, type ImportOptions } from './types'

const KEY = 'autoclip.import.preferences.v1'
const GOALS = ['auto', 'content', 'highlight', 'promo']
const LANGUAGES = ['source', 'zh', 'en', 'ja']
const ASPECTS = ['original', 'portrait', 'landscape']
const STYLES = ['auto', 'interview', 'podcast']

type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

function memory(): StorageLike {
  const data = new Map<string, string>()
  return { getItem: key => data.get(key) ?? null, setItem: (key, value) => { data.set(key, value) }, removeItem: key => { data.delete(key) } }
}

function browserStorage(): StorageLike {
  try {
    if (typeof localStorage !== 'undefined') return localStorage
  } catch { /* private mode */ }
  return memory()
}

let storage: StorageLike = browserStorage()

export function bindImportPreferenceStorage(next: StorageLike) {
  storage = next
}

/** Drop unknown fields so a hand-edited value cannot change the import contract. */
export function sanitizeImportPreferences(raw: unknown): ImportOptions {
  const value = raw && typeof raw === 'object' && !Array.isArray(raw) ? raw as Record<string, unknown> : {}
  const duration = typeof value.duration === 'number' && [15, 30, 60, 90, 120].includes(value.duration) ? value.duration : null
  return {
    goal: typeof value.goal === 'string' && GOALS.includes(value.goal) ? value.goal as ImportOptions['goal'] : defaultImportOptions.goal,
    language: typeof value.language === 'string' && LANGUAGES.includes(value.language) ? value.language as ImportOptions['language'] : defaultImportOptions.language,
    aspect: typeof value.aspect === 'string' && ASPECTS.includes(value.aspect) ? value.aspect as ImportOptions['aspect'] : null,
    duration,
    instruction: typeof value.instruction === 'string' ? value.instruction.slice(0, 1000) : '',
    portrait_style: typeof value.portrait_style === 'string' && STYLES.includes(value.portrait_style) ? value.portrait_style as ImportOptions['portrait_style'] : 'auto',
  }
}

export function readImportPreferences(): ImportOptions | null {
  try {
    const raw = storage.getItem(KEY)
    if (!raw) return null
    return sanitizeImportPreferences(JSON.parse(raw))
  } catch {
    return null
  }
}

export function writeImportPreferences(value: ImportOptions) {
  try { storage.setItem(KEY, JSON.stringify(sanitizeImportPreferences(value))) } catch { /* preference is optional */ }
}

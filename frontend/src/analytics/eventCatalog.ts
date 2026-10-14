/** Tracking-plan catalog validator. Tests load docs/analytics/event_catalog.json. */

export type Catalog = {
  common: {
    required: string[]
    os: string[]
    os_aliases?: Record<string, string>
    analytics_environment: string[]
    runtime: string[]
  }
  enums: Record<string, string[]>
  privacy?: {
    forbidden_keys?: string[]
    forbidden_substrings?: string[]
    user_content_keys?: string[]
    user_submitted_events?: string[]
  }
  scan?: { ignore_events?: string[] }
  families?: Record<string, { verbs: string[]; prefixes: Record<string, Record<string, unknown>>; status?: string }>
  events: Record<string, EventSpec>
}

export type EventSpec = {
  status?: string
  domain?: string
  kind?: string
  allow?: string[]
  required?: string[]
  required_when?: Record<string, string[]>
  enums?: Record<string, string>
}

const URL_WITH_PATH = /https?:\/\/\S+\/\S+/
const OS_ALIASES: Record<string, string> = { darwin: 'macos', win32: 'windows' }

export function normalizeOs(value?: string | null, catalog?: Catalog): string | undefined {
  if (typeof value !== 'string') return undefined
  const aliases = catalog?.common.os_aliases || OS_ALIASES
  const mapped = aliases[value] || value
  const allowed = catalog?.common.os || ['macos', 'windows', 'linux', 'unknown']
  return allowed.includes(mapped) ? mapped : undefined
}

export function detectOs(): string {
  if (typeof navigator === 'undefined') return 'unknown'
  const ua = navigator.userAgent
  if (/Mac/i.test(ua)) return 'macos'
  if (/Win/i.test(ua)) return 'windows'
  if (/Linux/i.test(ua)) return 'linux'
  return 'unknown'
}

export function listedEvents(catalog: Catalog): Set<string> {
  const names = new Set(Object.keys(catalog.events || {}))
  for (const family of Object.values(catalog.families || {})) {
    for (const prefix of Object.keys(family.prefixes || {})) {
      for (const verb of family.verbs || []) names.add(`${prefix}_${verb}`)
    }
  }
  return names
}

export function ignoreEvents(catalog: Catalog): Set<string> {
  return new Set(catalog.scan?.ignore_events || [])
}

export function eventSpec(name: string, catalog: Catalog): EventSpec | undefined {
  if (catalog.events[name]) return catalog.events[name]
  for (const family of Object.values(catalog.families || {})) {
    for (const [prefix, spec] of Object.entries(family.prefixes || {})) {
      for (const verb of family.verbs || []) {
        if (name === `${prefix}_${verb}`) {
          const requiredByVerb = (spec.required_by_verb || {}) as Record<string, string[]>
          return {
            status: (spec.status as string) || family.status,
            required: requiredByVerb[verb] || (spec.required as string[] | undefined),
          }
        }
      }
    }
  }
  return undefined
}

export function validateEvent(
  name: string,
  properties: Record<string, unknown> | null | undefined,
  catalog: Catalog,
  envelope = false,
): string[] {
  if (ignoreEvents(catalog).has(name)) return []
  const spec = eventSpec(name, catalog)
  if (!spec) return [`unregistered event: ${name}`]
  const props = properties && typeof properties === 'object' ? properties : {}
  const required = [...(spec.required || [])]
  for (const [rule, extra] of Object.entries(spec.required_when || {})) {
    const [key, expected] = rule.split('=')
    if (String(props[key]) === expected) required.push(...extra)
  }
  const errors: string[] = []
  const missing = required.filter(field => props[field] === undefined || props[field] === null || props[field] === '')
  if (missing.length) errors.push(`${name} missing required fields: ${missing.join(', ')}`)
  for (const [field, enumName] of Object.entries(spec.enums || {})) {
    if (!(field in props)) continue
    const allowed = catalog.enums[enumName] || []
    if (allowed.length && !allowed.includes(String(props[field]))) {
      errors.push(`${name}.${field}=${JSON.stringify(props[field])} not in ${enumName}`)
    }
  }
  if (envelope) {
    for (const field of catalog.common.required) {
      if (props[field] === undefined || props[field] === null || props[field] === '') {
        errors.push(`${name} missing common field: ${field}`)
      }
    }
    if (props.os !== undefined && !catalog.common.os.includes(String(props.os))) {
      errors.push(`${name}.os=${JSON.stringify(props.os)} is not a canonical os`)
    }
  }
  const forbiddenKeys = new Set((catalog.privacy?.forbidden_keys || []).map(key => key.toLowerCase()))
  const forbiddenSub = (catalog.privacy?.forbidden_substrings || []).map(item => item.toLowerCase())
  const userContent = new Set((catalog.privacy?.user_content_keys || []).map(key => key.toLowerCase()))
  const submitted = new Set(catalog.privacy?.user_submitted_events || [])
  if (spec.kind === 'user_submitted') submitted.add(name)
  for (const [key, value] of Object.entries(props)) {
    if (forbiddenKeys.has(key.toLowerCase())) errors.push(`${name} has forbidden property ${key}`)
    if (userContent.has(key.toLowerCase()) && !submitted.has(name)) errors.push(`${name} has user content ${key}`)
    if (typeof value === 'string') {
      const lowered = value.toLowerCase()
      if (forbiddenSub.some(marker => lowered.includes(marker))) errors.push(`${name}.${key} looks like a secret`)
      if (URL_WITH_PATH.test(value)) errors.push(`${name}.${key} contains a full URL path`)
    }
  }
  return errors
}

const PRODUCER_CALLS = [
  /captureBusinessEvent\(\s*['"]([a-z$][a-z0-9_]*)['"]/g,
  /posthog\.capture\(\s*['"]([^'"]+)['"]/g,
  /emitOnce\([^,]+,\s*[^,]+,\s*['"]([a-z_][a-z0-9_]*)['"]/g,
  /\bevent:\s*['"]([a-z_][a-z0-9_]*)['"]/g,
  /\bevent\s*=\s*['"]([a-z_][a-z0-9_]*)['"]/g,
]
const PREFIX_CALLS: Array<[RegExp, string[]]> = [
  [/observeStudioOperation\(\s*['"]([a-z_][a-z0-9_]*)['"]/g, ['requested', 'accepted', 'request_failed']],
  [/observeOperation\(\s*['"]([a-z_][a-z0-9_]*)['"]/g, ['requested', 'accepted', 'request_failed']],
  [/beginExperience\(\s*['"]([a-z_][a-z0-9_]*)['"]/g, ['requested', 'finished']],
]
const ANALYTICS_CONST = /^\s+[A-Z][A-Za-z]+:\s*['"]([a-z_][a-z0-9_]*)['"]/gm

export function extractProducerEvents(source: string): string[] {
  const names = new Set<string>()
  for (const pattern of PRODUCER_CALLS) {
    pattern.lastIndex = 0
    let match
    while ((match = pattern.exec(source))) names.add(match[1])
  }
  for (const [pattern, verbs] of PREFIX_CALLS) {
    pattern.lastIndex = 0
    let match
    while ((match = pattern.exec(source))) {
      for (const verb of verbs) names.add(`${match[1]}_${verb}`)
    }
  }
  ANALYTICS_CONST.lastIndex = 0
  let match
  while ((match = ANALYTICS_CONST.exec(source))) names.add(match[1])
  return [...names]
}

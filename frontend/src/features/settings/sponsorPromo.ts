/**
 * Apply an already validated promotion view.
 * Saved connections are not an input. A bad view is ignored.
 * Notices stay in every language and are resolved when the screen renders.
 */
import { FIRST_RUN_CHOICES, FIRST_RUN_DEFAULT } from './firstRunGuidance'
import { PROVIDERS } from './providers'
import {
  TRUSTED_REGISTER_HOSTS,
  readPromoLocale,
  type DynamicProviderSpec,
  type LocalePromoSlice,
} from './sponsorPromoState'

const STATUSES = new Set(['healthy', 'fault', 'out_of_service'])
const SUPPORTED_LOCALES = new Set([
  'zh', 'en', 'ja', 'ko', 'es', 'fr', 'pt', 'ru', 'id', 'tr', 'vi', 'de',
  'it', 'pl', 'th', 'nl', 'uk', 'hi', 'ar',
])
const LOCALE_CODE_RE = /^[a-z]{2,3}$/
const DYNAMIC_ID_RE = /^[a-z][a-z0-9_-]{1,31}$/
const DYNAMIC_CAPABILITIES = new Set(['language', 'vision', 'image', 'video', 'asr'])
const DYNAMIC_CANDIDATE_ROLES = new Set(['analysis', 'vision', 'asr', 'image'])
const RESERVED_DYNAMIC_IDS = new Set(['other', 'compatible', 'custom', 'local', 'default', 'system'])

const NOTICE_IDS = Object.keys(TRUSTED_REGISTER_HOSTS)

export interface AppliedSponsorPromo {
  choices: string[]
  defaultChoice: string
  firstRunChoices?: string[]
  firstRunDefault?: string
  notices: Record<string, Record<string, string>>
  badges?: Record<string, string | Record<string, string>>
  registerUrls: Record<string, string>
  statuses: Record<string, string>
  byLocale?: Record<string, LocalePromoSlice>
  providers?: DynamicProviderSpec[]
  sequence?: number
  revision?: number
  /** Process epoch of the publisher. A restart mints a new one and resets revision. */
  instance?: string
  pending?: boolean
  source?: string
}

export interface UsageNotice {
  provider: string
  label: string
  status: string
  text: string
}

function hostOf(url: string): string {
  try { return new URL(url).hostname.toLowerCase().replace(/\.$/, '') } catch { return '' }
}

function isPublicHttpsUrl(value: unknown, allowQuery = true): string | null {
  if (typeof value !== 'string') return null
  const url = value.trim()
  if (!url || url.length > 256 || !url.startsWith('https://')) return null
  try {
    const parsed = new URL(url)
    const host = parsed.hostname.toLowerCase().replace(/^\[|\]$/g, '').replace(/\.$/, '')
    if (
      parsed.protocol !== 'https:'
      || parsed.username
      || parsed.password
      || parsed.hash
      || (!allowQuery && parsed.search)
      || (parsed.port && parsed.port !== '443')
      || !host
      || !host.includes('.')
      || host === 'localhost'
      || host.endsWith('.localhost')
      || host.endsWith('.local')
      || host.endsWith('.internal')
      || /^\d+\.\d+\.\d+\.\d+$/.test(host)
      || host.includes(':')
    ) return null
    return url
  } catch {
    return null
  }
}

function cleanText(value: unknown, maxLen: number): string | null {
  if (typeof value !== 'string') return null
  const text = value.replace(/\s+/g, ' ').trim()
  if (!text || text.length > maxLen || text.includes('<') || text.includes('>') || text.toLowerCase().includes('://')) return null
  return text
}

function parseLocalizedMap(raw: unknown, maxLen: number, requireEn = false): Record<string, string> | null {
  if (typeof raw === 'string') {
    const cleaned = cleanText(raw, maxLen)
    return cleaned ? { en: cleaned } : null
  }
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  const entries = Object.entries(raw as Record<string, unknown>)
  if (!entries.length) return null
  const out: Record<string, string> = {}
  for (const [loc, val] of entries) {
    const key = loc.toLowerCase().split('-')[0]
    if (!LOCALE_CODE_RE.test(key)) return null
    const cleaned = cleanText(val, maxLen)
    if (!cleaned) return null
    if (SUPPORTED_LOCALES.has(key)) out[key] = cleaned
  }
  if (requireEn && !out.en) return null
  return out
}

function parseLocaleList(raw: unknown): string[] | null {
  if (!Array.isArray(raw)) return null
  const seen = new Set<string>()
  const known: string[] = []
  for (const item of raw) {
    if (typeof item !== 'string' || !LOCALE_CODE_RE.test(item) || seen.has(item)) return null
    seen.add(item)
    if (SUPPORTED_LOCALES.has(item)) known.push(item)
  }
  return known
}

function parseDynamicProviders(raw: unknown): DynamicProviderSpec[] | null {
  if (raw === undefined) return []
  if (!Array.isArray(raw) || raw.length > 16) return null
  const seen = new Set<string>()
  const out: DynamicProviderSpec[] = []
  for (const entry of raw) {
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) return null
    const row = entry as Record<string, unknown>
    const id = typeof row.id === 'string' ? row.id : ''
    if (!DYNAMIC_ID_RE.test(id) || id in PROVIDERS || id in TRUSTED_REGISTER_HOSTS || RESERVED_DYNAMIC_IDS.has(id) || seen.has(id)) return null
    const name = parseLocalizedMap(row.name, 48, true)
    const baseUrl = isPublicHttpsUrl(row.base_url, false)
    const registerUrl = isPublicHttpsUrl(row.register_url, true)
    const docsUrl = isPublicHttpsUrl(row.docs_url, true)
    if (!name || !baseUrl || !registerUrl || !docsUrl || baseUrl.replace(/\/+$/, '').toLowerCase().endsWith('/chat/completions')) return null
    if (!Array.isArray(row.capabilities) || !row.capabilities.length) return null
    const capabilities: string[] = []
    for (const cap of row.capabilities) {
      if (typeof cap !== 'string' || !DYNAMIC_CAPABILITIES.has(cap) || capabilities.includes(cap)) return null
      capabilities.push(cap)
    }
    const placeholder = cleanText(row.placeholder ?? 'sk-…', 32)
    if (!placeholder) return null
    const group = row.group === 'recommended' ? 'recommended' : row.group === undefined || row.group === 'popular' ? 'popular' : null
    if (!group) return null
    const hint = row.hint !== undefined ? parseLocalizedMap(row.hint, 240, false) : undefined
    if (row.hint !== undefined && !hint) return null
    const offer = row.offer !== undefined ? parseLocalizedMap(row.offer, 64, false) : undefined
    if (row.offer !== undefined && !offer) return null
    const iconUrl = row.icon_url !== undefined ? isPublicHttpsUrl(row.icon_url, true) : undefined
    if (row.icon_url !== undefined && !iconUrl) return null
    let candidates: DynamicProviderSpec['candidates']
    if (row.candidates !== undefined) {
      if (!row.candidates || typeof row.candidates !== 'object' || Array.isArray(row.candidates)) return null
      candidates = {}
      for (const [role, list] of Object.entries(row.candidates as Record<string, unknown>)) {
        if (!DYNAMIC_CANDIDATE_ROLES.has(role) || !Array.isArray(list) || list.length > 8) return null
        const models: string[] = []
        for (const item of list) {
          const clean = cleanText(item, 128)
          if (!clean) return null
          models.push(clean)
        }
        candidates[role as keyof NonNullable<DynamicProviderSpec['candidates']>] = models
      }
    }
    let locales: string[] | undefined
    if (row.locales !== undefined) {
      const parsedLocales = parseLocaleList(row.locales)
      if (parsedLocales === null) return null
      locales = parsedLocales
    }
    seen.add(id)
    out.push({
      id,
      name,
      baseUrl: baseUrl.replace(/\/+$/, ''),
      registerUrl,
      docsUrl,
      placeholder,
      capabilities,
      group,
      ...(hint && Object.keys(hint).length ? { hint } : {}),
      ...(offer && Object.keys(offer).length ? { offer } : {}),
      ...(iconUrl ? { iconUrl } : {}),
      ...(candidates ? { candidates } : {}),
      ...(locales !== undefined ? { locales } : {}),
    })
  }
  return out
}

function packagedHost(id: string, dynamicHosts: Record<string, string>): string {
  if (dynamicHosts[id]) return dynamicHosts[id]
  const trusted = TRUSTED_REGISTER_HOSTS[id] || ''
  const sponsor = PROVIDERS[id as keyof typeof PROVIDERS]?.sponsor
  if (!sponsor) return trusted
  return hostOf(sponsor.registerUrl) === trusted ? trusted : ''
}

function unwrap(response: unknown): Record<string, unknown> | null {
  if (!response || typeof response !== 'object') return null
  const record = response as Record<string, unknown>
  const body = record.choices ? record : record.data
  return body && typeof body === 'object' && !Array.isArray(body) ? body as Record<string, unknown> : null
}

function parseSlice(
  rawChoices: unknown,
  rawDefault: unknown,
  rawUrls: unknown,
  statuses: Record<string, string>,
  promoChoices: readonly string[],
  dynamicHosts: Record<string, string>,
  rawFirstRunChoices?: unknown,
  rawFirstRunDefault?: unknown,
): LocalePromoSlice | null {
  if (!Array.isArray(rawChoices) || typeof rawDefault !== 'string') return null
  const choices: string[] = []
  for (const id of rawChoices) {
    if (typeof id !== 'string' || !promoChoices.includes(id) || choices.includes(id)) return null
    if (statuses[id] === 'out_of_service') return null
    choices.push(id)
  }
  if (choices[choices.length - 1] !== 'other') return null
  const defaultChoice = choices.includes(rawDefault) ? rawDefault : choices[0]
  const registerUrls: Record<string, string> = {}
  const urlMap = rawUrls && typeof rawUrls === 'object' ? rawUrls as Record<string, unknown> : {}
  for (const id of choices) {
    if (id === 'other') continue
    const url = urlMap[id]
    if (typeof url !== 'string') continue
    if (hostOf(url) !== packagedHost(id, dynamicHosts) || !url.startsWith('https://')) return null
    registerUrls[id] = url
  }
  let firstRunChoices: string[] | undefined
  let firstRunDefault: string | undefined
  if (rawFirstRunChoices !== undefined) {
    if (!Array.isArray(rawFirstRunChoices)) return null
    const parsedFr: string[] = []
    for (const id of rawFirstRunChoices) {
      if (typeof id !== 'string' || !choices.includes(id) || parsedFr.includes(id)) return null
      parsedFr.push(id)
    }
    if (parsedFr[parsedFr.length - 1] !== 'other') return null
    firstRunChoices = parsedFr
    firstRunDefault = typeof rawFirstRunDefault === 'string' && parsedFr.includes(rawFirstRunDefault)
      ? rawFirstRunDefault
      : parsedFr[0]
  }
  return {
    choices,
    defaultChoice,
    registerUrls,
    ...(firstRunChoices ? { firstRunChoices, firstRunDefault } : {}),
  }
}

export function applySponsorPromo(view: unknown): AppliedSponsorPromo | null {
  if (!view || typeof view !== 'object' || Array.isArray(view)) return null
  const record = view as Record<string, unknown>
  const providers = parseDynamicProviders(record.providers)
  if (providers === null) return null
  const dynamicHosts: Record<string, string> = {}
  for (const dp of providers) dynamicHosts[dp.id] = hostOf(dp.registerUrl)
  const allowedIds = [...NOTICE_IDS, ...providers.map(dp => dp.id)]
  const promoChoices = [...allowedIds, 'other']
  const rawStatuses = record.statuses && typeof record.statuses === 'object' ? record.statuses as Record<string, unknown> : {}
  const statuses: Record<string, string> = {}
  for (const id of allowedIds) {
    const status = rawStatuses[id]
    if (status === undefined) continue
    if (!STATUSES.has(String(status))) return null
    statuses[id] = String(status)
  }
  const top = parseSlice(
    record.choices,
    record.default,
    record.register_urls,
    statuses,
    promoChoices,
    dynamicHosts,
    record.first_run_choices,
    record.first_run_default,
  )
  if (!top) return null
  let byLocale: Record<string, LocalePromoSlice> | undefined
  if (record.by_locale !== undefined) {
    if (!record.by_locale || typeof record.by_locale !== 'object' || Array.isArray(record.by_locale)) return null
    byLocale = {}
    for (const [loc, rawSlice] of Object.entries(record.by_locale as Record<string, unknown>)) {
      if (!LOCALE_CODE_RE.test(loc) || !rawSlice || typeof rawSlice !== 'object' || Array.isArray(rawSlice)) return null
      const entry = rawSlice as Record<string, unknown>
      const parsed = parseSlice(
        entry.choices,
        entry.default,
        entry.register_urls,
        statuses,
        promoChoices,
        dynamicHosts,
        entry.first_run_choices,
        entry.first_run_default,
      )
      if (!parsed) return null
      if (SUPPORTED_LOCALES.has(loc)) byLocale[loc] = parsed
    }
  }
  const notices: Record<string, Record<string, string>> = {}
  const rawNotices = record.notices && typeof record.notices === 'object' ? record.notices as Record<string, unknown> : {}
  for (const id of allowedIds) {
    const localized = rawNotices[id]
    if (!localized || typeof localized !== 'object') continue
    const texts: Record<string, string> = {}
    for (const [language, value] of Object.entries(localized as Record<string, unknown>)) {
      if (typeof value !== 'string' || !value.trim() || value.includes('://') || value.includes('<')) continue
      texts[language.toLowerCase().split('-')[0]] = value.trim()
    }
    if (Object.keys(texts).length) notices[id] = texts
  }
  const badges: Record<string, string | Record<string, string>> = {}
  if (record.badges !== undefined) {
    if (!record.badges || typeof record.badges !== 'object' || Array.isArray(record.badges)) return null
    for (const [id, rawBadge] of Object.entries(record.badges as Record<string, unknown>)) {
      if (!allowedIds.includes(id)) continue
      if (rawBadge === '') {
        badges[id] = ''
        continue
      }
      const parsed = parseLocalizedMap(rawBadge, 48, false)
      if (parsed === null) return null
      if (Object.keys(parsed).length) badges[id] = parsed
    }
  }
  return {
    choices: top.choices,
    defaultChoice: top.defaultChoice,
    ...(top.firstRunChoices ? { firstRunChoices: top.firstRunChoices, firstRunDefault: top.firstRunDefault } : {}),
    notices,
    ...(Object.keys(badges).length ? { badges } : {}),
    registerUrls: top.registerUrls,
    statuses,
    ...(byLocale ? { byLocale } : {}),
    ...(providers.length ? { providers } : {}),
    sequence: typeof record.sequence === 'number' ? record.sequence : undefined,
    revision: typeof record.revision === 'number' ? record.revision : undefined,
    instance: typeof record.instance === 'string' && record.instance ? record.instance : undefined,
    pending: record.pending === true,
    source: typeof record.source === 'string' ? record.source : undefined,
  }
}

export function bundledSponsorPromo(): AppliedSponsorPromo {
  return { choices: [...FIRST_RUN_CHOICES], defaultChoice: FIRST_RUN_DEFAULT, notices: {}, registerUrls: {}, statuses: {} }
}

export function noticeText(notices: Record<string, string> | undefined, language = 'zh'): string {
  if (!notices) return ''
  const key = (language || 'zh').toLowerCase().split('-')[0]
  return notices[key] || notices.en || notices.zh || ''
}

export function providerServiceNotice(
  applied: AppliedSponsorPromo | null,
  provider?: string | null,
  language = 'zh',
): { status: string; text: string } | null {
  if (!applied || typeof applied !== 'object' || !applied.statuses || !provider) return null
  const status = applied.statuses[provider]
  if (status !== 'fault' && status !== 'out_of_service') return null
  return { status, text: noticeText(applied.notices?.[provider], language) }
}

export interface UsageSlot {
  provider?: string
  label: string
}

/** Readonly. The same provider can appear once per enabled slot, never twice for one label. */
export function enabledUsageNotices(
  slots: UsageSlot[],
  applied: AppliedSponsorPromo | null,
  language = 'zh',
): UsageNotice[] {
  const seen = new Set<string>()
  const notices: UsageNotice[] = []
  for (const slot of slots) {
    if (!slot.provider) continue
    const key = `${slot.provider}\0${slot.label}`
    if (seen.has(key)) continue
    seen.add(key)
    const notice = providerServiceNotice(applied, slot.provider, language)
    if (!notice) continue
    notices.push({ provider: slot.provider, label: slot.label, status: notice.status, text: notice.text })
  }
  return notices
}

async function readPromotion(params: Record<string, string | number>) {
  const { default: api } = await import('../../services/api')
  const response = await api.get('/settings/sponsor-promo', {
    timeout: params.wait ? 5000 : 4000,
    retry: false,
    params,
  })
  return unwrap(response)
}

export async function loadSponsorPromo(trigger: 'startup' | 'settings' | 'interval' | 'resume' = 'settings'): Promise<AppliedSponsorPromo | null> {
  try {
    const locale = readPromoLocale()
    let body = await readPromotion(locale ? { trigger, locale } : { trigger })
    let applied = body ? applySponsorPromo(body) : null
    let rounds = 0
    // Two short reads. A generation can accept after this returns; the watcher keeps following.
    while (body?.pending === true && rounds < 2) {
      rounds += 1
      body = await readPromotion(locale ? { after: Number(body.revision || 0), wait: 2, locale } : { after: Number(body.revision || 0), wait: 2 })
      applied = (body && applySponsorPromo(body)) || applied
    }
    return applied
  } catch {
    return null
  }
}

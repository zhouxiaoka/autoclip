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
  type LocalePromoSlice,
} from './sponsorPromoState'

const STATUSES = new Set(['healthy', 'fault', 'out_of_service'])
const SUPPORTED_LOCALES = new Set(['zh', 'en', 'ja', 'ko', 'es', 'fr', 'pt', 'ru', 'id', 'tr', 'vi', 'de'])

const NOTICE_IDS = Object.keys(TRUSTED_REGISTER_HOSTS)
const PROMO_CHOICES = [...NOTICE_IDS, 'other']

export interface AppliedSponsorPromo {
  choices: string[]
  defaultChoice: string
  notices: Record<string, Record<string, string>>
  registerUrls: Record<string, string>
  statuses: Record<string, string>
  byLocale?: Record<string, LocalePromoSlice>
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
  try { return new URL(url).hostname.toLowerCase() } catch { return '' }
}

function packagedHost(id: string): string {
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
): LocalePromoSlice | null {
  if (!Array.isArray(rawChoices) || typeof rawDefault !== 'string') return null
  const choices: string[] = []
  for (const id of rawChoices) {
    if (typeof id !== 'string' || !PROMO_CHOICES.includes(id) || choices.includes(id)) return null
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
    if (hostOf(url) !== packagedHost(id) || !url.startsWith('https://')) return null
    registerUrls[id] = url
  }
  return { choices, defaultChoice, registerUrls }
}

export function applySponsorPromo(view: unknown): AppliedSponsorPromo | null {
  if (!view || typeof view !== 'object' || Array.isArray(view)) return null
  const record = view as Record<string, unknown>
  const rawStatuses = record.statuses && typeof record.statuses === 'object' ? record.statuses as Record<string, unknown> : {}
  const statuses: Record<string, string> = {}
  for (const id of NOTICE_IDS) {
    const status = rawStatuses[id]
    if (status === undefined) continue
    if (!STATUSES.has(String(status))) return null
    statuses[id] = String(status)
  }
  const top = parseSlice(record.choices, record.default, record.register_urls, statuses)
  if (!top) return null
  let byLocale: Record<string, LocalePromoSlice> | undefined
  if (record.by_locale !== undefined) {
    if (!record.by_locale || typeof record.by_locale !== 'object' || Array.isArray(record.by_locale)) return null
    byLocale = {}
    for (const [loc, rawSlice] of Object.entries(record.by_locale as Record<string, unknown>)) {
      if (!SUPPORTED_LOCALES.has(loc) || !rawSlice || typeof rawSlice !== 'object' || Array.isArray(rawSlice)) return null
      const entry = rawSlice as Record<string, unknown>
      const parsed = parseSlice(entry.choices, entry.default, entry.register_urls, statuses)
      if (!parsed) return null
      byLocale[loc] = parsed
    }
  }
  const notices: Record<string, Record<string, string>> = {}
  const rawNotices = record.notices && typeof record.notices === 'object' ? record.notices as Record<string, unknown> : {}
  for (const id of NOTICE_IDS) {
    const localized = rawNotices[id]
    if (!localized || typeof localized !== 'object') continue
    const texts: Record<string, string> = {}
    for (const [language, value] of Object.entries(localized as Record<string, unknown>)) {
      if (typeof value !== 'string' || !value.trim() || value.includes('://') || value.includes('<')) continue
      texts[language.toLowerCase().split('-')[0]] = value.trim()
    }
    if (Object.keys(texts).length) notices[id] = texts
  }
  return {
    choices: top.choices,
    defaultChoice: top.defaultChoice,
    notices,
    registerUrls: top.registerUrls,
    statuses,
    ...(byLocale ? { byLocale } : {}),
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

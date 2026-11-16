/**
 * Apply an already validated promotion view.
 * Saved connections are not an input. A bad view is ignored.
 * Notices stay in every language and are resolved when the screen renders.
 */
import { FIRST_RUN_CHOICES, FIRST_RUN_DEFAULT } from './firstRunGuidance'
import { PROVIDERS } from './providers'
import { TRUSTED_REGISTER_HOSTS } from './sponsorPromoState'

const STATUSES = new Set(['healthy', 'fault', 'out_of_service'])

const PROMO_CHOICES = ['apimart', 'api88', 'infistar', 'other'] as const
const NOTICE_IDS = ['apimart', 'api88', 'infistar'] as const

export interface AppliedSponsorPromo {
  choices: Array<(typeof PROMO_CHOICES)[number]>
  defaultChoice: (typeof PROMO_CHOICES)[number]
  notices: Record<string, Record<string, string>>
  registerUrls: Record<string, string>
  statuses: Record<string, string>
  sequence?: number
  revision?: number
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

export function applySponsorPromo(view: unknown): AppliedSponsorPromo | null {
  if (!view || typeof view !== 'object' || Array.isArray(view)) return null
  const record = view as Record<string, unknown>
  if (!Array.isArray(record.choices) || typeof record.default !== 'string') return null
  const choices: Array<(typeof PROMO_CHOICES)[number]> = []
  for (const id of record.choices) {
    if (typeof id !== 'string' || !PROMO_CHOICES.includes(id as (typeof PROMO_CHOICES)[number]) || choices.includes(id as (typeof PROMO_CHOICES)[number])) return null
    choices.push(id as (typeof PROMO_CHOICES)[number])
  }
  if (choices[choices.length - 1] !== 'other') return null
  const fallback = choices.includes(record.default as (typeof PROMO_CHOICES)[number]) ? record.default as (typeof PROMO_CHOICES)[number] : choices[0]
  const rawStatuses = record.statuses && typeof record.statuses === 'object' ? record.statuses as Record<string, unknown> : {}
  const statuses: Record<string, string> = {}
  for (const id of NOTICE_IDS) {
    const status = rawStatuses[id]
    if (status === undefined) continue
    if (!STATUSES.has(String(status))) return null
    if (choices.includes(id as (typeof PROMO_CHOICES)[number]) && status === 'out_of_service') return null
    statuses[id] = String(status)
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
  const registerUrls: Record<string, string> = {}
  const rawUrls = record.register_urls && typeof record.register_urls === 'object' ? record.register_urls as Record<string, unknown> : {}
  for (const id of choices) {
    if (id === 'other') continue
    const url = rawUrls[id]
    if (typeof url !== 'string') continue
    if (hostOf(url) !== packagedHost(id) || !url.startsWith('https://')) return null
    registerUrls[id] = url
  }
  return {
    choices,
    defaultChoice: fallback,
    notices,
    registerUrls,
    statuses,
    sequence: typeof record.sequence === 'number' ? record.sequence : undefined,
    revision: typeof record.revision === 'number' ? record.revision : undefined,
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
    let body = await readPromotion({ trigger })
    let applied = body ? applySponsorPromo(body) : null
    let rounds = 0
    while (body?.pending === true && rounds < 2) {
      rounds += 1
      body = await readPromotion({ after: Number(body.revision || 0), wait: 2 })
      applied = (body && applySponsorPromo(body)) || applied
    }
    return applied
  } catch {
    return null
  }
}

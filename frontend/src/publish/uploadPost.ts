/** 海外发布（Upload-Post）的纯逻辑。与后端 pick_preset / 私密字段约定保持一致。 */

export const VERTICAL_PLATFORMS = ['tiktok', 'instagram', 'youtube', 'facebook', 'threads', 'pinterest'] as const

export const PLATFORM_LABEL: Record<string, string> = {
  tiktok: 'TikTok',
  instagram: 'Instagram',
  youtube: 'YouTube',
  facebook: 'Facebook',
  linkedin: 'LinkedIn',
  x: 'X',
  threads: 'Threads',
  pinterest: 'Pinterest',
  bluesky: 'Bluesky',
  reddit: 'Reddit',
  discord: 'Discord',
  telegram: 'Telegram',
  google_business: 'Google Business',
  mastodon: 'Mastodon',
  wordpress: 'WordPress',
}

export type PublishVisibility = 'private' | 'public'

export function platformLabel(platform: string): string {
  return PLATFORM_LABEL[platform] || platform
}

/** 没指定预设时的规则：有竖屏平台就用 9:16 shorts，否则原画。界面若已选预设，以用户选择为准。 */
export function pickPreset(platforms: string[]): 'shorts' | 'original' {
  return platforms.some((p) => (VERTICAL_PLATFORMS as readonly string[]).includes(p)) ? 'shorts' : 'original'
}

/** 默认勾选已连接的竖屏平台；一个都没有时勾选全部已连接平台。 */
export function defaultPlatforms(connected: string[]): string[] {
  const vertical = connected.filter((p) => (VERTICAL_PLATFORMS as readonly string[]).includes(p))
  return vertical.length ? vertical : connected.slice()
}

/**
 * 「仅自己」只带文档里约定的字段：TikTok privacy_level=SELF_ONLY，YouTube privacyStatus=private。
 * 公开不附加字段，避免把无关平台的私密参数一并送出去。
 */
export function privateExtra(platforms: string[], visibility: PublishVisibility): Record<string, string> {
  if (visibility !== 'private') return {}
  const extra: Record<string, string> = {}
  if (platforms.includes('tiktok')) extra.privacy_level = 'SELF_ONLY'
  if (platforms.includes('youtube')) extra.privacyStatus = 'private'
  return extra
}

export type ScheduleResult =
  | { ok: true; scheduled_date?: string; timezone?: string }
  | { ok: false; reason: 'empty' | 'past' }

/** 现在发不带时间。定时要求本地时间晚于现在，秒数补成 ISO，时区交给调用方。 */
export function buildSchedule(when: 'now' | 'later', localValue: string, timeZone: string, nowMs: number): ScheduleResult {
  if (when === 'now') return { ok: true }
  const value = localValue.trim()
  if (!value) return { ok: false, reason: 'empty' }
  const parsed = Date.parse(value)
  if (Number.isNaN(parsed) || parsed <= nowMs) return { ok: false, reason: 'past' }
  return {
    ok: true,
    scheduled_date: value.length === 16 ? `${value}:00` : value,
    timezone: timeZone || 'UTC',
  }
}

export function recordStatusKey(status: string | undefined): string {
  if (status === 'scheduled') return '已排期'
  if (status === 'cancelled') return '已取消'
  if (status === 'failed' || status === 'not_found') return '发布失败'
  if (status === 'completed') return '已发出'
  return '处理中'
}

const WEEK_OFFSETS = [0, 2, 4]
const BUSY_RECORD = new Set(['scheduled', 'submitted', 'completed', 'processing', 'pending', 'running', 'queued'])

export interface WeekClip {
  id: string
  title: string
  score: number
}

export interface WeekRecord {
  clip_id?: string
  title?: string
  status?: string
  scheduled_date?: string | null
  submitted_at?: string
}

export interface WeekSlotPlan {
  at: Date
  stamp: string
  state: 'new' | 'taken' | 'empty'
  clipId?: string
  title?: string
  score?: number
}

export function localStamp(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:00`
}

export function dayKey(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function recordInstant(record: { scheduled_date?: string | null; submitted_at?: string }): Date | null {
  const raw = record.scheduled_date || record.submitted_at
  if (!raw) return null
  const date = new Date(raw)
  return Number.isNaN(date.getTime()) ? null : date
}

/** 周一开头的六周格子。month 从 0 起。 */
export function monthCells(year: number, month: number): { date: Date; inMonth: boolean }[] {
  const first = new Date(year, month, 1)
  const offset = (first.getDay() + 6) % 7
  const start = new Date(year, month, 1 - offset)
  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(start)
    date.setDate(start.getDate() + index)
    return { date, inMonth: date.getMonth() === month }
  })
}

function mondayOf(now: Date): Date {
  const date = new Date(now)
  const diff = date.getDay() === 0 ? -6 : 1 - date.getDay()
  date.setDate(date.getDate() + diff)
  date.setHours(0, 0, 0, 0)
  return date
}

function slotsFromMonday(monday: Date): Date[] {
  return WEEK_OFFSETS.map((offset) => {
    const date = new Date(monday)
    date.setDate(monday.getDate() + offset)
    date.setHours(9, 0, 0, 0)
    return date
  })
}

/** 这一周还没到的周一、三、五 09:00。都过了就用下一周。 */
export function upcomingWeekSlots(now: Date): Date[] {
  const monday = mondayOf(now)
  const current = slotsFromMonday(monday).filter((slot) => slot.getTime() > now.getTime())
  if (current.length) return current
  const next = new Date(monday)
  next.setDate(monday.getDate() + 7)
  return slotsFromMonday(next)
}

function sameMinute(left: Date, right: Date): boolean {
  return left.getFullYear() === right.getFullYear()
    && left.getMonth() === right.getMonth()
    && left.getDate() === right.getDate()
    && left.getHours() === right.getHours()
    && left.getMinutes() === right.getMinutes()
}

/** 还没发出、也没在排期里的切片。失败和已取消的可以再排。 */
export function remainingClips(clips: WeekClip[], records: WeekRecord[]): WeekClip[] {
  const busyIds = new Set(records.filter((record) => BUSY_RECORD.has(record.status || '') && record.clip_id).map((record) => record.clip_id as string))
  return clips.filter((clip) => clip.id && !busyIds.has(clip.id))
}

/** 月历默认停在下一条未来排期所在的月份；没有就停在今天。month 从 0 起。 */
export function focusMonth(records: WeekRecord[], now: Date): { year: number; month: number } {
  const upcoming = records
    .filter((record) => record.status === 'scheduled')
    .map((record) => recordInstant(record))
    .filter((date): date is Date => !!date && date.getTime() > now.getTime())
    .sort((a, b) => a.getTime() - b.getTime())
  const focus = upcoming[0] || now
  return { year: focus.getFullYear(), month: focus.getMonth() }
}

/** 高分优先。已经发过或排过的切片不再占用空档；撞上已有排期的时间留空给那条记录。 */
export function planWeek(clips: WeekClip[], records: WeekRecord[], now: Date): WeekSlotPlan[] {
  const ranked = remainingClips(clips, records)
    .sort((a, b) => (b.score || 0) - (a.score || 0) || a.title.localeCompare(b.title))
  let index = 0
  return upcomingWeekSlots(now).map((at) => {
    const taken = records.find((record) => record.status === 'scheduled' && record.scheduled_date && sameMinute(new Date(record.scheduled_date), at))
    const stamp = localStamp(at)
    if (taken) return { at, stamp, state: 'taken', title: taken.title, clipId: taken.clip_id }
    const clip = ranked[index]
    index += 1
    if (!clip) return { at, stamp, state: 'empty' }
    return { at, stamp, state: 'new', clipId: clip.id, title: clip.title, score: clip.score }
  })
}

export function recordTone(status: string | undefined): 'ok' | 'error' | 'accent' | 'muted' {
  if (status === 'completed') return 'ok'
  if (status === 'failed' || status === 'not_found') return 'error'
  if (status === 'cancelled') return 'muted'
  return 'accent'
}

export function readApiDetail(err: unknown, fallback: string): string {
  if (!err || typeof err !== 'object') return fallback
  const detail = (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (typeof item === 'string') return item
      if (item && typeof item === 'object' && 'msg' in item && typeof (item as { msg: unknown }).msg === 'string') {
        return (item as { msg: string }).msg
      }
      return ''
    }).filter(Boolean)
    if (parts.length) return parts.join('；')
  }
  const message = (err as { message?: unknown }).message
  return typeof message === 'string' && message.trim() ? message : fallback
}

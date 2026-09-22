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

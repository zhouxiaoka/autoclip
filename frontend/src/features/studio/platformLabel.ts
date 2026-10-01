import { t } from '../../i18n'

/** Localized display name for a platform strategy id; the single source for Studio UI labels. */
export function platformLabel(id: string): string {
  switch (id) {
    case 'douyin': return t('抖音')
    case 'tiktok': return 'TikTok'
    case 'instagram_reels': return 'Instagram Reels'
    case 'youtube_shorts': return 'YouTube Shorts'
    case 'youtube_long': return t('YouTube 视频')
    case 'bilibili': return t('B站')
    case 'xiaohongshu': return t('小红书')
    case 'original': return t('原画')
    default: return t('所选平台')
  }
}

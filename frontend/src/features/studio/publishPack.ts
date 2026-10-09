import { t } from '../../i18n'
import { REPO_URL } from './outputShare'

const ENGLISH = new Set(['tiktok', 'instagram_reels', 'youtube_shorts', 'youtube_long'])

export type PackArtifact = 'combined' | 'cover_3x4'

/** Credit line pasted with the combined action. The plain copy button does not use this. */
export function captionWithCredit(caption: string, strategyId: string): string {
  const credit = `${ENGLISH.has(strategyId) ? 'Made with AutoClip' : t('用 AutoClip 剪的')} · ${REPO_URL}`
  return caption ? `${caption}\n\n${credit}` : credit
}

export function coverArtifact(strategyId: string): 'cover_3x4' | null {
  return strategyId === 'xiaohongshu' ? 'cover_3x4' : null
}

/** Copy already happened. This only saves the video and, when present, the cover. */
export async function savePublishPack(input: {
  desktop: boolean
  strategyId: string
  hasCover: boolean
  saveVideo: () => Promise<void>
  saveCover: () => Promise<void>
  requestDownload: (artifact: PackArtifact) => void
  observeDownload: (action: () => Promise<void>, artifact: PackArtifact) => Promise<void>
  openBrowser: (kind: 'video' | 'cover') => void
}): Promise<'native' | 'browser'> {
  const cover = coverArtifact(input.strategyId)
  if (!input.desktop) {
    input.requestDownload('combined')
    if (cover && input.hasCover) input.requestDownload(cover)
    input.openBrowser('video')
    if (input.hasCover) input.openBrowser('cover')
    return 'browser'
  }
  await input.observeDownload(async () => {
    await input.saveVideo()
    if (input.hasCover && !cover) await input.saveCover()
  }, 'combined')
  if (cover && input.hasCover) await input.observeDownload(() => input.saveCover(), 'cover_3x4')
  return 'native'
}

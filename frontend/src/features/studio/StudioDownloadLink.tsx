import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { message } from 'antd'
import { studioDownloadRequested, observeStudioDownload, type VariantProperties } from '../../analytics/studio'
import { captureStudioException } from '../../desktop/sentry'
import { studioApi } from './api'
import { isDesktopDownload, saveStudioExport } from './nativeDownload'

export default function StudioDownloadLink({ projectId, jobId, className = 'studio-link', onSaved, variant }: {
  projectId: string; jobId: string; className?: string; onSaved?: () => void
  /** Enum summary of the output variant being downloaded, for delivery analytics. */
  variant?: VariantProperties
}) {
  const { t } = useTranslation()
  const pending = useRef(false)
  const [busy, setBusy] = useState(false)
  return <a className={className} href={studioApi.video(projectId, jobId, true)} download
    aria-busy={busy} aria-disabled={busy}
    onClick={async event => {
      if (!isDesktopDownload()) { studioDownloadRequested(projectId, jobId, variant); onSaved?.(); return }
      event.preventDefault()
      if (pending.current) return
      pending.current = true
      setBusy(true)
      try {
        await observeStudioDownload(() => saveStudioExport(projectId, jobId), projectId, jobId, variant)
        message.success(t('已保存到下载文件夹'))
        onSaved?.()
      } catch (error) {
        captureStudioException(error, 'native_download')
        message.error(t('下载失败，请稍后重试'))
      } finally {
        pending.current = false
        setBusy(false)
      }
    }}>{t('下载成片')}</a>
}

import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { message } from 'antd'
import { studioDownloadRequested } from '../../analytics/studio'
import { studioApi } from './api'
import { isDesktopDownload, saveStudioExport } from './nativeDownload'

export default function StudioDownloadLink({ projectId, jobId, className = 'studio-link' }: {
  projectId: string; jobId: string; className?: string
}) {
  const { t } = useTranslation()
  const pending = useRef(false)
  const [busy, setBusy] = useState(false)
  return <a className={className} href={studioApi.video(projectId, jobId, true)} download
    aria-busy={busy} aria-disabled={busy}
    onClick={async event => {
      if (!isDesktopDownload()) { studioDownloadRequested(); return }
      event.preventDefault()
      if (pending.current) return
      pending.current = true
      setBusy(true)
      studioDownloadRequested()
      try {
        await saveStudioExport(projectId, jobId)
        message.success(t('已保存到下载文件夹'))
      } catch {
        message.error(t('下载失败，请稍后重试'))
      } finally {
        pending.current = false
        setBusy(false)
      }
    }}>{t('下载成片')}</a>
}

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { isDesktopMode } from '../utils/desktopMode'
import { Btn } from '../ui'
import { t } from '../i18n'

const CRASH_BANNER_MESSAGE = '本地后台服务多次意外退出，已暂停自动重启。请点击重启服务恢复使用。'

/** Surface an actionable recovery banner when the Tauri backend exhausts auto-restarts. */
export default function BackendCrashBanner() {
  useTranslation()
  const [crashed, setCrashed] = useState(false)
  const [restarting, setRestarting] = useState(false)

  useEffect(() => {
    let unlistenCrashed: (() => void) | undefined
    let unlistenStarted: (() => void) | undefined
    let cancelled = false
    void (async () => {
      if (!(await isDesktopMode())) return
      const { listen } = await import('@tauri-apps/api/event')
      unlistenCrashed = await listen('backend-crashed', () => {
        if (!cancelled) {
          setRestarting(false)
          setCrashed(true)
        }
      })
      unlistenStarted = await listen('backend-started', () => {
        if (!cancelled) {
          setRestarting(false)
          setCrashed(false)
        }
      })
    })()
    return () => {
      cancelled = true
      unlistenCrashed?.()
      unlistenStarted?.()
    }
  }, [])

  if (!crashed) return null

  const restart = async () => {
    setRestarting(true)
    try {
      const { invoke } = await import('@tauri-apps/api/core')
      await invoke('restart_backend_service')
    } catch (error) {
      console.warn('restart_backend failed', error)
      setRestarting(false)
    }
  }

  return (
    <div className="ac-failure-summary" role="alert" data-testid="backend-crash-banner" style={{ margin: '12px 24px 0' }}>
      <p className="ac-failure-reason">{t(CRASH_BANNER_MESSAGE)}</p>
      <div className="studio-actions">
        <Btn size="sm" variant="cta" loading={restarting} disabled={restarting} onClick={() => void restart()}>
          {t('立即重启')}
        </Btn>
      </div>
    </div>
  )
}

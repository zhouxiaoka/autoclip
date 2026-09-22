import { useTranslation } from 'react-i18next'
import { t } from '../i18n'
import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { Btn, ProgressLine } from '../ui'
import { isDesktopMode } from '../utils/desktopMode'
import {
  type AppUpdate,
  checkForUpdate,
  emptyProgress,
  getAppVersion,
  maybeCheckForUpdate,
} from './updater'
import { applyDownloadEvent, displayError, previewNotes, SNOOZE_KEY } from './updateSchedule'

export type UpdatePhase = 'idle' | 'checking' | 'downloading' | 'ready' | 'failed' | 'restarting'

export type AppUpdateController = {
  phase: UpdatePhase
  desktop: boolean
  preview: boolean
  version: string
  currentVersion: string
  notes: string
  percent: number | null
  error: string
  toastVisible: boolean
  checkNow: () => Promise<'current' | 'available'>
  snooze: () => void
  showToast: () => void
  openUpdate: () => void
  restart: () => Promise<void>
  retry: () => Promise<void>
}

const UpdateContext = createContext<AppUpdateController | null>(null)

type PreviewKind = 'downloading' | 'ready' | 'failed'

function readPreview(): PreviewKind | null {
  if (!import.meta.env.DEV || typeof window === 'undefined') return null
  const query = window.location.hash.split('?')[1] || ''
  const value = new URLSearchParams(query).get('previewUpdate')
  if (value === 'downloading' || value === 'ready' || value === 'failed') return value
  return null
}

function readSnooze(): string {
  try { return sessionStorage.getItem(SNOOZE_KEY) || '' } catch { return '' }
}

function writeSnooze(version: string) {
  try {
    if (version) sessionStorage.setItem(SNOOZE_KEY, version)
  } catch { /* 隐私模式 */ }
}

function clearSnooze() {
  try { sessionStorage.removeItem(SNOOZE_KEY) } catch { /* 隐私模式 */ }
}

export const UpdateProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const previewKind = useMemo(readPreview, [])
  const [phase, setPhase] = useState<UpdatePhase>(
    previewKind === 'downloading' ? 'downloading' : previewKind === 'ready' ? 'ready' : previewKind === 'failed' ? 'failed' : 'idle',
  )
  const [desktop, setDesktop] = useState(Boolean(previewKind))
  const [version, setVersion] = useState(previewKind ? '1.4.0' : '')
  const [currentVersion, setCurrentVersion] = useState(previewKind ? '1.3.1' : '')
  const [notes, setNotes] = useState(previewKind && previewKind !== 'failed' ? '后台下载新版本，准备好后提示重启。' : '')
  const [percent, setPercent] = useState<number | null>(previewKind === 'downloading' ? 42 : previewKind === 'ready' ? 100 : null)
  const [error, setError] = useState(previewKind === 'failed' ? 'offline' : '')
  const [toastVisible, setToastVisible] = useState(previewKind === 'ready' || previewKind === 'failed')
  const live = useRef<AppUpdate | null>(null)
  const generation = useRef(0)

  const beginDownload = useCallback(async (found: AppUpdate) => {
    const token = ++generation.current
    const previous = live.current
    live.current = found
    if (previous && previous !== found) void previous.close().catch(() => undefined)
    setVersion(found.version)
    setNotes(previewNotes(found.body))
    setError('')
    setPercent(null)
    setPhase('downloading')
    setToastVisible(false)
    const snap = emptyProgress()
    let latest = snap
    let lastPaint = 0
    try {
      await found.download((event) => {
        if (token !== generation.current) return
        latest = applyDownloadEvent(latest, event)
        const now = Date.now()
        if (event.event === 'Finished' || now - lastPaint > 150) {
          lastPaint = now
          setPercent(latest.percent)
        }
      })
      if (token !== generation.current) return
      setPercent(100)
      setPhase('ready')
      if (readSnooze() !== found.version) setToastVisible(true)
    } catch (err) {
      if (token !== generation.current) return
      setError(displayError(err))
      setPhase('failed')
      setToastVisible(true)
    }
  }, [])

  const checkNow = useCallback(async (): Promise<'current' | 'available'> => {
    if (previewKind) {
      setToastVisible(true)
      return phase === 'idle' ? 'current' : 'available'
    }
    if (!(await isDesktopMode())) throw new Error('desktop-only')
    setPhase('checking')
    setError('')
    try {
      const found = await checkForUpdate()
      const current = await getAppVersion()
      setCurrentVersion(current)
      setDesktop(true)
      if (!found) {
        setPhase('idle')
        setVersion('')
        setNotes('')
        setToastVisible(false)
        const previous = live.current
        live.current = null
        if (previous) void previous.close().catch(() => undefined)
        return 'current'
      }
      clearSnooze()
      await beginDownload(found)
      return 'available'
    } catch (err) {
      setPhase('idle')
      throw err
    }
  }, [beginDownload, phase, previewKind])

  const restart = useCallback(async () => {
    if (previewKind) {
      setPhase('restarting')
      setToastVisible(true)
      return
    }
    const found = live.current
    if (!found) return
    setPhase('restarting')
    setToastVisible(true)
    try {
      await found.installAndRelaunch()
    } catch (err) {
      setError(displayError(err))
      setPhase('ready')
      setToastVisible(true)
    }
  }, [previewKind])

  const retry = useCallback(async () => {
    clearSnooze()
    await checkNow()
  }, [checkNow])

  const snooze = useCallback(() => {
    writeSnooze(version)
    setToastVisible(false)
  }, [version])

  const showToast = useCallback(() => setToastVisible(true), [])

  const openUpdate = useCallback(() => {
    clearSnooze()
    setToastVisible(true)
    if (phase === 'failed') void checkNow()
  }, [phase, checkNow])

  useEffect(() => {
    if (previewKind) return
    let cancelled = false
    void (async () => {
      const isDesktop = await isDesktopMode()
      if (cancelled) return
      setDesktop(isDesktop)
      const current = await getAppVersion()
      if (cancelled) return
      setCurrentVersion(current)
      if (!isDesktop) return
      const found = await maybeCheckForUpdate()
      if (cancelled || !found) return
      await beginDownload(found)
    })()
    return () => { cancelled = true }
  }, [beginDownload, previewKind])

  const value = useMemo<AppUpdateController>(() => ({
    phase, desktop, preview: Boolean(previewKind), version, currentVersion, notes, percent, error, toastVisible,
    checkNow, snooze, showToast, openUpdate, restart, retry,
  }), [phase, desktop, previewKind, version, currentVersion, notes, percent, error, toastVisible, checkNow, snooze, showToast, openUpdate, restart, retry])

  return <UpdateContext.Provider value={value}>{children}</UpdateContext.Provider>
}

export function useAppUpdate(): AppUpdateController {
  const value = useContext(UpdateContext)
  if (!value) throw new Error('useAppUpdate must be used within UpdateProvider')
  return value
}

export const UpdateToast: React.FC = () => {
  useTranslation()
  const update = useAppUpdate()
  const { toastVisible, phase, snooze } = update
  useEffect(() => {
    if (!toastVisible) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && phase !== 'restarting') snooze()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [toastVisible, phase, snooze])

  if (!update.toastVisible) return null
  const title = update.phase === 'ready' || update.phase === 'restarting'
    ? t('更新已就绪')
    : update.phase === 'failed'
      ? t('更新没有下载完')
      : t('正在准备更新')
  const description = update.phase === 'failed'
    ? update.error
    : update.phase === 'downloading'
      ? t('正在下载 {{version}}', { version: update.version })
      : t('重启以完成 AutoClip {{version}} 的安装。正在做的项目会保留。', { version: update.version })

  return (
    <div className="ac-update-toast" role="status" aria-live="polite" data-phase={update.phase}>
      <h3>{title}</h3>
      <p>{description}</p>
      {update.notes && update.phase !== 'failed' && <p className="ac-update-notes">{update.notes}</p>}
      {update.phase === 'downloading' && (
        <div className="ac-update-progress">
          <ProgressLine percent={update.percent ?? 0} />
          {update.percent != null && <span className="ac-update-percent">{update.percent}%</span>}
        </div>
      )}
      <div className="ac-update-actions">
        {update.phase !== 'restarting' && (
          <Btn size="sm" onClick={update.snooze}>{t('暂不')}</Btn>
        )}
        {update.phase === 'ready' && (
          <Btn size="sm" variant="cta" onClick={() => void update.restart()}>{t('更新并重启')}</Btn>
        )}
        {update.phase === 'failed' && (
          <Btn size="sm" variant="cta" onClick={() => void update.retry()}>{t('重试')}</Btn>
        )}
        {update.phase === 'restarting' && (
          <Btn size="sm" variant="cta" loading>{t('正在重启')}</Btn>
        )}
      </div>
    </div>
  )
}

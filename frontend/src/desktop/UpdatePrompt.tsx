import { useTranslation } from 'react-i18next'
import { t } from '../i18n'
import React, { useEffect, useState } from 'react'
import { Btn, Dialog } from '../ui'
import {
  type AppUpdate,
  checkForUpdate,
  getAppVersion,
  installUpdateAndRelaunch,
  maybeCheckForUpdate,
} from './updater'

export const UpdateDialog: React.FC<{
  update: AppUpdate
  currentVersion?: string
  open: boolean
  onClose: () => void
}> = ({ update, currentVersion, open, onClose }) => {
  useTranslation()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const install = async () => {
    setBusy(true)
    setError('')
    try {
      await installUpdateAndRelaunch(update)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setBusy(false)
    }
  }

  return (
    <Dialog
      open={open}
      onClose={() => { if (!busy) onClose() }}
      title={t('有新版本')}
      description={currentVersion
        ? t('发现 {{version}}，当前是 {{current}}。下载安装后会自动重启。', { version: update.version, current: currentVersion })
        : t('发现 {{version}}。下载安装后会自动重启。', { version: update.version })}
      footer={(
        <>
          <Btn size="sm" onClick={onClose} disabled={busy}>{t('稍后')}</Btn>
          <Btn size="sm" variant="cta" loading={busy} onClick={() => void install()}>{t('下载并安装')}</Btn>
        </>
      )}
    >
      {update.body && (
        <p className="ac-sub" style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{update.body}</p>
      )}
      {error && <p className="ac-sub" style={{ margin: '10px 0 0', color: 'var(--ac-error)' }}>{error}</p>}
    </Dialog>
  )
}

/** 启动时静默检查；有更新再弹出，不自动安装。 */
export const UpdatePrompt: React.FC = () => {
  const [update, setUpdate] = useState<AppUpdate | null>(null)
  const [current, setCurrent] = useState('')

  useEffect(() => {
    void (async () => {
      const [found, version] = await Promise.all([maybeCheckForUpdate(), getAppVersion()])
      setCurrent(version)
      setUpdate(found)
    })()
  }, [])

  if (!update) return null
  return (
    <UpdateDialog
      update={update}
      currentVersion={current}
      open
      onClose={() => setUpdate(null)}
    />
  )
}

export async function runManualUpdateCheck(): Promise<{
  update: AppUpdate | null
  currentVersion: string
}> {
  const [update, currentVersion] = await Promise.all([checkForUpdate(), getAppVersion()])
  return { update, currentVersion }
}

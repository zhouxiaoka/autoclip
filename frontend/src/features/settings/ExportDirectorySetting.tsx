import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { t } from '../../i18n'
import { Btn, Row } from '../../ui'
import { exportDirectory, exportDirectoryIssue, type ExportDirectoryAction, type ExportDirectoryState } from '../../desktop/exportDirectory'

export default function ExportDirectorySetting({ desktop }: { desktop: boolean }) {
  useTranslation()
  const [destination, setDestination] = useState<ExportDirectoryState | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const pending = useRef(false)
  const version = useRef(0)
  const mounted = useRef(false)

  useEffect(() => {
    mounted.current = true
    const generation = ++version.current
    if (desktop) {
      void exportDirectory('get_export_directory').then(value => {
        if (mounted.current && version.current === generation) { setDestination(value); setError('') }
      }).catch(reason => {
        if (mounted.current && version.current === generation) setError(exportDirectoryIssue(reason))
      })
    }
    return () => { mounted.current = false; version.current++ }
  }, [desktop])

  async function act(action: ExportDirectoryAction) {
    if (!desktop || pending.current) return
    pending.current = true
    const generation = ++version.current
    setBusy(true)
    try {
      const value = await exportDirectory(action)
      if (mounted.current && version.current === generation) { setDestination(value); setError('') }
    } catch (reason) {
      if (mounted.current && version.current === generation) setError(exportDirectoryIssue(reason))
    } finally {
      pending.current = false
      if (mounted.current && version.current === generation) setBusy(false)
    }
  }

  return <Row label={t('exportFolder.title')} hint={t(desktop ? 'exportFolder.hint' : 'exportFolder.browser')}>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minWidth: 0, maxWidth: 420 }}>
      {desktop && destination && <span className="ac-note" style={{ overflowWrap: 'anywhere' }} data-testid="export-directory-path">{destination.effectivePath}</span>}
      {error && <p className="ac-note" role="alert">{t(error)}</p>}
      {desktop && <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        <Btn size="sm" disabled={busy} loading={busy} onClick={() => void act('choose_export_directory')}>{t('exportFolder.choose')}</Btn>
        <Btn size="sm" disabled={busy} onClick={() => void act('reset_export_directory')}>{t('exportFolder.reset')}</Btn>
        {error && <Btn size="sm" disabled={busy} onClick={() => void act('get_export_directory')}>{t('exportFolder.retry')}</Btn>}
      </div>}
    </div>
  </Row>
}

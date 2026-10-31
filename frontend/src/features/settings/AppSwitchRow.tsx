import { useCallback, useEffect, useRef, useState } from 'react'
import { Switch, message } from 'antd'
import { t } from '../../i18n'
import { Btn, Row } from '../../ui'

/** One settings row: load a boolean, save it, and offer a retry when the read fails. */
export default function AppSwitchRow({
  label, hint, read, write,
}: {
  label: string
  hint: string
  read: () => Promise<boolean>
  write: (value: boolean) => Promise<boolean>
}) {
  const [enabled, setEnabled] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [failed, setFailed] = useState(false)
  const [saving, setSaving] = useState(false)
  const mounted = useRef(false)
  const readRef = useRef(read)
  const writeRef = useRef(write)
  readRef.current = read
  writeRef.current = write
  const load = useCallback(async () => {
    setFailed(false)
    try {
      const value = await readRef.current()
      if (mounted.current) { setEnabled(value); setLoaded(true) }
    } catch { if (mounted.current) setFailed(true) }
  }, [])
  useEffect(() => { mounted.current = true; void load(); return () => { mounted.current = false } }, [load])
  const save = async (value: boolean) => {
    setSaving(true)
    try {
      const saved = await writeRef.current(value)
      if (mounted.current) setEnabled(saved)
    } catch { if (mounted.current) message.error(t('保存失败，请稍后重试')) }
    finally { if (mounted.current) setSaving(false) }
  }
  return <Row label={label} hint={hint}>
    {failed ? <Btn size="sm" onClick={() => void load()}>{t('重试')}</Btn> :
      loaded && <Switch aria-label={label} checked={enabled} loading={saving} onChange={value => void save(value)} />}
  </Row>
}

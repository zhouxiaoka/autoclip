import { useEffect, useRef, type RefObject } from 'react'
import { useBlocker } from 'react-router-dom'
import { t } from '../../i18n'
import { Btn, Dialog } from '../../ui'

export default function ModelSettingsLeaveGuard({ dirty, saving, onSave }: {
  dirty: RefObject<boolean>
  saving: boolean
  onSave: () => Promise<boolean>
}) {
  const blocker = useBlocker(({ currentLocation, nextLocation }) => dirty.current === true && currentLocation.pathname !== nextLocation.pathname)
  const blockerRef = useRef(blocker)
  blockerRef.current = blocker
  const mountedRef = useRef(true)
  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])
  const busyRef = useRef(false)
  if (blocker.state !== 'blocked') return null
  const safeReset = () => {
    if (!mountedRef.current || blockerRef.current.state !== 'blocked') return
    try { blockerRef.current.reset() } catch { /* Router blocker already unblocked during async save */ }
  }
  const safeProceed = () => {
    if (!mountedRef.current || blockerRef.current.state !== 'blocked') return
    try { blockerRef.current.proceed() } catch { /* Router blocker already unblocked during async save */ }
  }
  const stay = () => { if (!saving && !busyRef.current) safeReset() }
  const saveAndLeave = async () => {
    if (busyRef.current) return
    busyRef.current = true
    try {
      const ok = await onSave()
      if (ok) safeProceed()
      else safeReset()
    } finally {
      busyRef.current = false
    }
  }
  return <Dialog open onClose={stay} title={t('有未保存的更改')} footer={<>
    <Btn disabled={saving} onClick={stay}>{t('继续编辑')}</Btn>
    <Btn disabled={saving} onClick={safeProceed}>{t('放弃更改')}</Btn>
    <Btn variant="cta" loading={saving} onClick={() => void saveAndLeave()}>{t('保存并离开')}</Btn>
  </>} />
}

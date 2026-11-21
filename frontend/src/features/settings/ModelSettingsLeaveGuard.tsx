import type { RefObject } from 'react'
import { useBlocker } from 'react-router-dom'
import { t } from '../../i18n'
import { Btn, Dialog } from '../../ui'

export default function ModelSettingsLeaveGuard({ dirty, saving, onSave }: {
  dirty: RefObject<boolean>
  saving: boolean
  onSave: () => Promise<boolean>
}) {
  const blocker = useBlocker(({ currentLocation, nextLocation }) => dirty.current === true && currentLocation.pathname !== nextLocation.pathname)
  if (blocker.state !== 'blocked') return null
  const stay = () => { if (!saving) blocker.reset() }
  const saveAndLeave = async () => {
    if (await onSave()) blocker.proceed()
    else blocker.reset()
  }
  return <Dialog open onClose={stay} title={t('有未保存的更改')} footer={<>
    <Btn disabled={saving} onClick={stay}>{t('继续编辑')}</Btn>
    <Btn disabled={saving} onClick={() => blocker.proceed()}>{t('放弃更改')}</Btn>
    <Btn variant="cta" loading={saving} onClick={() => void saveAndLeave()}>{t('保存并离开')}</Btn>
  </>} />
}

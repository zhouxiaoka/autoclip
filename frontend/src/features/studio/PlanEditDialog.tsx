import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Btn, Dialog } from '../../ui'
import ImportPreferences from './ImportPreferences'
import { errorText, studioApi } from './api'
import { defaultImportOptions, type ImportPlan, type ImportOptions } from './types'

interface Props {
  projectId: string
  plan?: ImportPlan
  remake?: boolean
  onClose: () => void
  onSubmitted: () => void
}

export default function PlanEditDialog({ projectId, plan, remake, onClose, onSubmitted }: Props) {
  const { t } = useTranslation()
  const [value, setValue] = useState<ImportOptions>(() => {
    const previous = plan?.confirmed_preferences
    const firstGoal = plan?.selected_goals?.[0]
    return {
      ...defaultImportOptions,
      ...(remake && plan?.preferences),
      ...plan?.overrides,
      ...(remake && previous),
      ...(remake && firstGoal && plan?.goal_preferences?.[firstGoal]),
    }
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit() {
    if (busy) return
    setBusy(true)
    setError('')
    try {
      await studioApi.correctPlan(projectId, { ...value, auto_start: false })
      onSubmitted()
    } catch (err) {
      setError(errorText(err))
      setBusy(false)
    }
  }

  return <Dialog open title={remake ? t('再做一版') : t('调整制作方案')}
    description={t('新方案由你确认后开始制作。已有草稿和导出会保留。')}
    onClose={() => { if (!busy) onClose() }}
    footer={<><Btn disabled={busy} onClick={onClose}>{t('取消')}</Btn><Btn variant="cta" loading={busy} onClick={submit}>{t('生成新方案')}</Btn></>}>
    <ImportPreferences value={value} onChange={setValue} />
    <label className="studio-field">{t('补充要求')}
      <input value={value.instruction} maxLength={1000} onChange={e => setValue({ ...value, instruction: e.target.value })} />
    </label>
    {error && <p role="alert" className="studio-error">{t(error)}</p>}
  </Dialog>
}

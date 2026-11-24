import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Btn, Dialog } from '../../ui'
import ImportPreferences from './ImportPreferences'
import PlatformPicker from './PlatformPicker'
import { errorText, studioApi } from './api'
import { defaultImportOptions, languages, type ImportPlan, type ImportOptions } from './types'

interface Props {
  projectId: string
  plan?: ImportPlan
  remake?: boolean
  initialPlatforms?: string[]
  existingPlatforms?: string[]
  onClose: () => void
  onSubmitted: () => void
}

export default function PlanEditDialog({ projectId, plan, remake, initialPlatforms, existingPlatforms, onClose, onSubmitted }: Props) {
  const { t } = useTranslation()
  const [platforms, setPlatforms] = useState<string[]>(() => {
    if (initialPlatforms?.length) return initialPlatforms
    if (existingPlatforms?.length) return existingPlatforms
    if (plan?.overrides?.platforms?.length) return plan.overrides.platforms
    return ['douyin']
  })
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
      if (remake) {
        await studioApi.correctPlan(projectId, {
          ...value,
          goal: 'auto',
          aspect: null,
          platforms,
          auto_start: true,
        })
      } else {
        await studioApi.correctPlan(projectId, { ...value, auto_start: false })
      }
      onSubmitted()
    } catch (err) {
      setError(errorText(err))
      setBusy(false)
    }
  }

  return <Dialog open title={remake ? t('重做') : t('调整制作方案')}
    description={remake ? t('用当前素材生成新版本，已有成片会保留。') : t('新方案由你确认后开始制作。已有草稿和导出会保留。')}
    onClose={() => { if (!busy) onClose() }}
    footer={<><Btn disabled={busy} onClick={onClose}>{t('取消')}</Btn><Btn variant="cta" loading={busy} onClick={submit}>{remake ? t('开始重做') : t('生成新方案')}</Btn></>}>
    {remake ? <>
      <PlatformPicker value={platforms} onChange={setPlatforms} disabled={busy} includeOriginal existing={existingPlatforms}
        legend={t('选择目标平台')} hint={t('可重新生成已有平台，或增选其他平台与原画幅。')} />
      <details className="studio-details">
        <summary>{t('更多选项（可选）')}</summary>
        <label className="studio-field">{t('文字语言')}
          <select aria-label={t('文字语言')} disabled={busy} value={value.language}
            onChange={e => setValue({ ...value, language: e.target.value as ImportOptions['language'] })}>
            {languages.map(l => <option key={l.value} value={l.value}>{l.value === 'source' ? t('沿用素材语言（推荐）') : l.label}</option>)}
          </select>
        </label>
        <label className="studio-field">{t('补充要求')}
          <input value={value.instruction} maxLength={1000} onChange={e => setValue({ ...value, instruction: e.target.value })} />
        </label>
      </details>
    </> : <>
      <ImportPreferences value={value} onChange={setValue} />
      <label className="studio-field">{t('补充要求')}
        <input value={value.instruction} maxLength={1000} onChange={e => setValue({ ...value, instruction: e.target.value })} />
      </label>
    </>}
    {error && <p role="alert" className="studio-error">{t(error)}</p>}
  </Dialog>
}

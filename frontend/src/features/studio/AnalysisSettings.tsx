import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { t } from '../../i18n'
import { Btn, Section } from '../../ui'
import { studioApi, errorText } from './api'
import { AnalysisPreferences } from './types'
import './studio.css'

export default function AnalysisSettings() {
  useTranslation()
  const [value,setValue]=useState<AnalysisPreferences|null>(null)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [saved,setSaved]=useState(false)
  useEffect(()=>{let live=true;studioApi.analysisPreferences().then(v=>{if(live)setValue(v)}).catch(e=>{if(live)setError(errorText(e))});return()=>{live=false}},[])
  const save=async()=>{if(!value)return;setBusy(true);setError('');setSaved(false);try{setValue(await studioApi.saveAnalysisPreferences(value));setSaved(true)}catch(e){setError(errorText(e))}finally{setBusy(false)}}
  return <Section title={t('分析方式')} description={t('配置视觉模型不会自动切换分析方式。')}>
    {value&&<fieldset className="studio-fieldset" disabled={busy}>
      <label className="studio-field">{t('默认分析方式')}<select value={value.analysis_mode} onChange={e=>{setValue({...value,analysis_mode:e.target.value as AnalysisPreferences['analysis_mode'],allow_visual_screening:e.target.value==='subtitle'?false:value.allow_visual_screening});setSaved(false)}}>
        <option value="subtitle">{t('字幕分析 · 低成本')}</option><option value="auto">{t('智能选择')}</option><option value="visual">{t('视觉分析')}</option>
      </select></label>
      {value.analysis_mode==='subtitle'&&<p className="studio-muted">{t('仅分析字幕文本；无字幕时需要转写。')}</p>}
      {value.analysis_mode!=='subtitle'&&<label className="studio-field"><span><input type="checkbox" checked={value.allow_visual_screening} onChange={e=>{setValue({...value,allow_visual_screening:e.target.checked});setSaved(false)}}/>{t('允许付费视觉初筛')}</span><small>{t('发送抽样画面与文本，按模型服务商计费。')}</small><small>{t('关闭时不调用视觉初筛，确认后才开始正式分析。')}</small></label>}
      <Btn variant="cta" loading={busy} onClick={save}>{t('保存')}</Btn>
    </fieldset>}
    {error&&<p role="alert" className="studio-error">{t(error)}</p>}{saved&&<p role="status">{t('分析偏好已保存')}</p>}
  </Section>
}

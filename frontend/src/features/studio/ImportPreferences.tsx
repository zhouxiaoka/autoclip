import { useTranslation } from 'react-i18next'
import { t } from '../../i18n'
import { ImportOptions, goalLabels, languages } from './types'

export default function ImportPreferences({value, onChange, hideGoal=false}: {value: ImportOptions; onChange: (value: ImportOptions) => void; hideGoal?:boolean}) {
  useTranslation()
  const patch = (changes: Partial<ImportOptions>) => onChange({...value, ...changes})
  return <div className="studio-fields">
    {!hideGoal&&<label className="studio-field">{t("制作方式")}<select value={value.goal} onChange={e=>patch({goal:e.target.value as ImportOptions['goal']})}>{Object.entries(goalLabels).map(([key,label])=><option value={key} key={key}>{t(label)}</option>)}</select></label>}
    <label className="studio-field">{t("文字语言")}<select value={value.language} onChange={e=>patch({language:e.target.value as ImportOptions['language']})}>{languages.map(l=><option value={l.value} key={l.value}>{l.value==='source'?t("沿用素材语言（推荐）"):l.label}</option>)}</select></label>
    <label className="studio-field">{t("每条期望时长")}<select value={value.duration ?? ''} onChange={e=>patch({duration:e.target.value?Number(e.target.value):null})}><option value="">{t("AI 根据内容匹配")}</option>{[15,30,60,90,120].map(n=><option value={n} key={n}>{t('约 {{seconds}} 秒', { seconds: n })}</option>)}</select>{value.goal==='content'&&<small>{t("内容切片按完整语义选段，具体起止可在编辑器调整。")}</small>}</label>
    <label className="studio-field">{t("画幅")}<select value={value.aspect ?? ''} onChange={e=>patch({aspect:(e.target.value || null) as ImportOptions['aspect']})}><option value="">{t("AI 根据内容匹配")}</option><option value="original">{t("保持原画幅")}</option><option value="portrait">{t("9:16 竖屏")}</option><option value="landscape">{t("16:9 横屏")}</option></select></label>
  </div>
}

import { useTranslation } from 'react-i18next'
import { Select } from 'antd'
import { t } from '../../i18n'
import { Row } from '../../ui'
import { ImportOptions, goalLabels, languages } from './types'

/** Optional production preferences as setting rows; every field defaults to "let AI match". */
export default function ImportPreferences({value, onChange, hideGoal=false}: {value: ImportOptions; onChange: (value: ImportOptions) => void; hideGoal?:boolean}) {
  useTranslation()
  const patch = (changes: Partial<ImportOptions>) => onChange({...value, ...changes})
  return <div className="ac-rows studio-preferences">
    {!hideGoal&&<Row label={t("制作方式")}>
      <Select aria-label={t("制作方式")} size="small" style={{width:180}} value={value.goal} options={Object.entries(goalLabels).map(([key,label])=>({value:key,label:t(label)}))} onChange={goal=>patch({goal:goal as ImportOptions['goal']})} />
    </Row>}
    <Row label={t("文字语言")}>
      <Select aria-label={t("文字语言")} size="small" style={{width:180}} value={value.language} options={languages.map(l=>({value:l.value,label:l.value==='source'?t("沿用素材语言（推荐）"):l.label}))} onChange={language=>patch({language:language as ImportOptions['language']})} />
    </Row>
    <Row label={t("每条期望时长")} hint={value.goal==='content'?t("内容切片按完整语义选段，具体起止可在编辑器调整。"):undefined}>
      <Select aria-label={t("每条期望时长")} size="small" style={{width:180}} value={value.duration ?? ''} options={[{value:'',label:t("AI 根据内容匹配")},...[15,30,60,90,120].map(n=>({value:n,label:t('约 {{seconds}} 秒', { seconds: n })}))]} onChange={duration=>patch({duration:duration===''?null:Number(duration)})} />
    </Row>
    <Row label={t("画幅")}>
      <Select aria-label={t("画幅")} size="small" style={{width:180}} value={value.aspect ?? ''} options={[{value:'',label:t("AI 根据内容匹配")},{value:'original',label:t("保持原画幅")},{value:'portrait',label:t("9:16 竖屏")},{value:'landscape',label:t("16:9 横屏")}]} onChange={aspect=>patch({aspect:(aspect || null) as ImportOptions['aspect']})} />
    </Row>
  </div>
}

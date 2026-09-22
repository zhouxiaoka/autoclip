import { ImportOptions, goalLabels, languages } from './types'

export default function ImportPreferences({value, onChange, hideGoal=false}: {value: ImportOptions; onChange: (value: ImportOptions) => void; hideGoal?:boolean}) {
  const patch = (changes: Partial<ImportOptions>) => onChange({...value, ...changes})
  return <div className="studio-fields">
    {!hideGoal&&<label className="studio-field">制作方式<select value={value.goal} onChange={e=>patch({goal:e.target.value as ImportOptions['goal']})}>{Object.entries(goalLabels).map(([key,label])=><option value={key} key={key}>{label}</option>)}</select></label>}
    <label className="studio-field">文字语言<select value={value.language} onChange={e=>patch({language:e.target.value as ImportOptions['language']})}>{languages.map(l=><option value={l.value} key={l.value}>{l.value==='source'?'沿用素材语言（推荐）':l.label}</option>)}</select></label>
    <label className="studio-field">每条期望时长<select value={value.duration ?? ''} onChange={e=>patch({duration:e.target.value?Number(e.target.value):null})}><option value="">AI 根据内容匹配</option>{[15,30,60,90,120].map(n=><option value={n} key={n}>约 {n} 秒</option>)}</select>{value.goal==='content'&&<small>内容切片按完整语义选段，具体起止可在编辑器调整。</small>}</label>
    <label className="studio-field">画幅<select value={value.aspect ?? ''} onChange={e=>patch({aspect:(e.target.value || null) as ImportOptions['aspect']})}><option value="">AI 根据内容匹配</option><option value="original">保持原画幅</option><option value="portrait">9:16 竖屏</option><option value="landscape">16:9 横屏</option></select></label>
  </div>
}

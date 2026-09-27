import { useTranslation } from 'react-i18next'
import { t } from '../../i18n'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Btn } from '../../ui'
import { useWorkspace } from './useWorkspace'
import { studioApi, errorText } from './api'
import PlanSummary from './PlanSummary'
import { defaultImportOptions } from './types'
import './studio.css'

export default function ImportReview() {
  useTranslation()
  const { id } = useParams()
  const navigate = useNavigate()
  const { workspace, error, refresh } = useWorkspace(id)
  const [actionError,setActionError]=useState('')
  const [busy,setBusy]=useState(false)
  const retry=async()=>{if(!id)return;setBusy(true);setActionError('');try{await studioApi.correctPlan(id,{...defaultImportOptions,...workspace.plan?.overrides});refresh()}catch(e){setActionError(t(errorText(e)))}finally{setBusy(false)}}
  const running=workspace.analysis?.status==='running'
  const producing=running&&workspace.analysis?.phase==='production'
  if(!id)return null
  return <main className="ac-page studio-import-review">
    <button className="ac-back" onClick={()=>navigate('/')}>{t("返回导入")}</button>
    <h1 className="ac-title">{t("确认制作内容")}</h1>
    <p className="studio-muted">{t("导入视频 → 识别与确认 → 开始制作")}</p>
    {running?<div className="studio-import-box"><h2>{producing?t("制作已经开始"):t("正在快速识别素材")}</h2><p className="studio-muted">{producing?t("可进入项目查看进度。"):t("先判断适合制作的类型，完成后由你确认；此时不会开始正式剪辑。")}</p>{producing&&<Btn variant="cta" onClick={()=>navigate(`/project/${id}`)}>{t("查看制作进度")}</Btn>}</div>:<PlanSummary projectId={id} plan={workspace.plan} status={workspace.analysis?.status} onChanged={refresh} onStarted={()=>navigate(`/project/${id}`)}/>}
    {(error||actionError||workspace.analysis?.status==='failed')&&<p role="alert" className="studio-error">{t(actionError||error||workspace.analysis?.error||'')}</p>}
    {!running&&<div className="studio-actions"><Btn size="sm" loading={busy} onClick={retry}>{t("重新识别")}</Btn><Btn size="sm" onClick={()=>navigate('/settings')}>{t("模型设置")}</Btn></div>}
    {workspace.plan&&<details className="studio-details"><summary>{t("查看导入的素材")}</summary><video controls preload="metadata" className="studio-source-video" src={studioApi.source(id)}/></details>}
  </main>
}

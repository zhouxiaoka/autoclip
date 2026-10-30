import { t } from '../i18n'
import { useTranslation } from 'react-i18next'
import React, { useState, useEffect } from 'react'
import { 
  Layout, 
  Typography, 
  Select, 
  Spin, 
  message 
} from 'antd'
import { useNavigate } from 'react-router-dom'
import ProjectCard from '../components/ProjectCard'
import CreativeImport from '../features/studio/CreativeImport'
import FirstRunSetup from '../features/settings/FirstRunSetup'


import { projectApi } from '../services/api'
import { openExample as startExampleProject } from '../features/studio/openExample'
import { modelSettingsApi, type ModelSettings } from '../features/settings/modelSettingsApi'
import { forSave } from '../features/settings/modelSettingsLogic'
import { syncFollowingCover } from '../features/settings/modelDefaults'
import { recommendTimelineReplacement } from '../features/settings/timelineReplacement'
import { analysisProviderId, listSwitchModelOptions, usableConnectionCount } from '../features/studio/switchModelOptions'
import { studioApi } from '../features/studio/api'
import { Btn } from '../ui'
import { useSimpleProgressStore } from '../stores/useSimpleProgressStore'
import { Project, useProjectStore } from '../store/useProjectStore'
import { useProjectPolling } from '../hooks/useProjectPolling'

const { Content } = Layout
const { Title, Text } = Typography
const { Option } = Select

export default function HomePage() {
  useTranslation()
  const navigate = useNavigate()
  const { projects, setProjects, deleteProject, loading, setLoading } = useProjectStore()
  const [statusFilter, setStatusFilter] = useState<string>('all')
  // null until the model document has loaded; true blocks import until the first AI service is saved.
  const [setupNeeded, setSetupNeeded] = useState<boolean | null>(null)
  const [setupRequest, setSetupRequest] = useState(0)
  const [exampleBusy, setExampleBusy] = useState(false)
  const [aiSettings, setAiSettings] = useState<ModelSettings | null>(null)

  // 使用项目轮询Hook
  useProjectPolling({
    onProjectsUpdate: (updatedProjects) => {
      setProjects(updatedProjects || [])
    },
    enabled: true,
    interval: 30000 // 30秒轮询一次，减少频繁请求
  })

  // 全局保险：当没有运行中的项目时，强制停止进度轮询并清空缓存
  useEffect(() => {
    const hasActive = projects.some(p => p.status === 'processing' || p.status === 'pending')
    if (!hasActive) {
      try {
        const { stopPolling, clearAllProgress } = useSimpleProgressStore.getState()
        stopPolling()
        clearAllProgress()
        console.log('无运行项目，已全局停止进度轮询并清空进度缓存')
      } catch (e) {
        console.warn('停止全局进度轮询时出现问题:', e)
      }
    }
  }, [projects])

  useEffect(() => {
    // 延迟加载项目，避免启动时立即发起大量请求
    const timer = setTimeout(() => {
      loadProjects()
    }, 1000) // 延迟1秒加载
    
    return () => clearTimeout(timer)
  }, [])

  const loadProjects = async () => {
    setLoading(true)
    try {
      // 从后端API获取真实项目数据
      const projects = await projectApi.getProjects()
      // 确保projects是数组类型
      const safeProjects = Array.isArray(projects) ? projects : []
      setProjects(safeProjects)
    } catch (error) {
      message.error(t("加载项目失败"))
      console.error('Load projects error:', error)
      // 如果API调用失败，设置空数组
      setProjects([])
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteProject = async (id: string) => {
    try {
      await projectApi.deleteProject(id)
      deleteProject(id)
      message.success(t("项目删除成功"))
    } catch (error) {
      message.error(t("删除项目失败"))
      console.error('Delete project error:', error)
    }
  }

  // 由 ProjectCard 在「用户手动点重试」且重试请求已成功后调用。
  // ProjectCard.handleRetry 已经发过 start/retryProcessing 请求，这里只负责
  // 提示 + 刷新列表，绝不能再发一次重试请求（会和卡片自身的请求叠加，并制造
  // loadProjects→重挂载→自动启动 的循环）。
  useEffect(() => {
    let live = true
    modelSettingsApi.get().then(value => { if (live) setAiSettings(value) }).catch(() => { if (live) setAiSettings(null) })
    return () => { live = false }
  }, [])

  const replacement = recommendTimelineReplacement(aiSettings)

  const switchOptions = listSwitchModelOptions(aiSettings, {
    connectionId: aiSettings?.analysis?.connection_id,
    model: aiSettings?.analysis?.model,
  })

  /** X2: accept the dialog's connectionId/model; fall back to timeline replacement only when omitted. */
  const handleSwitchModelAndRetry = async (
    projectId: string,
    choice?: { connectionId: string; model: string },
  ) => {
    const nextModel = choice || recommendTimelineReplacement(aiSettings)
    const project = projects.find(item => item.id === projectId)
    if (!aiSettings || !nextModel || !project) {
      message.error(t("重试失败，请稍后再试"))
      return
    }
    const managed = !!(project.settings?.smart_import || project.processing_config?.smart_import)
      || ['highlight', 'promo'].includes(project.settings?.creative?.goal || project.processing_config?.creative?.goal)
    try {
      const saved = await modelSettingsApi.save(forSave(syncFollowingCover(aiSettings, {
        ...aiSettings,
        analysis: {
          connection_id: nextModel.connectionId,
          model: nextModel.model,
          capability: aiSettings.analysis?.capability || 'auto',
          model_source: 'user',
        },
      })))
      setAiSettings(saved)
      if (managed) await studioApi.retry(projectId, { retry_kind: 'switch_model' })
      else await projectApi.retryProcessing(projectId)
      message.success(t("已开始重试处理项目"))
      await loadProjects()
    } catch (error) {
      message.error(t("重试失败，请稍后再试"))
      console.error('Switch model and retry error:', error)
    }
  }

  const handleRetryProject = async () => {
    message.success(t("已开始重试处理项目"))
    try {
      await loadProjects()
    } catch (error) {
      console.error('Refresh after retry error:', error)
    }
  }

  const openExample = async () => {
    setExampleBusy(true)
    try {
      await startExampleProject(navigate)
      void loadProjects().catch(() => undefined)
    } catch (error) {
      message.error(t("示例项目暂时不可用"))
      console.error('Example project error:', error)
    } finally {
      setExampleBusy(false)
    }
  }

  const handleProjectCardClick = (project: Project) => {
    // 导入中状态的项目不能点击进入详情页
    if (project.status === 'pending' && !project.settings?.smart_import && !project.processing_config?.smart_import) {
      message.warning(t("项目正在导入中，请稍后再查看详情"))
      return
    }
    
    // 其他状态可以正常进入详情页
    navigate(`/project/${project.id}`)
  }

  const pendingImports = projects.filter(p => p.settings?.import_staging || p.processing_config?.import_staging)
  const filteredProjects = (projects || [])
    .filter(p => !p.settings?.import_staging && !p.processing_config?.import_staging)
    .filter(project => {
      const matchesStatus = !statusFilter || statusFilter === 'all' || project.status === statusFilter || (statusFilter === 'error' && project.status === 'failed')
      return matchesStatus
    })
    .sort((a, b) => {
      // 按创建时间倒序排列，最新的在前面
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    })

  return (
    <Layout style={{
      minHeight: '100vh',
      background: 'var(--ac-bg)'
    }}>
      <Content style={{ padding: '40px 56px 56px', position: 'relative' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', position: 'relative' }}>
          <FirstRunSetup onStatus={setSetupNeeded} openRequest={setupRequest} />
          <CreativeImport onImported={loadProjects} blocked={setupNeeded === true} onBlocked={() => setSetupRequest(n => n + 1)} onExample={() => void openExample()} exampleBusy={exampleBusy} />
          {pendingImports.length>0&&<div className="studio-import-resume"><b>{t('未完成的导入')}</b>{pendingImports.map(p=><button key={p.id} className="studio-link" onClick={()=>navigate(`/import/${p.id}`)}>{p.name} · {t('继续导入确认')}</button>)}</div>}

          {/* 项目管理区域 */}
          <div style={{
            background: 'transparent',
            padding: '0',
            marginBottom: '32px'
          }}>
            {/* 项目列表标题区域 */}
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'baseline',
              marginTop: '56px',
              marginBottom: '22px'
            }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px' }}>
                <Title
                  level={2}
                  style={{ margin: 0, color: 'var(--ac-ink)', fontSize: '16px', fontWeight: 600 }}
                >{t("我的项目")}</Title>
                <Text style={{ color: 'var(--ac-muted)', fontSize: '13px' }}>
                  {filteredProjects.length}
                </Text>
              </div>
              
              {/* 状态筛选移到右侧 */}
              <div style={{ 
                display: 'flex', 
                alignItems: 'center'
              }}>
                <Select
                  placeholder={t("全部状态")}
                  value={statusFilter}
                  onChange={setStatusFilter}
                  variant="borderless"
                  style={{ minWidth: '120px', fontSize: '13px' }}
                  suffixIcon={<span style={{ color: 'var(--ac-muted)', fontSize: '10px' }}>⌄</span>}
                  allowClear
                >
                  <Option value="all">{t("全部状态")}</Option>
                  <Option value="completed">{t("已完成")}</Option>
                  <Option value="processing">{t("处理中")}</Option>
                  <Option value="error">{t("处理失败")}</Option>
                </Select>
              </div>
            </div>

            {/* 项目列表内容 */}
             <div>
               {loading ? (
                 <div style={{
                   textAlign: 'center',
                   padding: '72px 0',
                   background: 'var(--ac-card)',
                   borderRadius: '16px',
                   border: '1px solid var(--ac-line)'
                 }}>
                   <Spin size="large" />
                   <div style={{ marginTop: '18px', color: 'var(--ac-muted)', fontSize: '14px' }}>{t("正在加载项目列表…")}</div>
                 </div>
               ) : filteredProjects.length === 0 ? (
                 projects.length === 0 ? (
                   /* 空态按 DESIGN.md：一句话 + 一件可做的事。示例项目不需要 Key，先看效果再导入自己的视频。 */
                   <div className="ac-empty">
                     <b>{t("还没有项目")}</b>
                     <span>{t("从上方导入一段视频，或者先用示例项目看看出片效果。")}</span>
                     <div style={{ marginTop: 18 }}>
                       <Btn size="sm" loading={exampleBusy} onClick={() => void openExample()}>{t("用示例项目看看效果")}</Btn>
                     </div>
                   </div>
                 ) : (
                   <div className="ac-empty"><b>{t("没有找到匹配的项目")}</b></div>
                 )
               ) : (
                 <div style={{
                   display: 'grid',
                   gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
                   gap: '24px',
                   justifyContent: 'start'
                 }}>
                   {filteredProjects.map((project: Project) => (
                     <div key={project.id} style={{ position: 'relative', zIndex: 1 }}>
                       <ProjectCard 
                         project={project} 
                         onDelete={handleDeleteProject}
                         onRetry={() => handleRetryProject()}
                         onClick={() => handleProjectCardClick(project)}
                         replacement={replacement}
                         switchOptions={switchOptions}
                         connectionCount={usableConnectionCount(aiSettings)}
                         analysisProvider={analysisProviderId(aiSettings)}
                         onSwitchAndRetry={handleSwitchModelAndRetry}
                       />
                     </div>
                   ))}
                 </div>
               )}
             </div>
           </div>
         </div>
      </Content>
    </Layout>
  )
}



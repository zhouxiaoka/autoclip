import React, { useState, useEffect } from 'react'
import { 
  Layout, 
  Typography, 
  Select, 
  Spin, 
  Empty,
  message 
} from 'antd'
import { useNavigate } from 'react-router-dom'
import ProjectCard from '../components/ProjectCard'
import FileUpload from '../components/FileUpload'
import BilibiliDownload from '../components/BilibiliDownload'

import { projectApi } from '../services/api'
import { useSimpleProgressStore } from '../stores/useSimpleProgressStore'
import { Project, useProjectStore } from '../store/useProjectStore'
import { useProjectPolling } from '../hooks/useProjectPolling'

const { Content } = Layout
const { Title, Text } = Typography
const { Option } = Select

const HomePage: React.FC = () => {
  const navigate = useNavigate()
  const { projects, setProjects, deleteProject, loading, setLoading } = useProjectStore()
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [activeTab, setActiveTab] = useState<'upload' | 'bilibili'>('bilibili')

  // 使用项目轮询Hook
  useProjectPolling({
    onProjectsUpdate: (updatedProjects) => {
      setProjects(updatedProjects || [])
    },
    enabled: true,
    interval: 5000
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
      message.error('Failed to load projects')
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
      message.success('Project deleted')
    } catch (error) {
      message.error('Failed to delete project')
      console.error('Delete project error:', error)
    }
  }

  // 由 ProjectCard 在「用户手动点重试」且重试请求已成功后调用。
  // ProjectCard.handleRetry 已经发过 start/retryProcessing 请求，这里只负责
  // 提示 + 刷新列表，绝不能再发一次重试请求（会和卡片自身的请求叠加，并制造
  // loadProjects→重挂载→自动启动 的循环）。
  const handleRetryProject = async () => {
    message.success('Retrying project')
    try {
      await loadProjects()
    } catch (error) {
      console.error('Refresh after retry error:', error)
    }
  }

  const handleProjectCardClick = (project: Project) => {
    // 导入中状态的项目不能点击进入详情页
    if (project.status === 'pending') {
      message.warning('This project is still importing. Try again in a moment.')
      return
    }
    
    // 其他状态可以正常进入详情页
    navigate(`/project/${project.id}`)
  }

  const filteredProjects = (projects || [])
    .filter(project => {
      const matchesStatus = statusFilter === 'all' || project.status === statusFilter
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
          {/* 文件上传区域 */}
          <div style={{ 
            marginBottom: '48px',
            marginTop: '20px',
            display: 'flex',
            justifyContent: 'center'
          }}>
            <div style={{ width: '100%', maxWidth: '820px' }}>
              <div style={{ fontSize: '13px', color: 'var(--ac-muted)', margin: '0 4px 14px', letterSpacing: '0.2px' }}>
                Paste a link — AI clips it for you
              </div>
              <div style={{
                background: 'var(--ac-card)',
                borderRadius: '16px',
                border: '1px solid var(--ac-line)',
                padding: '18px',
                boxShadow: 'var(--ac-shadow)'
              }}>
              {/* 标签页切换 — 胶囊分段 */}
              <div style={{
                display: 'inline-flex',
                marginBottom: '14px',
                borderRadius: '999px',
                background: 'var(--ac-line-2)',
                padding: '3px',
                gap: '2px'
              }}>
                 <button
                   style={{
                     padding: '8px 18px',
                     borderRadius: '999px',
                     background: activeTab === 'bilibili' ? 'var(--ac-card)' : 'transparent',
                     color: activeTab === 'bilibili' ? 'var(--ac-ink)' : 'var(--ac-sub)',
                     cursor: 'pointer',
                     fontSize: '14px',
                     fontWeight: 500,
                     transition: 'all 0.2s ease',
                     border: 'none',
                     boxShadow: activeTab === 'bilibili' ? '0 1px 2px rgba(0,0,0,.08)' : 'none'
                   }}
                   onClick={() => setActiveTab('bilibili')}
                 >
                   Import from link
                 </button>
                <button
                   style={{
                     padding: '8px 18px',
                     borderRadius: '999px',
                     background: activeTab === 'upload' ? 'var(--ac-card)' : 'transparent',
                     color: activeTab === 'upload' ? 'var(--ac-ink)' : 'var(--ac-sub)',
                     cursor: 'pointer',
                     fontSize: '14px',
                     fontWeight: 500,
                     transition: 'all 0.2s ease',
                     border: 'none',
                     boxShadow: activeTab === 'upload' ? '0 1px 2px rgba(0,0,0,.08)' : 'none'
                   }}
                   onClick={() => setActiveTab('upload')}
                 >
                   Import file
                 </button>
              </div>
              
              {/* 内容区域 */}
              <div>
                {activeTab === 'bilibili' && (
                  <BilibiliDownload onDownloadSuccess={async () => {
                    // 处理完成后刷新项目列表
                    await loadProjects()
                    // 不再显示重复的toast提示，BilibiliDownload组件已经显示了统一的提示
                  }} />
                )}
                {activeTab === 'upload' && (
                  <FileUpload onUploadSuccess={async () => {
                    // 处理完成后刷新项目列表
                    await loadProjects()
                    message.success('Project created. Processing…')
                  }} />
                )}
              </div>
              </div>
            </div>
          </div>

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
                >
                  My projects
                </Title>
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
                  placeholder="All statuses"
                  value={statusFilter}
                  onChange={setStatusFilter}
                  variant="borderless"
                  style={{ minWidth: '120px', fontSize: '13px' }}
                  suffixIcon={<span style={{ color: 'var(--ac-muted)', fontSize: '10px' }}>⌄</span>}
                  allowClear
                >
                  <Option value="all">All statuses</Option>
                  <Option value="completed">Completed</Option>
                  <Option value="processing">Processing</Option>
                  <Option value="error">Failed</Option>
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
                   <div style={{ marginTop: '18px', color: 'var(--ac-muted)', fontSize: '14px' }}>
                     Loading projects…
                   </div>
                 </div>
               ) : filteredProjects.length === 0 ? (
                 <div style={{
                   textAlign: 'center',
                   padding: '72px 0',
                   background: 'var(--ac-card)',
                   borderRadius: '16px',
                   border: '1px solid var(--ac-line)'
                 }}>
                   <Empty
                     image={Empty.PRESENTED_IMAGE_SIMPLE}
                     description={
                       <div>
                         <Text type="secondary">
                           {projects.length === 0 ? 'No projects yet. Import a video above to get started.' : 'No matching projects'}
                         </Text>
                       </div>
                     }
                   />
                 </div>
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

export default HomePage
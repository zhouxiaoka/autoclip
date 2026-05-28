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
      message.error('加载项目失败')
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
      message.success('项目删除成功')
    } catch (error) {
      message.error('删除项目失败')
      console.error('Delete project error:', error)
    }
  }

  const handleRetryProject = async (projectId: string) => {
    try {
      // 查找项目状态
      const project = projects.find(p => p.id === projectId)
      if (!project) {
        message.error('项目不存在')
        return
      }
      
      // 统一使用retryProcessing API，它会自动处理视频文件不存在的情况
      await projectApi.retryProcessing(projectId)
      message.success('已开始重试处理项目')
      
      await loadProjects()
    } catch (error) {
      message.error('重试失败，请稍后再试')
      console.error('Retry project error:', error)
    }
  }

  const handleProjectCardClick = (project: Project) => {
    // 导入中状态的项目不能点击进入详情页
    if (project.status === 'pending') {
      message.warning('项目正在导入中，请稍后再查看详情')
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
      background: '#0f0f0f'
    }}>
      <Content style={{ padding: '40px 24px', position: 'relative' }}>
        <div style={{ maxWidth: '1600px', margin: '0 auto', position: 'relative' }}>
          {/* 文件上传区域 */}
          <div style={{ 
            marginBottom: '48px',
            marginTop: '20px',
            display: 'flex',
            justifyContent: 'center'
          }}>
            <div style={{
              width: '100%',
              maxWidth: '800px',
              background: 'rgba(26, 26, 26, 0.8)',
              backdropFilter: 'blur(20px)',
              borderRadius: '16px',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              padding: '20px',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(255, 255, 255, 0.05)'
            }}>
              {/* 标签页切换 */}
              <div style={{
                display: 'flex',
                marginBottom: '16px',
                borderRadius: '8px',
                background: 'rgba(0, 0, 0, 0.3)',
                padding: '3px'
              }}>
                 <button 
                   style={{
                     flex: 1,
                     padding: '12px 24px',
                     borderRadius: '8px',
                     background: activeTab === 'bilibili' ? 'rgba(255, 255, 255, 0.1)' : 'transparent',
                     color: activeTab === 'bilibili' ? '#ffffff' : '#cccccc',
                     cursor: 'pointer',
                     fontSize: '16px',
                     fontWeight: 600,
                     transition: 'all 0.3s ease',
                     border: activeTab === 'bilibili' ? '1px solid rgba(255, 255, 255, 0.2)' : '1px solid transparent'
                   }}
                   onClick={() => setActiveTab('bilibili')}
                 >
                   📺 链接导入
                 </button>
                <button 
                   style={{
                     flex: 1,
                     padding: '12px 24px',
                     borderRadius: '8px',
                     background: activeTab === 'upload' ? 'rgba(255, 255, 255, 0.1)' : 'transparent',
                     color: activeTab === 'upload' ? '#ffffff' : '#cccccc',
                     cursor: 'pointer',
                     fontSize: '16px',
                     fontWeight: 600,
                     transition: 'all 0.3s ease',
                     border: activeTab === 'upload' ? '1px solid rgba(255, 255, 255, 0.2)' : '1px solid transparent'
                   }}
                   onClick={() => setActiveTab('upload')}
                 >
                   📁 文件导入
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
                    message.success('项目创建成功，正在处理中...')
                  }} />
                )}
              </div>
            </div>
          </div>

          {/* 项目管理区域 */}
          <div style={{
            background: 'rgba(26, 26, 26, 0.7)',
            backdropFilter: 'blur(20px)',
            borderRadius: '24px',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            padding: '32px',
            marginBottom: '32px',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.2), 0 0 0 1px rgba(255, 255, 255, 0.03)'
          }}>
            {/* 项目列表标题区域 */}
            <div style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center',
              marginBottom: '24px',
              paddingBottom: '16px',
              borderBottom: '1px solid rgba(255, 255, 255, 0.1)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <Title 
                  level={2} 
                  style={{ 
                    margin: 0,
                    color: '#ffffff',
                    fontSize: '24px',
                    fontWeight: 600,
                    background: 'linear-gradient(135deg, #ffffff 0%, #cccccc 100%)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    backgroundClip: 'text'
                  }}
                >
                  我的项目
                </Title>
                <div style={{
                  padding: '8px 16px',
                  background: 'rgba(255, 255, 255, 0.1)',
                  borderRadius: '20px',
                  border: '1px solid rgba(255, 255, 255, 0.2)',
                  backdropFilter: 'blur(10px)'
                }}>
                  <Text style={{ color: '#ffffff', fontWeight: 600, fontSize: '14px' }}>
                    共 {filteredProjects.length} 个项目
                  </Text>
                </div>
              </div>
              
              {/* 状态筛选移到右侧 */}
              <div style={{ 
                display: 'flex', 
                alignItems: 'center'
              }}>
                <Select
                  placeholder="选择状态"
                  value={statusFilter}
                  onChange={setStatusFilter}
                  style={{ 
                    minWidth: '140px',
                    height: '36px',
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255, 255, 255, 0.2)',
                    borderRadius: '8px',
                    color: '#ffffff',
                    fontSize: '14px'
                  }}
                  styles={{
                    popup: {
                      root: {
                        background: 'rgba(26, 26, 26, 0.95)',
                        border: '1px solid rgba(255, 255, 255, 0.2)',
                        borderRadius: '8px',
                        backdropFilter: 'blur(20px)',
                        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)'
                      }
                    }
                  }}
                  suffixIcon={
                    <span style={{ 
                      color: '#8c8c8c', 
                      fontSize: '10px',
                      transition: 'all 0.2s ease'
                    }}>
                      ⌄
                    </span>
                  }
                  allowClear
                >
                  <Option value="all" style={{ color: '#ffffff' }}>全部状态</Option>
                  <Option value="completed" style={{ color: '#52c41a' }}>已完成</Option>
                  <Option value="processing" style={{ color: '#1890ff' }}>处理中</Option>
                  <Option value="error" style={{ color: '#ff4d4f' }}>处理失败</Option>
                </Select>
              </div>
            </div>

            {/* 项目列表内容 */}
             <div>
               {loading ? (
                 <div style={{ 
                   textAlign: 'center', 
                   padding: '60px 0',
                   background: '#262626',
                   borderRadius: '12px',
                   border: '1px solid #404040'
                 }}>
                   <Spin size="large" />
                   <div style={{ 
                     marginTop: '20px', 
                     color: '#cccccc',
                     fontSize: '16px'
                   }}>
                     正在加载项目列表...
                   </div>
                 </div>
               ) : filteredProjects.length === 0 ? (
                 <div style={{
                   textAlign: 'center',
                   padding: '60px 0',
                   background: '#262626',
                   borderRadius: '12px',
                   border: '1px solid #404040'
                 }}>
                   <Empty
                     image={Empty.PRESENTED_IMAGE_SIMPLE}
                     description={
                       <div>
                         <Text type="secondary">
                           {projects.length === 0 ? '还没有项目，请使用上方的导入区域创建第一个项目' : '没有找到匹配的项目'}
                         </Text>
                       </div>
                     }
                   />
                 </div>
               ) : (
                 <div style={{
                   display: 'grid',
                   gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                   gap: '16px',
                   justifyContent: 'start',
                   padding: '6px 0'
                 }}>
                   {filteredProjects.map((project: Project) => (
                     <div key={project.id} style={{ position: 'relative', zIndex: 1 }}>
                       <ProjectCard 
                         project={project} 
                         onDelete={handleDeleteProject}
                         onRetry={() => handleRetryProject(project.id)}
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
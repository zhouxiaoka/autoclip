import React, { useState, useEffect } from 'react'
import { Card, Tag, Button, Space, Typography, Progress, Popconfirm, message, Tooltip } from 'antd'
import { PlayCircleOutlined, DeleteOutlined, EyeOutlined, DownloadOutlined, ReloadOutlined, LoadingOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { Project } from '../store/useProjectStore'
import { projectApi } from '../services/api'
import { UnifiedStatusBar } from './UnifiedStatusBar'
// import { 
//   getProjectStatusConfig, 
//   calculateProjectProgress, 
//   normalizeProjectStatus,
//   getProgressStatus 
// } from '../utils/statusUtils'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import timezone from 'dayjs/plugin/timezone'
import utc from 'dayjs/plugin/utc'
import 'dayjs/locale/zh-cn'

dayjs.extend(relativeTime)
dayjs.extend(timezone)
dayjs.extend(utc)
dayjs.locale('zh-cn')

// 添加CSS动画样式
const pulseAnimation = `
  @keyframes pulse {
    0% {
      opacity: 1;
      transform: scale(1);
    }
    50% {
      opacity: 0.5;
      transform: scale(1.1);
    }
    100% {
      opacity: 1;
      transform: scale(1);
    }
  }
`

// 将样式注入到页面
if (typeof document !== 'undefined') {
  const style = document.createElement('style')
  style.textContent = pulseAnimation
  document.head.appendChild(style)
}

const { Text, Title } = Typography
const { Meta } = Card

interface ProjectCardProps {
  project: Project
  onDelete: (id: string) => void
  onRetry?: (id: string) => void
  onClick?: () => void
}

interface LogEntry {
  timestamp: string
  module: string
  level: string
  message: string
}

const ProjectCard: React.FC<ProjectCardProps> = ({ project, onDelete, onRetry, onClick }) => {
  const navigate = useNavigate()
  const [videoThumbnail, setVideoThumbnail] = useState<string | null>(null)
  const [thumbnailLoading, setThumbnailLoading] = useState(false)
  const [isRetrying, setIsRetrying] = useState(false)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [currentLogIndex, setCurrentLogIndex] = useState(0)

  // 获取分类信息
  const getCategoryInfo = (category?: string) => {
    const categoryMap: Record<string, { name: string; icon: string; color: string }> = {
      'default': { name: '默认', icon: '🎬', color: '#4facfe' },
      'knowledge': { name: '知识科普', icon: '📚', color: '#52c41a' },
      'business': { name: '商业财经', icon: '💼', color: '#faad14' },
      'opinion': { name: '观点评论', icon: '💭', color: '#722ed1' },
      'experience': { name: '经验分享', icon: '🌟', color: '#13c2c2' },
      'speech': { name: '演讲脱口秀', icon: '🎤', color: '#eb2f96' },
      'content_review': { name: '内容解说', icon: '🎭', color: '#f5222d' },
      'entertainment': { name: '娱乐内容', icon: '🎪', color: '#fa8c16' }
    }
    return categoryMap[category || 'default'] || categoryMap['default']
  }

  // 缩略图缓存管理
  const thumbnailCacheKey = `thumbnail_${project.id}`
  
  // 生成项目视频缩略图（带缓存）
  useEffect(() => {
    const generateThumbnail = async () => {
      // 优先使用后端提供的缩略图
      if (project.thumbnail) {
        setVideoThumbnail(project.thumbnail)
        console.log(`使用后端提供的缩略图: ${project.id}`)
        return
      }
      
      if (!project.video_path) {
        console.log('项目没有视频路径:', project.id)
        return
      }
      
      // 检查缓存
      const cachedThumbnail = localStorage.getItem(thumbnailCacheKey)
      if (cachedThumbnail) {
        setVideoThumbnail(cachedThumbnail)
        return
      }
      
      setThumbnailLoading(true)
      
      try {
        const video = document.createElement('video')
        video.crossOrigin = 'anonymous'
        video.muted = true
        video.preload = 'metadata'
        
        // 尝试多个可能的视频文件路径
        const possiblePaths = [
          'input/input.mp4',
          'input.mp4',
          project.video_path,
          `${project.video_path}/input.mp4`
        ].filter(Boolean)
        
        let videoLoaded = false
        
        for (const path of possiblePaths) {
          if (videoLoaded) break
          
          try {
            const videoUrl = projectApi.getProjectFileUrl(project.id, path)
            console.log('尝试加载视频:', videoUrl)
            
            await new Promise((resolve, reject) => {
              const timeoutId = setTimeout(() => {
                reject(new Error('视频加载超时'))
              }, 10000) // 10秒超时
              
              video.onloadedmetadata = () => {
                clearTimeout(timeoutId)
                console.log('视频元数据加载成功:', videoUrl)
                video.currentTime = Math.min(5, video.duration / 4) // 取视频1/4处或5秒处的帧
              }
              
              video.onseeked = () => {
                clearTimeout(timeoutId)
                try {
                  const canvas = document.createElement('canvas')
                  const ctx = canvas.getContext('2d')
                  if (!ctx) {
                    reject(new Error('无法获取canvas上下文'))
                    return
                  }
                  
                  // 设置合适的缩略图尺寸
                  const maxWidth = 320
                  const maxHeight = 180
                  const aspectRatio = video.videoWidth / video.videoHeight
                  
                  let width = maxWidth
                  let height = maxHeight
                  
                  if (aspectRatio > maxWidth / maxHeight) {
                    height = maxWidth / aspectRatio
                  } else {
                    width = maxHeight * aspectRatio
                  }
                  
                  canvas.width = width
                  canvas.height = height
                  ctx.drawImage(video, 0, 0, width, height)
                  
                  const thumbnail = canvas.toDataURL('image/jpeg', 0.7)
                  setVideoThumbnail(thumbnail)
                  
                  // 缓存缩略图
                  try {
                    localStorage.setItem(thumbnailCacheKey, thumbnail)
                  } catch (e) {
                    // 如果localStorage空间不足，清理旧缓存
                    const keys = Object.keys(localStorage).filter(key => key.startsWith('thumbnail_'))
                    if (keys.length > 50) { // 保留最多50个缩略图缓存
                      keys.slice(0, 10).forEach(key => localStorage.removeItem(key))
                      localStorage.setItem(thumbnailCacheKey, thumbnail)
                    }
                  }
                  
                  videoLoaded = true
                  resolve(thumbnail)
                } catch (error) {
                  reject(error)
                }
              }
              
              video.onerror = (error) => {
                clearTimeout(timeoutId)
                console.error('视频加载失败:', videoUrl, error)
                reject(error)
              }
              
              video.src = videoUrl
            })
            
            break // 如果成功加载，跳出循环
          } catch (error) {
            console.warn(`路径 ${path} 加载失败:`, error)
            continue // 尝试下一个路径
          }
        }
        
        if (!videoLoaded) {
          console.error('所有视频路径都加载失败')
        }
      } catch (error) {
        console.error('生成缩略图时发生错误:', error)
      } finally {
        setThumbnailLoading(false)
      }
    }
    
    generateThumbnail()
  }, [project.id, project.video_path, thumbnailCacheKey])

  // 获取项目日志（仅在处理中时）
  useEffect(() => {
    if (project.status !== 'processing') {
      setLogs([])
      return
    }

    const fetchLogs = async () => {
      try {
        const response = await projectApi.getProjectLogs(project.id, 20)
        setLogs(response.logs.filter(log => 
          log.message.includes('Step') || 
          log.message.includes('开始') || 
          log.message.includes('完成') ||
          log.message.includes('处理') ||
          log.level === 'ERROR'
        ))
      } catch (error) {
        console.error('获取日志失败:', error)
      }
    }

    // 立即获取一次
    fetchLogs()
    
    // 每3秒更新一次日志
    const logInterval = setInterval(fetchLogs, 3000)
    
    return () => clearInterval(logInterval)
  }, [project.id, project.status])

  // 日志轮播
  useEffect(() => {
    if (logs.length <= 1) return
    
    const interval = setInterval(() => {
      setCurrentLogIndex(prev => (prev + 1) % logs.length)
    }, 2000) // 每2秒切换一条日志
    
    return () => clearInterval(interval)
  }, [logs.length])

  const getStatusColor = (status: Project['status']) => {
    switch (status) {
      case 'completed': return 'success'
      case 'processing': return 'processing'
      case 'error': return 'error'
      case 'uploading': return 'default'
      default: return 'default'
    }
  }

  // 检查是否是等待处理状态 - pending状态显示为导入中
  const isImporting = project.status === 'pending'
  
  // 状态标准化处理 - pending状态显示为导入中
  const normalizedStatus = project.status === 'error' ? 'failed' : 
                          isImporting ? 'importing' : project.status
  
  // 调试信息
  console.log('ProjectCard Debug:', {
    projectId: project.id,
    projectStatus: project.status,
    isImporting,
    normalizedStatus,
    processingConfig: project.processing_config
  })
  
  // 计算进度百分比
  const progressPercent = project.status === 'completed' ? 100 : 
                         project.status === 'failed' ? 0 :
                         isImporting ? 20 : // 导入中显示20%进度
                         project.current_step && project.total_steps ? 
                         Math.round((project.current_step / project.total_steps) * 100) : 
                         project.status === 'processing' ? 10 : 0

  const handleRetry = async () => {
    if (isRetrying) return
    
    setIsRetrying(true)
    try {
      // 对于PENDING状态的项目，使用startProcessing；对于其他状态，使用retryProcessing
      if (project.status === 'pending') {
        await projectApi.startProcessing(project.id)
      } else {
        await projectApi.retryProcessing(project.id)
      }
      // 移除重复的toast显示，让父组件统一处理
      if (onRetry) {
        onRetry(project.id)
      }
    } catch (error) {
      console.error('重试失败:', error)
      message.error('重试失败，请稍后再试')
    } finally {
      setIsRetrying(false)
    }
  }

  return (
    <Card
      hoverable
      className="project-card"
      style={{ 
        width: 200, 
        height: 240,
        borderRadius: '4px',
        overflow: 'hidden',
        background: 'linear-gradient(145deg, #1e1e1e 0%, #2a2a2a 100%)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)',
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        cursor: 'pointer',
        marginBottom: '0px'
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-4px)'
        e.currentTarget.style.boxShadow = '0 8px 30px rgba(0, 0, 0, 0.4)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)'
        e.currentTarget.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.3)'
      }}
      bodyStyle={{
        padding: '12px',
        background: 'transparent',
        height: 'calc(100% - 120px)',
        display: 'flex',
        flexDirection: 'column'
      }}
      cover={
        <div 
          style={{ 
            height: 120, 
            position: 'relative',
            background: videoThumbnail 
              ? `url(${videoThumbnail}) center/cover` 
              : 'linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            overflow: 'hidden'
          }}
          onClick={() => {
            // 导入中状态的项目不能点击进入详情页
            if (project.status === 'pending') {
              message.warning('项目正在导入中，请稍后再查看详情')
              return
            }
            
            if (onClick) {
              onClick()
            } else {
              navigate(`/project/${project.id}`)
            }
          }}
        >
          {/* 缩略图加载状态 */}
          {thumbnailLoading && (
            <div style={{ 
              textAlign: 'center',
              color: 'rgba(255, 255, 255, 0.8)'
            }}>
              <LoadingOutlined 
                style={{ 
                  fontSize: '24px', 
                  marginBottom: '4px'
                }} 
              />
              <div style={{ 
                fontSize: '12px',
                fontWeight: 500
              }}>
                生成封面中...
              </div>
            </div>
          )}
          
          {/* 无缩略图时的默认显示 */}
          {!videoThumbnail && !thumbnailLoading && (
            <div style={{ textAlign: 'center' }}>
              <PlayCircleOutlined 
                style={{ 
                  fontSize: '40px', 
                  color: 'rgba(255, 255, 255, 0.9)',
                  marginBottom: '4px',
                  filter: 'drop-shadow(0 2px 8px rgba(0,0,0,0.3))'
                }} 
              />
              <div style={{ 
                color: 'rgba(255, 255, 255, 0.8)', 
                fontSize: '12px',
                fontWeight: 500
              }}>
                点击预览
              </div>
            </div>
          )}
          
          {/* 分类标签 - 左上角 */}
          {project.video_category && project.video_category !== 'default' && (
            <div style={{
              position: 'absolute',
              top: '8px',
              left: '8px'
            }}>
              <Tag
                style={{
                  background: `${getCategoryInfo(project.video_category).color}15`,
                  border: `1px solid ${getCategoryInfo(project.video_category).color}40`,
                  borderRadius: '3px',
                  color: getCategoryInfo(project.video_category).color,
                  fontSize: '10px',
                  fontWeight: 500,
                  padding: '2px 6px',
                  lineHeight: '14px',
                  height: '18px',
                  margin: 0
                }}
              >
                <span style={{ marginRight: '2px' }}>{getCategoryInfo(project.video_category).icon}</span>
                {getCategoryInfo(project.video_category).name}
              </Tag>
            </div>
          )}
          
          {/* 移除右上角状态指示器 - 可读性差且冗余 */}
          
          {/* 更新时间和操作按钮 - 移动到封面底部 */}
          <div style={{
            position: 'absolute',
            bottom: '0',
            left: '0',
            right: '0',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: 'rgba(0, 0, 0, 0.7)',
            backdropFilter: 'blur(10px)',
            borderRadius: '0',
            padding: '6px 8px',
            height: '28px'
          }}>
            <Text style={{ fontSize: '12px', color: 'rgba(255, 255, 255, 0.8)' }}>
              {dayjs(project.created_at).tz('Asia/Shanghai').fromNow()}
            </Text>
            
            {/* 操作按钮 */}
            <div 
              className="card-action-buttons"
              style={{
                display: 'flex',
                gap: '4px',
                opacity: 0,
                transition: 'opacity 0.3s ease'
              }}
            >
              {/* 失败状态：只显示重试和删除按钮 */}
              {normalizedStatus === 'failed' ? (
                <>
                  <Button
                    type="text"
                    icon={<ReloadOutlined />}
                    loading={isRetrying}
                    onClick={(e) => {
                      e.stopPropagation()
                      handleRetry()
                    }}
                    style={{
                      height: '20px',
                      width: '20px',
                      borderRadius: '3px',
                      color: '#52c41a',
                      border: '1px solid rgba(82, 196, 26, 0.5)',
                      background: 'rgba(82, 196, 26, 0.1)',
                      padding: 0,
                      minWidth: '20px',
                      fontSize: '10px'
                    }}
                  />
                  
                  <Popconfirm
                    title="确定要删除这个项目吗？"
                    description="删除后无法恢复"
                    onConfirm={(e) => {
                      e?.stopPropagation()
                      onDelete(project.id)
                    }}
                    onCancel={(e) => {
                      e?.stopPropagation()
                    }}
                    okText="确定"
                    cancelText="取消"
                  >
                    <Button
                      type="text"
                      icon={<DeleteOutlined />}
                      onClick={(e) => {
                        e.stopPropagation()
                      }}
                      style={{
                        height: '20px',
                        width: '20px',
                        borderRadius: '3px',
                        color: '#ff6b6b',
                        border: '1px solid rgba(255, 107, 107, 0.5)',
                        background: 'rgba(255, 107, 107, 0.1)',
                        padding: 0,
                        minWidth: '20px',
                        fontSize: '10px'
                      }}
                    />
                  </Popconfirm>
                </>
              ) : (
                /* 其他状态：显示下载、重试和删除按钮 */
                <>
                  <Space size={4}>
                    {/* 重试按钮 - 在处理中和等待中状态显示，允许用户重新提交任务 */}
                    {(normalizedStatus === 'processing' || normalizedStatus === 'importing' || project.status === 'pending') && (
                      <Tooltip title={project.status === 'pending' ? "开始处理" : "重新提交任务"}>
                        <Button
                          type="text"
                          icon={<ReloadOutlined />}
                          loading={isRetrying}
                          onClick={(e) => {
                            e.stopPropagation()
                            handleRetry()
                          }}
                          style={{
                            width: '20px',
                            height: '20px',
                            borderRadius: '3px',
                            color: '#1890ff',
                            border: '1px solid rgba(24, 144, 255, 0.5)',
                            background: 'rgba(24, 144, 255, 0.1)',
                            padding: 0,
                            minWidth: '20px',
                            fontSize: '10px'
                          }}
                        />
                      </Tooltip>
                    )}
                    
                    {/* 下载按钮 - 仅在完成状态显示 */}
                    {normalizedStatus === 'completed' && (
                      <Button
                        type="text"
                        icon={<DownloadOutlined />}
                        onClick={(e) => {
                          e.stopPropagation()
                          // 实现下载功能
                          message.info('下载功能开发中...')
                        }}
                        style={{
                          width: '20px',
                          height: '20px',
                          borderRadius: '3px',
                          color: 'rgba(255, 255, 255, 0.8)',
                          border: '1px solid rgba(255, 255, 255, 0.2)',
                          background: 'rgba(255, 255, 255, 0.1)',
                          padding: 0,
                          minWidth: '20px',
                          fontSize: '10px'
                        }}
                      />
                    )}
                    
                    {/* 删除按钮 */}
                    <Popconfirm
                      title="确定要删除这个项目吗？"
                      description="删除后无法恢复"
                      onConfirm={(e) => {
                        e?.stopPropagation()
                        onDelete(project.id)
                      }}
                      onCancel={(e) => {
                        e?.stopPropagation()
                      }}
                      okText="确定"
                      cancelText="取消"
                    >
                      <Button
                        type="text"
                        icon={<DeleteOutlined />}
                        onClick={(e) => {
                          e.stopPropagation()
                        }}
                        style={{
                          width: '20px',
                          height: '20px',
                          borderRadius: '3px',
                          color: 'rgba(255, 255, 255, 0.8)',
                          border: '1px solid rgba(255, 255, 255, 0.2)',
                          background: 'rgba(255, 255, 255, 0.1)',
                          padding: 0,
                          minWidth: '20px',
                          fontSize: '10px'
                        }}
                      />
                    </Popconfirm>
                  </Space>
                 </>
               )}
            </div>
          </div>
        </div>
      }
    >
      <div style={{ padding: '0', flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
        <div>
          {/* 项目名称 - 始终在顶部 */}
          <div style={{ marginBottom: '12px', position: 'relative' }}>
            <Tooltip title={project.name} placement="top">
              <Text 
                strong 
                style={{ 
                  fontSize: '13px', 
                  color: '#ffffff',
                  fontWeight: 600,
                  lineHeight: '16px',
                  display: '-webkit-box',
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  cursor: 'help',
                  height: '32px'
                }}
              >
                {project.name}
              </Text>
            </Tooltip>
          </div>
          
          {/* 状态和统计信息 */}
          {(normalizedStatus === 'importing' || normalizedStatus === 'processing' || normalizedStatus === 'failed') ? (
            // 导入中、处理中、失败：只显示状态块，居中展示
            <div style={{ 
              display: 'flex', 
              justifyContent: 'center',
              marginBottom: '12px'
            }}>
              <div style={{ width: '100%', maxWidth: '200px' }}>
                <UnifiedStatusBar
                  projectId={project.id}
                  status={normalizedStatus}
                  downloadProgress={progressPercent}
                  onStatusChange={(newStatus) => {
                    console.log(`项目 ${project.id} 状态变化: ${normalizedStatus} -> ${newStatus}`)
                  }}
                  onDownloadProgressUpdate={(progress) => {
                    console.log(`项目 ${project.id} 下载进度更新: ${progress}%`)
                  }}
                />
              </div>
            </div>
          ) : (
            // 其他状态：显示状态块 + 切片数 + 合集数
            <div style={{ 
              display: 'flex', 
              gap: '6px',
              marginBottom: '12px'
            }}>
              {/* 状态显示 - 占据更多空间 */}
              <div style={{ flex: 2 }}>
                <UnifiedStatusBar
                  projectId={project.id}
                  status={normalizedStatus}
                  downloadProgress={progressPercent}
                  onStatusChange={(newStatus) => {
                    console.log(`项目 ${project.id} 状态变化: ${normalizedStatus} -> ${newStatus}`)
                  }}
                  onDownloadProgressUpdate={(progress) => {
                    console.log(`项目 ${project.id} 下载进度更新: ${progress}%`)
                  }}
                />
              </div>
              
              {/* 切片数量 - 减小宽度 */}
              <div style={{
                background: 'rgba(102, 126, 234, 0.15)',
                border: '1px solid rgba(102, 126, 234, 0.3)',
                borderRadius: '3px',
                padding: '3px 4px',
                textAlign: 'center',
                minWidth: '50px',
                flex: 0.8
              }}>
                <div style={{ color: '#667eea', fontSize: '11px', fontWeight: 600, lineHeight: '12px' }}>
                  {project.total_clips || 0}
                </div>
                <div style={{ color: '#999999', fontSize: '8px', lineHeight: '9px' }}>
                  切片
                </div>
              </div>
              
              {/* 合集数量 - 减小宽度 */}
              <div style={{
                background: 'rgba(118, 75, 162, 0.15)',
                border: '1px solid rgba(118, 75, 162, 0.3)',
                borderRadius: '3px',
                padding: '3px 4px',
                textAlign: 'center',
                minWidth: '50px',
                flex: 0.8
              }}>
                <div style={{ color: '#764ba2', fontSize: '11px', fontWeight: 600, lineHeight: '12px' }}>
                  {project.total_collections || 0}
                </div>
                <div style={{ color: '#999999', fontSize: '8px', lineHeight: '9px' }}>
                  合集
                </div>
              </div>
            </div>
          )}

          {/* 详细进度显示已隐藏 - 只在状态块中显示百分比 */}

        </div>
      </div>
    </Card>
  )
}

export default ProjectCard
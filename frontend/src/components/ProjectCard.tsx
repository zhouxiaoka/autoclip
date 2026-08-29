import React, { useState, useEffect } from 'react'
import { Card, Tag, Button, Space, Typography, Popconfirm, message, Tooltip } from 'antd'
import { PlayCircleOutlined, DeleteOutlined, DownloadOutlined, ReloadOutlined, LoadingOutlined } from '@ant-design/icons'
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
import 'dayjs/locale/en'

dayjs.extend(relativeTime)
dayjs.extend(timezone)
dayjs.extend(utc)
dayjs.locale('en')

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

const { Text } = Typography

// Tracks which project ids have already had a best-effort auto-start, surviving
// component remounts (the list briefly unmounts while HomePage shows its
// loading spinner). A useRef would reset on every remount and let auto-start
// fire again, which created an infinite onRetry→loadProjects→remount loop.
// Project ids are unique per import, so once-per-session is exactly right.
const autoStartedProjectIds = new Set<string>()

interface ProjectCardProps {
  project: Project
  onDelete: (id: string) => void
  onRetry?: (id: string) => void
  onClick?: () => void
}

const ProjectCard: React.FC<ProjectCardProps> = ({ project, onDelete, onRetry, onClick }) => {
  const navigate = useNavigate()
  const [videoThumbnail, setVideoThumbnail] = useState<string | null>(null)
  const [thumbnailLoading, setThumbnailLoading] = useState(false)
  const [isRetrying, setIsRetrying] = useState(false)

  // 获取分类信息
  const getCategoryInfo = (category?: string) => {
    const categoryMap: Record<string, { name: string; icon: string; color: string }> = {
      'default': { name: 'Default', icon: '🎬', color: '#4facfe' },
      'knowledge': { name: 'Knowledge', icon: '📚', color: '#52c41a' },
      'business': { name: 'Business', icon: '💼', color: '#faad14' },
      'opinion': { name: 'Opinion', icon: '💭', color: '#722ed1' },
      'experience': { name: 'Experience', icon: '🌟', color: '#13c2c2' },
      'speech': { name: 'Speech', icon: '🎤', color: '#eb2f96' },
      'content_review': { name: 'Review', icon: '🎭', color: '#f5222d' },
      'entertainment': { name: 'Entertainment', icon: '🎪', color: '#fa8c16' }
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

  // 检查是否是下载状态 - 根据下载进度判断
  const downloadProgress = project.processing_config?.download_progress || project.settings?.download_progress || 0
  const isDownloading = project.status === 'pending' && downloadProgress > 0 && downloadProgress < 100
  const isImporting = project.status === 'pending' && !isDownloading
  
  // 状态标准化处理
  const normalizedStatus = project.status === 'error' ? 'failed' : 
                          isDownloading ? 'downloading' :
                          isImporting ? 'importing' : project.status
  
  // 调试信息
  console.log('ProjectCard Debug:', {
    projectId: project.id,
    projectStatus: project.status,
    downloadProgress,
    isDownloading,
    isImporting,
    normalizedStatus,
    processingConfig: project.processing_config
  })

  // 自动启动 pending 状态的项目（但不包括下载中的项目）。
  // 关键：每个项目最多只自动尝试一次，且失败时不弹 toast。
  // 之前这里把 isRetrying 放进依赖、又在 handleRetry 里翻转 isRetrying，
  // 导致 effect 反复触发 → 对一个还没下载完的 B站项目疯狂 POST /process（返回
  // 400 "Video file not found"）→ 满屏「重试失败」。下载完成后后端会自动启动
  // 流水线，所以这里只需做一次「尽力而为」的启动即可。
  useEffect(() => {
    if (
      project.status === 'pending' &&
      !isDownloading &&
      !autoStartedProjectIds.has(project.id)
    ) {
      autoStartedProjectIds.add(project.id)
      // Best-effort, one-shot per project. Uploads (file already present) start
      // processing; B站 imports whose download isn't done yet return 400 here —
      // that's fine, the backend auto-starts the pipeline when the download
      // completes. Silent + no onRetry so this never drives the parent's
      // toast/reload path.
      handleRetry({ silent: true })
    }
  }, [project.status, project.id, isDownloading])
  
  // 计算进度百分比
  const progressPercent = project.status === 'completed' ? 100 : 
                         project.status === 'failed' ? 0 :
                         isDownloading ? downloadProgress : // 下载中显示实际下载进度
                         isImporting ? 5 : // pending状态显示5%进度，表示等待处理
                         project.current_step && project.total_steps ? 
                         Math.round((project.current_step / project.total_steps) * 100) : 
                         project.status === 'processing' ? 10 : 0

  const handleRetry = async (opts?: { silent?: boolean }) => {
    if (isRetrying) return

    setIsRetrying(true)
    try {
      // 对于PENDING状态的项目，使用startProcessing；对于其他状态，使用retryProcessing
      if (project.status === 'pending') {
        await projectApi.startProcessing(project.id)
      } else {
        await projectApi.retryProcessing(project.id)
      }
      // 让父组件统一处理 toast / 刷新。但「静默自动启动」绝不能触发父组件，
      // 否则会走 handleRetryProject → loadProjects → 列表重挂载 → 再次自动启动
      // 的死循环。只有用户手动点重试才通知父组件。
      if (onRetry && !opts?.silent) {
        onRetry(project.id)
      }
    } catch (error) {
      console.error('重试失败:', error)
      // 自动启动（silent）失败不打扰用户；只有用户手动点重试才提示。
      if (!opts?.silent) {
      message.error('Retry failed. Please try again.')
      }
    } finally {
      setIsRetrying(false)
    }
  }

  return (
    <Card
      hoverable
      className="project-card"
      style={{
        width: '100%',
        borderRadius: '16px',
        overflow: 'hidden',
        background: 'var(--ac-card)',
        border: '1px solid var(--ac-line)',
        boxShadow: 'none',
        transition: 'all 0.2s ease',
        cursor: 'pointer',
        marginBottom: '0px'
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-2px)'
        e.currentTarget.style.boxShadow = 'var(--ac-shadow)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)'
        e.currentTarget.style.boxShadow = 'none'
      }}
      bodyStyle={{
        padding: '18px 20px 20px',
        background: 'transparent',
        display: 'flex',
        flexDirection: 'column'
      }}
      cover={
        <div
          style={{
            height: 160,
            position: 'relative',
            background: videoThumbnail
              ? `url(${videoThumbnail}) center/cover`
              : 'var(--ac-thumb)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            overflow: 'hidden'
          }}
          onClick={() => {
            // 导入中状态的项目不能点击进入详情页
            if (project.status === 'pending') {
              message.warning('This project is still importing. Try again in a moment.')
              return
            }
            
            // 处理中状态的项目不能点击进入详情页
            if (project.status === 'processing') {
              message.warning('This project is still processing.')
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
            <div style={{ textAlign: 'center', color: 'var(--ac-muted)' }}>
              <LoadingOutlined style={{ fontSize: '22px', marginBottom: '4px' }} />
              <div style={{ fontSize: '12px' }}>Generating cover…</div>
            </div>
          )}

          {/* 无缩略图时的默认显示 */}
          {!videoThumbnail && !thumbnailLoading && (
            <PlayCircleOutlined style={{ fontSize: '32px', color: 'var(--ac-muted)' }} />
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
            alignItems: 'flex-end',
            background: 'linear-gradient(to top, rgba(0,0,0,0.42), rgba(0,0,0,0))',
            borderRadius: '0',
            padding: '10px 12px',
            height: '52px'
          }}>
            <Text style={{ fontSize: '12px', color: 'rgba(255, 255, 255, 0.92)' }}>
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
                    title="Delete this project?"
                    description="This cannot be undone."
                    onConfirm={(e) => {
                      e?.stopPropagation()
                      onDelete(project.id)
                    }}
                    onCancel={(e) => {
                      e?.stopPropagation()
                    }}
                    okText="Delete"
                    cancelText="Cancel"
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
                      <Tooltip title={project.status === 'pending' ? "Start processing" : "Retry"}>
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
                          message.info('Download is coming soon')
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
                      title="Delete this project?"
                      description="This cannot be undone."
                      onConfirm={(e) => {
                        e?.stopPropagation()
                        onDelete(project.id)
                      }}
                      onCancel={(e) => {
                        e?.stopPropagation()
                      }}
                      okText="Delete"
                      cancelText="Cancel"
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
          
          {/* 状态和统计信息 — Calm Premium，见 DESIGN.md */}
          {(normalizedStatus === 'importing' || normalizedStatus === 'downloading' || normalizedStatus === 'processing' || normalizedStatus === 'failed') ? (
            // 进行中 / 失败：细进度线或终态点，占满宽度
            <div style={{ marginBottom: '2px' }}>
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
          ) : (
            // 已完成：● 已完成  +  灰色 mono 元信息（N 切片 · M 合集）
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '2px' }}>
              <UnifiedStatusBar
                projectId={project.id}
                status={normalizedStatus}
                downloadProgress={progressPercent}
                onStatusChange={() => {}}
              />
              <div style={{ color: 'var(--ac-muted)', fontSize: '12.5px', whiteSpace: 'nowrap' }}>
                <span className="ac-mono">{project.total_clips || 0}</span> clips
                <span style={{ margin: '0 6px' }}>·</span>
                <span className="ac-mono">{project.total_collections || 0}</span> collections
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
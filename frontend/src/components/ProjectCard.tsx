import { t } from '../i18n'
import { useTranslation } from 'react-i18next'
import React, { useState, useEffect } from 'react'
import { message } from 'antd'
import { useNavigate } from 'react-router-dom'
import { Project } from '../store/useProjectStore'
import { projectApi } from '../services/api'
import { studioApi } from '../features/studio/api'
import { UnifiedStatusBar } from './UnifiedStatusBar'
import FeedbackDialog from './FeedbackDialog'
import { useSimpleProgressStore } from '../stores/useSimpleProgressStore'
import { Btn, Dialog, Icon, StatusDot } from '../ui'
import { classifyLlmKeyFailure } from '../utils/llmFailure'
import { classifySubtitleFailure } from '../utils/subtitleFailure'
import { classifyTimelineEmpty } from '../utils/timelineFailure'
import { isSourceDownloading, readDownloadProgress } from '../utils/downloadProgress'
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
  useTranslation()
  const navigate = useNavigate()
  const creative = project.settings?.creative || project.processing_config?.creative
  const isVisual = ['highlight', 'promo'].includes(creative?.goal)
  const isManaged = isVisual || !!project.settings?.smart_import || !!project.processing_config?.smart_import
  const [videoThumbnail, setVideoThumbnail] = useState<string | null>(null)
  const [thumbnailLoading, setThumbnailLoading] = useState(false)
  const [isRetrying, setIsRetrying] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)

  // 获取分类信息
  const isExample = !!(project.settings?.example || project.processing_config?.example)
  const getCategoryInfo = (category?: string) => {
    const categoryMap: Record<string, string> = {
      default: t("默认"), knowledge: t("知识科普"), business: t("商业财经"),
      opinion: t("观点评论"), experience: t("经验分享"), speech: t("演讲脱口秀"),
      content_review: t("内容解说"), entertainment: t("娱乐内容"),
    }
    return categoryMap[category || 'default'] || categoryMap.default
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
        const possiblePaths = [studioApi.source(project.id)]
        
        let videoLoaded = false
        
        for (const path of possiblePaths) {
          if (videoLoaded) break
          
          try {
            const videoUrl = path
            console.log('尝试加载视频:', videoUrl)
            
            await new Promise((resolve, reject) => {
              const timeoutId = setTimeout(() => {
                reject(new Error(t("视频加载超时")))
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
                    reject(new Error(t("无法获取canvas上下文")))
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
  }, [project.id, project.video_path, project.thumbnail, thumbnailCacheKey])

  // 片源进度在接口的 settings 上（后端字段名 processing_config）。
  // 读错字段时进度恒为 0，下面会把所有 pending 画成 5%。
  const downloadProgress = readDownloadProgress(project)
  const isDownloading = isSourceDownloading(project)
  const awaitingConfirmation = project.status === 'pending' && !!(project.settings?.awaiting_confirmation || project.processing_config?.awaiting_confirmation)
  const isImporting = project.status === 'pending' && !isDownloading && !awaitingConfirmation
  
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
      !isManaged && project.status === 'pending' &&
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
  }, [project.status, project.id, isDownloading, isManaged])
  
  // 计算进度百分比
  const progressPercent = project.status === 'completed' ? 100 : 
                         project.status === 'failed' ? 0 :
                         isDownloading ? downloadProgress : // 下载中显示实际下载进度
                         isImporting ? 5 : // pending状态显示5%进度，表示等待处理
                         project.current_step && project.total_steps ? 
                         Math.round((project.current_step / project.total_steps) * 100) : 
                         project.status === 'processing' ? 10 : 0

  const [feedbackOpen, setFeedbackOpen] = useState(false)
  const failedProgress = useSimpleProgressStore((st) => st.getProgress(project.id))
  const failureContext = {
    source: 'failure' as const,
    project_id: project.id,
    stage: failedProgress?.stage,
    error_message: project.error_message || failedProgress?.message || undefined,
    error_code: project.error_code || undefined,
  }
  const failureText = project.error_message || failedProgress?.message
  const timelineEmpty = classifyTimelineEmpty(failureText, project.error_code)
  const llmKeyFailure = !timelineEmpty && classifyLlmKeyFailure(failureText, project.error_code)
  const subtitleFailure = timelineEmpty
    ? null
    : classifySubtitleFailure(failureText, project.error_code)

  const handleRetry = async (opts?: { silent?: boolean }) => {
    if (isRetrying) return

    setIsRetrying(true)
    try {
      // 对于PENDING状态的项目，使用startProcessing；对于其他状态，使用retryProcessing
      if (isManaged) {
        navigate(`/import/${project.id}`)
        return
      } else if (project.status === 'pending') {
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
        message.error(t("重试失败，请稍后再试"))
      }
    } finally {
      setIsRetrying(false)
    }
  }

  const openProject = () => {
    if (!isManaged && project.status === 'pending') {
      message.warning(t("项目正在导入中，请稍后再查看详情"))
      return
    }
    if (!isManaged && project.status === 'processing') {
      message.warning(t("项目处理中，请完成后再查看"))
      return
    }
    if (awaitingConfirmation) navigate(`/import/${project.id}`)
    else if (onClick) onClick()
    else navigate(`/project/${project.id}`)
  }

  return (
    <>
      <article className="ac-card ac-project-card">
        <div className="ac-card-thumb" style={{ backgroundImage: videoThumbnail ? `url(${videoThumbnail})` : undefined }}>
          <button type="button" className="ac-project-open" aria-label={project.name} onClick={openProject}>
            {!videoThumbnail && <Icon.Play size={30} />}
            {thumbnailLoading && <span className="ac-project-thumbnail-loading">{t("生成封面中…")}</span>}
          </button>
          <div className="ac-project-tags">
            {isExample && <span className="ac-tag ac-tag--sans">{t("示例")}</span>}
            {project.video_category && project.video_category !== 'default' && <span className="ac-tag ac-tag--sans">{getCategoryInfo(project.video_category)}</span>}
          </div>
        </div>
        <div className="ac-card-body">
          <button type="button" className="ac-project-title" onClick={openProject} title={project.name}>
            <span className="ac-card-title">{project.name}</span>
          </button>
          {awaitingConfirmation ? (
            <div className="ac-project-status"><StatusDot tone="muted" label={t("待确认制作类型")} /><Btn size="sm" onClick={() => navigate(`/import/${project.id}`)}>{t("查看建议")}</Btn></div>
          ) : isManaged && project.status === 'processing' ? (
            <StatusDot tone="accent" label={t("制作中 · 查看进度")} />
          ) : (
            <UnifiedStatusBar projectId={project.id} status={normalizedStatus} downloadProgress={progressPercent} />
          )}
          {normalizedStatus === 'completed' && (
            <div className="ac-project-counts ac-mono">
              {isVisual ? t('成片草稿数量', { count: project.settings?.studio_draft_count || project.processing_config?.studio_draft_count || 0 }) : <>{t("切片数量", { count: project.total_clips || 0 })}<span> · </span>{t("合集数量", { count: project.total_collections || 0 })}</>}
            </div>
          )}
          {normalizedStatus === 'failed' && failureText && (
            <div className="ac-empty ac-project-error" role="alert">
              <span className="ac-mono">{failureText}</span>
            </div>
          )}
          {normalizedStatus === 'failed' && (
            <div className="ac-project-recovery">
              {subtitleFailure && <Btn variant="text" size="sm" onClick={() => navigate('/settings?section=speech')}>{t("转写设置")}</Btn>}
              {llmKeyFailure && <Btn variant="text" size="sm" onClick={() => navigate('/settings?section=model')}>{t("模型设置")}</Btn>}
              <Btn variant="text" size="sm" loading={isRetrying} onClick={() => handleRetry()}>{t("重试")}</Btn>
              <Btn variant="text" size="sm" onClick={() => setFeedbackOpen(true)}>{t("反馈")}</Btn>
            </div>
          )}
          <div className="ac-card-foot">
            <time className="meta" dateTime={project.created_at}>{dayjs(project.created_at).fromNow()}</time>
            <div className="ac-card-actions">
              {(normalizedStatus === 'processing' || normalizedStatus === 'importing') && !isManaged && <Btn variant="text" size="sm" loading={isRetrying} onClick={() => handleRetry()} title={t("重新提交任务")}><Icon.Refresh /></Btn>}
              <Btn variant="danger" size="sm" onClick={() => setDeleteOpen(true)} title={t("删除")} aria-label={t("删除")}><Icon.Trash /></Btn>
            </div>
          </div>
        </div>
      </article>
      <Dialog open={deleteOpen} onClose={() => setDeleteOpen(false)} title={t("确定要删除这个项目吗？")} description={t("删除后无法恢复")}
        footer={<div className="right"><Btn onClick={() => setDeleteOpen(false)}>{t("取消")}</Btn><Btn variant="danger" onClick={() => { setDeleteOpen(false); onDelete(project.id) }}>{t("确定")}</Btn></div>} />
      <FeedbackDialog open={feedbackOpen} onClose={() => setFeedbackOpen(false)} context={failureContext} />
    </>
  )
}

export default ProjectCard

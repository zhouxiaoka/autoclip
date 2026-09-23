import React, { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, Navigate } from 'react-router-dom'
import { message } from 'antd'
import dayjs from 'dayjs'
import { useProjectStore, Collection } from '../store/useProjectStore'
import { projectApi } from '../services/api'
import StudioResults from '../features/studio/StudioResults'
import { studioApi, errorText } from '../features/studio/api'
import ClipCard from '../components/ClipCard'
import CollectionCard from '../components/CollectionCard'
import CollectionPreviewModal from '../components/CollectionPreviewModal'
import CreateCollectionModal from '../components/CreateCollectionModal'
import { useCollectionVideoDownload } from '../hooks/useCollectionVideoDownload'
import { ProjectTaskManager } from '../components/ProjectTaskManager'
import FeedbackDialog from '../components/FeedbackDialog'
import { Btn, Icon, parseTimecode, fmtDuration } from '../ui'

const ProjectDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const {
    currentProject,
    setCurrentProject,
    upsertProject,
    updateCollection,
    addCollection,
    deleteCollection,
    removeClipFromCollection,
    reorderCollectionClips,
    addClipToCollection
  } = useProjectStore()

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const loadVersion = useRef(0)
  const [statusLoading, setStatusLoading] = useState(false)
  const [showCreateCollection, setShowCreateCollection] = useState(false)
  const [feedbackOpen, setFeedbackOpen] = useState(false)
  const [showCollectionDetail, setShowCollectionDetail] = useState(false)
  const [selectedCollection, setSelectedCollection] = useState<Collection | null>(null)
  const { generateAndDownloadCollectionVideo } = useCollectionVideoDownload()

  useEffect(() => {
    if (!id) return
    loadProject()
    loadProcessingStatus()
    return () => { loadVersion.current += 1 }
  }, [id])

  const loadProject = async () => {
    if (!id) return
    const version = ++loadVersion.current
    setError('')
    if (currentProject?.id !== id) setLoading(true)
    try {
      const project = await projectApi.getProject(id)
      if (version !== loadVersion.current) return
      if (project.status === 'completed') {
        try {
          const [clips, collections] = await Promise.all([
            projectApi.getClips(id),
            projectApi.getCollections(id)
          ])
          if (version !== loadVersion.current) return
          const projectWithData = { ...project, clips: clips || [], collections: collections || [] }
          setCurrentProject(projectWithData)
          // 同步更新项目列表，避免页面与列表状态漂移
          upsertProject(projectWithData)
        } catch (err) {
          if (version !== loadVersion.current) return
          console.error('Failed to load clips/collections:', err)
          setCurrentProject(project)
        }
      } else {
        setCurrentProject(project)
      }
    } catch (err) {
      if (version !== loadVersion.current) return
      setError(errorText(err))
    } finally {
      if (version === loadVersion.current) setLoading(false)
    }
  }

  const loadProcessingStatus = async () => {
    if (!id) return
    setStatusLoading(true)
    try {
      await projectApi.getProcessingStatus(id)
    } catch (err) {
      console.error('Failed to load processing status:', err)
    } finally {
      setStatusLoading(false)
    }
  }

  const handleStartProcessing = async () => {
    if (!id) return
    try {
      await projectApi.startProcessing(id)
      message.success('开始处理')
      loadProcessingStatus()
    } catch (err) {
      console.error('Failed to start processing:', err)
      message.error('启动处理失败')
    }
  }

  const handleRetryProcessing = async () => {
    if (!id) return
    setStatusLoading(true)
    try {
      await projectApi.retryProcessing(id)
      message.success('已重新开始处理')
      loadProcessingStatus()
      await loadProject()
    } catch (err) {
      console.error('Failed to retry processing:', err)
      message.error('重试失败，请稍后再试')
    } finally {
      setStatusLoading(false)
    }
  }

  const handleCreateCollection = async (title: string, summary: string, clipIds: string[]) => {
    if (!id) return
    try {
      await addCollection(id, {
        id: `collection_${Date.now()}`,
        collection_title: title,
        collection_summary: summary,
        clip_ids: clipIds,
        collection_type: 'manual',
        created_at: new Date().toISOString()
      })
      setShowCreateCollection(false)
      message.success('合集创建成功')
    } catch (err) {
      console.error('Failed to create collection:', err)
      message.error('创建合集失败')
    }
  }

  const handleViewCollection = (collection: Collection) => {
    setSelectedCollection(collection)
    setShowCollectionDetail(true)
  }

  const handleRemoveClipFromCollection = async (collectionId: string, clipId: string): Promise<void> => {
    if (!id) return
    try {
      await removeClipFromCollection(id, collectionId, clipId)
      message.success('切片已从合集中移除')
    } catch (err) {
      console.error('Failed to remove clip from collection:', err)
      message.error('移除切片失败')
    }
  }

  const handleDeleteCollection = async (collectionId: string) => {
    if (!id) return
    try {
      await deleteCollection(id, collectionId)
      setShowCollectionDetail(false)
      setSelectedCollection(null)
      message.success('合集已删除')
    } catch (err) {
      console.error('Failed to delete collection:', err)
      message.error('删除合集失败')
    }
  }

  const handleReorderCollectionClips = async (collectionId: string, newClipIds: string[]): Promise<void> => {
    if (!id) return
    try {
      await reorderCollectionClips(id, collectionId, newClipIds)
      message.success('合集顺序已更新')
    } catch (err) {
      console.error('Failed to reorder collection clips:', err)
      message.error('更新合集顺序失败')
    }
  }

  const handleAddClipToCollection = async (collectionId: string, clipIds: string[]): Promise<void> => {
    if (!id) return
    try {
      await addClipToCollection(id, collectionId, clipIds)
      message.success('切片已添加到合集')
    } catch (err) {
      console.error('Failed to add clip to collection:', err)
      message.error('添加切片失败')
    }
  }

  const createDraft = async (clipIds: string[], title: string) => {
    try {
      const draft = await studioApi.create(id!, clipIds, title, true)
      navigate(`/project/${id}/studio/${draft.id}`)
    } catch (e) { message.error(errorText(e)) }
  }

  const getSortedClips = () => {
    if (!currentProject?.clips) return []
    const clips = [...currentProject.clips]
    return clips.sort((a, b) => b.final_score - a.final_score)
  }

  if (loading) {
    return (
      <div className="ac-page" style={{ display: 'flex', justifyContent: 'center', paddingTop: 120 }}>
        <span className="ac-btn ac-btn--text" style={{ color: 'var(--ac-muted)' }}><span className="spin" /> 加载中</span>
      </div>
    )
  }

  if (error || !currentProject || currentProject.id !== id) {
    return (
      <div className="ac-page">
        <div className="ac-empty">
          <b>加载失败</b>
          {error || '项目不存在'}
          <div style={{ marginTop: 16 }}>
            <Btn size="sm" onClick={() => navigate('/')}>返回首页</Btn>
          </div>
        </div>
      </div>
    )
  }

  if (currentProject.settings?.import_staging || currentProject.processing_config?.import_staging) return <Navigate to={`/import/${id}`} replace />

  const clips = currentProject.clips || []
  const collections = currentProject.collections || []
  const totalClipSec = clips.reduce((s, c) => s + Math.max(0, parseTimecode(c.end_time) - parseTimecode(c.start_time)), 0)
  const sortedCollections = [...collections].sort((a, b) => {
    const ta = a.created_at ? new Date(a.created_at).getTime() : 0
    const tb = b.created_at ? new Date(b.created_at).getTime() : 0
    return tb - ta
  })
  const isVisual = !!currentProject.settings?.smart_import || !!currentProject.processing_config?.smart_import || ['highlight', 'promo'].includes(currentProject.settings?.creative?.goal || currentProject.processing_config?.creative?.goal)
  const isCompleted = currentProject.status === 'completed'
  const isFailed = currentProject.status === 'failed' || (currentProject.status as string) === 'error'
  const failureContext = {
    source: 'failure' as const,
    project_id: currentProject.id,
    error_message: currentProject.error_message || undefined,
  }

  return (
    <div className="ac-page">
      {/* 页头：返回 · 标题 · mono 元信息 */}
      <header>
        <button className="ac-back" onClick={() => navigate('/')}>
          <Icon.Back /> 项目
        </button>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 24 }}>
          <div style={{ minWidth: 0 }}>
            <h1 className="ac-title">{currentProject.name}</h1>
            <div className="ac-meta">
              {isVisual ? <span>{'智能制作'}</span> : isCompleted ? (
                <>
                  <span><span className="ac-mono">{clips.length}</span> 切片</span>
                  <span className="dot" />
                  <span><span className="ac-mono">{collections.length}</span> 合集</span>
                  {totalClipSec > 0 && (
                    <>
                      <span className="dot" />
                      <span>共 <span className="ac-mono">{fmtDuration(totalClipSec)}</span></span>
                    </>
                  )}
                </>
              ) : (
                <span>{currentProject.status === 'pending' ? '等待处理' : isFailed ? '处理失败' : '处理中'}</span>
              )}
              {currentProject.created_at && (
                <>
                  <span className="dot" />
                  <span>{dayjs(currentProject.created_at).fromNow()}</span>
                </>
              )}
            </div>
          </div>
          {!isVisual && currentProject.status === 'pending' && (
            <Btn variant="cta" onClick={handleStartProcessing} loading={statusLoading}>开始处理</Btn>
          )}
          {!isVisual && isFailed && (
            <div style={{ display: 'flex', gap: 8, flex: '0 0 auto' }}>
              <Btn onClick={() => setFeedbackOpen(true)}>反馈问题</Btn>
              <Btn variant="cta" onClick={handleRetryProcessing} loading={statusLoading}>重试</Btn>
            </div>
          )}
        </div>
      </header>

      {isCompleted || isVisual ? (
        <StudioResults key={currentProject.id} project={currentProject} onCreateCollection={() => setShowCreateCollection(true)} onReload={loadProject}>
          {sortedCollections.map(collection => <CollectionCard key={collection.id} collection={collection} clips={clips}
            onView={handleViewCollection}
            onEdit={() => createDraft(collection.clip_ids, collection.collection_title)}
            onUpdate={(collectionId, updates) => updateCollection(currentProject.id, collectionId, updates)}
            onGenerateVideo={async collectionId => { const c = collections.find(x => x.id === collectionId); if(c) await generateAndDownloadCollectionVideo(currentProject.id, collectionId, c.collection_title) }}
            onDelete={handleDeleteCollection} />)}
          {getSortedClips().map(clip => <ClipCard key={clip.id} clip={clip} projectId={currentProject.id}
            onEdit={() => createDraft([clip.id], clip.generated_title || clip.title || '新成片')}
            videoUrl={projectApi.getClipVideoUrl(currentProject.id, clip.id, clip.title || clip.generated_title)}
            onDownload={clipId => projectApi.downloadVideo(currentProject.id, clipId)}
            onClipUpdate={(clipId, updates) => setCurrentProject({...currentProject, clips: clips.map(c => c.id === clipId ? {...c, ...updates} : c)})} />)}
        </StudioResults>
      ) : isFailed ? (
        <div className="ac-empty" style={{ marginTop: 32 }}>
          <b>这次处理没有成功</b>
          {currentProject.error_message ? (
            <span className="ac-mono" style={{ display: 'block', marginTop: 6, color: 'var(--ac-muted)', wordBreak: 'break-all' }}>
              {currentProject.error_message}
            </span>
          ) : (
            '可以直接重试；如果反复失败，点「反馈问题」，运行环境与错误会自动附上。'
          )}
        </div>
      ) : (
        <div style={{ marginTop: 32 }}>
          <ProjectTaskManager projectId={currentProject.id} projectName={currentProject.name} />
          <div className="ac-empty" style={{ marginTop: 24 }}>
            <b>还在处理中</b>
            完成后这里会出现切片与合集。
          </div>
        </div>
      )}

      <FeedbackDialog open={feedbackOpen} onClose={() => setFeedbackOpen(false)} context={failureContext} />

      <CreateCollectionModal
        visible={showCreateCollection}
        clips={clips}
        onCancel={() => setShowCreateCollection(false)}
        onCreate={handleCreateCollection}
      />

      <CollectionPreviewModal
        visible={showCollectionDetail}
        collection={selectedCollection}
        clips={clips}
        projectId={currentProject.id}
        onClose={() => {
          setShowCollectionDetail(false)
          setSelectedCollection(null)
        }}
        onUpdateCollection={(collectionId, updates) => updateCollection(currentProject.id, collectionId, updates)}
        onRemoveClip={handleRemoveClipFromCollection}
        onReorderClips={handleReorderCollectionClips}
        onDelete={handleDeleteCollection}
        onAddClip={handleAddClipToCollection}
      />
    </div>
  )
}

export default ProjectDetailPage

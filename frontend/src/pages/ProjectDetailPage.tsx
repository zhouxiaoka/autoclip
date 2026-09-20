import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { message } from 'antd'
import { useTranslation } from 'react-i18next'
import dayjs from 'dayjs'
import { useProjectStore, Clip, Collection } from '../store/useProjectStore'
import { projectApi } from '../services/api'
import ClipCard from '../components/ClipCard'
import CollectionCard from '../components/CollectionCard'
import CollectionPreviewModal from '../components/CollectionPreviewModal'
import CreateCollectionModal from '../components/CreateCollectionModal'
import { useCollectionVideoDownload } from '../hooks/useCollectionVideoDownload'
import { ProjectTaskManager } from '../components/ProjectTaskManager'
import FeedbackDialog from '../components/FeedbackDialog'
import { Btn, Icon, Section, Segmented, parseTimecode, fmtDuration } from '../ui'

const ProjectDetailPage: React.FC = () => {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const {
    currentProject,
    loading,
    error,
    setCurrentProject,
    upsertProject,
    updateCollection,
    addCollection,
    deleteCollection,
    removeClipFromCollection,
    reorderCollectionClips,
    addClipToCollection
  } = useProjectStore()

  const [statusLoading, setStatusLoading] = useState(false)
  const [showCreateCollection, setShowCreateCollection] = useState(false)
  const [feedbackOpen, setFeedbackOpen] = useState(false)
  const [sortBy, setSortBy] = useState<'time' | 'score'>('score')
  const [showCollectionDetail, setShowCollectionDetail] = useState(false)
  const [selectedCollection, setSelectedCollection] = useState<Collection | null>(null)
  const { generateAndDownloadCollectionVideo } = useCollectionVideoDownload()

  useEffect(() => {
    if (!id) return
    loadProject()
    loadProcessingStatus()
  }, [id])

  const loadProject = async () => {
    if (!id) return
    try {
      const project = await projectApi.getProject(id)
      if (project.status === 'completed') {
        try {
          const [clips, collections] = await Promise.all([
            projectApi.getClips(id),
            projectApi.getCollections(id)
          ])
          const projectWithData = { ...project, clips: clips || [], collections: collections || [] }
          setCurrentProject(projectWithData)
          // 同步更新项目列表，避免页面与列表状态漂移
          upsertProject(projectWithData)
        } catch (err) {
          console.error('Failed to load clips/collections:', err)
          setCurrentProject(project)
        }
      } else {
        setCurrentProject(project)
      }
    } catch (err) {
      console.error('Failed to load project:', err)
      message.error(t('projectDetail.loadProjectFailed'))
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
      message.success(t('projectDetail.startSuccess'))
      loadProcessingStatus()
    } catch (err) {
      console.error('Failed to start processing:', err)
      message.error(t('projectDetail.startFailed'))
    }
  }

  const handleRetryProcessing = async () => {
    if (!id) return
    setStatusLoading(true)
    try {
      await projectApi.retryProcessing(id)
      message.success(t('projectDetail.retrySuccess'))
      loadProcessingStatus()
      await loadProject()
    } catch (err) {
      console.error('Failed to retry processing:', err)
      message.error(t('projectDetail.retryFailed'))
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
      message.success(t('projectDetail.collectionCreated'))
    } catch (err) {
      console.error('Failed to create collection:', err)
      message.error(t('projectDetail.createCollectionFailed'))
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
      message.success(t('projectDetail.clipRemoved'))
    } catch (err) {
      console.error('Failed to remove clip from collection:', err)
      message.error(t('projectDetail.removeClipFailed'))
    }
  }

  const handleDeleteCollection = async (collectionId: string) => {
    if (!id) return
    try {
      await deleteCollection(id, collectionId)
      setShowCollectionDetail(false)
      setSelectedCollection(null)
      message.success(t('projectDetail.collectionDeleted'))
    } catch (err) {
      console.error('Failed to delete collection:', err)
      message.error(t('projectDetail.deleteCollectionFailed'))
    }
  }

  const handleReorderCollectionClips = async (collectionId: string, newClipIds: string[]): Promise<void> => {
    if (!id) return
    try {
      await reorderCollectionClips(id, collectionId, newClipIds)
      message.success(t('projectDetail.collectionOrderUpdated'))
    } catch (err) {
      console.error('Failed to reorder collection clips:', err)
      message.error(t('projectDetail.reorderFailed'))
    }
  }

  const handleAddClipToCollection = async (collectionId: string, clipIds: string[]): Promise<void> => {
    if (!id) return
    try {
      await addClipToCollection(id, collectionId, clipIds)
      message.success(t('projectDetail.clipAdded'))
    } catch (err) {
      console.error('Failed to add clip to collection:', err)
      message.error(t('projectDetail.addClipFailed'))
    }
  }

  const getSortedClips = () => {
    if (!currentProject?.clips) return []
    const clips = [...currentProject.clips]
    if (sortBy === 'score') return clips.sort((a, b) => b.final_score - a.final_score)
    return clips.sort((a, b) => parseTimecode(a.start_time) - parseTimecode(b.start_time))
  }

  if (loading) {
    return (
      <div className="ac-page" style={{ display: 'flex', justifyContent: 'center', paddingTop: 120 }}>
        <span className="ac-btn ac-btn--text" style={{ color: 'var(--ac-muted)' }}><span className="spin" /> {t('common.loading')}</span>
      </div>
    )
  }

  if (error || !currentProject) {
    return (
      <div className="ac-page">
        <div className="ac-empty">
          <b>{t('projectDetail.loadFailed')}</b>
          {error || t('projectDetail.projectNotFound')}
          <div style={{ marginTop: 16 }}>
            <Btn size="sm" onClick={() => navigate('/')}>{t('projectDetail.backHome')}</Btn>
          </div>
        </div>
      </div>
    )
  }

  const clips = currentProject.clips || []
  const collections = currentProject.collections || []
  const totalClipSec = clips.reduce((s, c) => s + Math.max(0, parseTimecode(c.end_time) - parseTimecode(c.start_time)), 0)
  const sortedCollections = [...collections].sort((a, b) => {
    const ta = a.created_at ? new Date(a.created_at).getTime() : 0
    const tb = b.created_at ? new Date(b.created_at).getTime() : 0
    return tb - ta
  })
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
          <Icon.Back /> {t('projectDetail.backToProjects')}
        </button>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 24 }}>
          <div style={{ minWidth: 0 }}>
            <h1 className="ac-title">{currentProject.name}</h1>
            <div className="ac-meta">
              {isCompleted ? (
                <>
                  <span><span className="ac-mono">{clips.length}</span> {t('projectDetail.clips')}</span>
                  <span className="dot" />
                  <span><span className="ac-mono">{collections.length}</span> {t('projectDetail.collections')}</span>
                  {totalClipSec > 0 && (
                    <>
                      <span className="dot" />
                      <span>{t('projectDetail.total')} <span className="ac-mono">{fmtDuration(totalClipSec)}</span></span>
                    </>
                  )}
                </>
              ) : (
                <span>{currentProject.status === 'pending' ? t('projectDetail.pending') : isFailed ? t('projectDetail.failed') : t('projectDetail.processing')}</span>
              )}
              {currentProject.created_at && (
                <>
                  <span className="dot" />
                  <span>{dayjs(currentProject.created_at).fromNow()}</span>
                </>
              )}
            </div>
          </div>
          {currentProject.status === 'pending' && (
            <Btn variant="cta" onClick={handleStartProcessing} loading={statusLoading}>{t('projectDetail.startProcessing')}</Btn>
          )}
          {isFailed && (
            <div style={{ display: 'flex', gap: 8, flex: '0 0 auto' }}>
              <Btn onClick={() => setFeedbackOpen(true)}>{t('projectDetail.feedback')}</Btn>
              <Btn variant="cta" onClick={handleRetryProcessing} loading={statusLoading}>{t('projectDetail.retry')}</Btn>
            </div>
          )}
        </div>
      </header>

      {isCompleted ? (
        <>
          {/* 合集 */}
          <Section
            title={t('projectDetail.collectionsSectionTitle')}
            count={collections.length}
            description={collections.length > 0 ? t('projectDetail.collectionsSectionDesc') : t('projectDetail.collectionsSectionDescEmpty')}
            right={
              <Btn size="sm" onClick={() => setShowCreateCollection(true)}>
                <Icon.Plus size={13} /> {t('projectDetail.newCollection')}
              </Btn>
            }
          >
            {collections.length > 0 ? (
              <div className="ac-hscroll">
                {sortedCollections.map((collection) => (
                  <CollectionCard
                    key={collection.id}
                    collection={collection}
                    clips={clips}
                    onView={handleViewCollection}
                    onUpdate={(collectionId, updates) => updateCollection(currentProject.id, collectionId, updates)}
                    onGenerateVideo={async (collectionId) => {
                      const c = collections.find((x) => x.id === collectionId)
                      if (c) await generateAndDownloadCollectionVideo(currentProject.id, collectionId, c.collection_title)
                    }}
                    onDelete={handleDeleteCollection}
                  />
                ))}
              </div>
            ) : (
              <div className="ac-empty">
                <b>{t('projectDetail.noCollectionsTitle')}</b>
                {t('projectDetail.noCollectionsDesc')}
              </div>
            )}
          </Section>

          {/* 切片 */}
          <Section
            title={t('projectDetail.clipsSectionTitle')}
            count={clips.length}
            right={
              <Segmented
                size="sm"
                ariaLabel={t('projectDetail.sortBy')}
                value={sortBy}
                onChange={setSortBy}
                options={[{ value: 'score', label: t('projectDetail.sortByScore') }, { value: 'time', label: t('projectDetail.sortByTime') }]}
              />
            }
          >
            {clips.length > 0 ? (
              <div className="ac-grid-3">
                {getSortedClips().map((clip) => (
                  <ClipCard
                    key={clip.id}
                    clip={clip}
                    projectId={currentProject.id}
                    videoUrl={projectApi.getClipVideoUrl(currentProject.id, clip.id, clip.title || clip.generated_title)}
                    onDownload={(clipId) => projectApi.downloadVideo(currentProject.id, clipId)}
                    onClipUpdate={(clipId: string, updates: Partial<Clip>) => {
                      const updatedProject = {
                        ...currentProject,
                        clips: clips.map((c: Clip) => (c.id === clipId ? { ...c, ...updates } : c))
                      }
                      setCurrentProject(updatedProject)
                    }}
                  />
                ))}
              </div>
            ) : (
              <div className="ac-empty">
                <b>{t('projectDetail.noClipsTitle')}</b>
                {t('projectDetail.noClipsDesc')}
                <div style={{ marginTop: 12 }}>
                  <Btn variant="text" size="sm" onClick={() => setFeedbackOpen(true)}>{t('projectDetail.tellUsFeedback')}</Btn>
                </div>
              </div>
            )}
          </Section>
        </>
      ) : isFailed ? (
        <div className="ac-empty" style={{ marginTop: 32 }}>
          <b>{t('projectDetail.processingFailedTitle')}</b>
          {currentProject.error_message ? (
            <span className="ac-mono" style={{ display: 'block', marginTop: 6, color: 'var(--ac-muted)', wordBreak: 'break-all' }}>
              {currentProject.error_message}
            </span>
          ) : (
            t('projectDetail.processingFailedDesc')
          )}
        </div>
      ) : (
        <div style={{ marginTop: 32 }}>
          <ProjectTaskManager projectId={currentProject.id} projectName={currentProject.name} />
          <div className="ac-empty" style={{ marginTop: 24 }}>
            <b>{t('projectDetail.stillProcessingTitle')}</b>
            {t('projectDetail.stillProcessingDesc')}
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

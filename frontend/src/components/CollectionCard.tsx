import { t } from '../i18n'
import { useTranslation } from 'react-i18next'
import React, { useMemo, useState } from 'react'
import { Collection, Clip } from '../store/useProjectStore'
import EditableCollectionTitle from './EditableCollectionTitle'
import { Btn, Icon, parseTimecode, fmtDuration } from '../ui'

interface CollectionCardProps {
  onEdit?: () => void
  collection: Collection
  clips: Clip[]
  onView: (collection: Collection) => void
  onGenerateVideo?: (collectionId: string) => void
  onDelete?: (collectionId: string) => void
  onUpdate?: (collectionId: string, updates: Partial<Collection>) => void
}

// Calm Premium collection card — same anatomy as ClipCard (see DESIGN.md)
const CollectionCard: React.FC<CollectionCardProps> = ({ collection, clips, onView, onGenerateVideo, onUpdate, onEdit }) => {
  useTranslation()
  const safeClips = Array.isArray(clips) ? clips : []
  const safeClipIds = Array.isArray(collection.clip_ids) ? collection.clip_ids : []
  const collectionClips = safeClipIds
    .map((id) => safeClips.find((c) => c.id === id))
    .filter(Boolean) as Clip[]

  const totalDuration = collectionClips.reduce(
    (t, c) => t + Math.max(0, parseTimecode(c.end_time) - parseTimecode(c.start_time)),
    0
  )

  const thumbnailUrl = useMemo(() => {
    if (!collection.project_id) return ''
    const ts = encodeURIComponent(collection.created_at || '')
    return `/api/v1/projects/${collection.project_id}/collections/${collection.id}/thumbnail?t=${ts}`
  }, [collection.project_id, collection.id, collection.created_at])

  const [imgError, setImgError] = useState(false)
  const hasThumb = !imgError && !!collection.thumbnail_path

  return (
    <article className="ac-card">
      <div className="ac-card-thumb" onClick={onEdit || (() => onView(collection))} tabIndex={0} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); (onEdit || (() => onView(collection)))() } }} role="button" aria-label={t(onEdit ? "预览与修改" : "预览合集")}>
        {hasThumb && (
          <img src={thumbnailUrl} alt="" onError={() => setImgError(true)} draggable={false} />
        )}
        <div className="play"><span><Icon.Play size={18} /></span></div>
        <span className="ac-tag ac-tag--tl ac-tag--sans">
          {collection.collection_type === 'ai_recommended' ? t("AI 推荐") : t("手动")}
        </span>
        <span className="ac-tag ac-tag--bl">{t("切片数量", { count: collectionClips.length })}</span>
        <span className="ac-tag ac-tag--br">{fmtDuration(totalDuration)}</span>
      </div>

      <div className="ac-card-body">
        <div className="ac-card-title">
          <EditableCollectionTitle
            title={collection.collection_title}
            collectionId={collection.id}
            onTitleUpdate={(t) => onUpdate?.(collection.id, { collection_title: t })}
            style={{ fontSize: 'inherit', fontWeight: 'inherit', lineHeight: 'inherit', color: 'inherit', width: '100%' }}
          />
        </div>
        <div className="ac-card-desc" title={collection.collection_summary || ''}>
          {collection.collection_summary || ''}
        </div>
        <div className="ac-card-foot">
          <span className="meta">{t("切片数量", { count: collectionClips.length })} · {fmtDuration(totalDuration)}</span>
          <div className="ac-card-actions">
            <Btn variant="text" onClick={onEdit || (() => onView(collection))}>{t(onEdit ? "预览与修改" : "预览")}</Btn>
            {onGenerateVideo && <Btn variant="text" onClick={() => onGenerateVideo(collection.id)}>{t("下载")}</Btn>}
            <Btn variant="text" onClick={() => onView(collection)}>{t("管理合集")}</Btn>
          </div>
        </div>
      </div>
    </article>
  )
}

export default CollectionCard

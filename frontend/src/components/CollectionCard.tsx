import React, { useMemo, useState } from 'react'
import { Card, Button, Tooltip, message } from 'antd'
import { PlayCircleOutlined, EditOutlined, DownloadOutlined } from '@ant-design/icons'
import { Collection, Clip } from '../store/useProjectStore'
import EditableCollectionTitle from './EditableCollectionTitle'
import './CollectionCard.css'

interface CollectionCardProps {
  collection: Collection
  clips: Clip[]
  onView: (collection: Collection) => void
  onGenerateVideo?: (collectionId: string) => void
  onDelete?: (collectionId: string) => void
  onUpdate?: (collectionId: string, updates: Partial<Collection>) => void
}

const CollectionCard: React.FC<CollectionCardProps> = ({ 
  collection, 
  clips,
  onView,
  onGenerateVideo,
  onUpdate
}) => {
  // 按照collection.clip_ids的顺序排列clips
  const safeClips = Array.isArray(clips) ? clips : []
  const safeClipIds = Array.isArray(collection.clip_ids) ? collection.clip_ids : []
  const collectionClips = safeClipIds.map(clipId => safeClips.find(clip => clip.id === clipId)).filter(Boolean) as Clip[]
  
  const totalDuration = collectionClips.reduce((total, clip) => {
    const start = clip.start_time.split(':')
    const end = clip.end_time.split(':')
    const startSeconds = parseInt(start[0]) * 3600 + parseInt(start[1]) * 60 + parseFloat(start[2].replace(',', '.'))
    const endSeconds = parseInt(end[0]) * 3600 + parseInt(end[1]) * 60 + parseFloat(end[2].replace(',', '.'))
    return total + (endSeconds - startSeconds)
  }, 0)

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${String(secs).padStart(2, '0')}`
  }

  const thumbnailUrl = useMemo(() => {
    if (!collection.project_id) return ''
    const ts = encodeURIComponent(collection.created_at || '')
    return `/api/v1/projects/${collection.project_id}/collections/${collection.id}/thumbnail?t=${ts}`
  }, [collection.project_id, collection.id, collection.created_at])

  const [imgError, setImgError] = useState(false)

  return (
    <Card
      className="collection-card"
      hoverable
      style={{ 
        width: '320px',
        height: '380px',
        borderRadius: '16px',
        border: '1px solid var(--ac-line)',
        background: 'var(--ac-card)',
        overflow: 'hidden',
        cursor: 'pointer',
        flexShrink: 0
      }}
      styles={{
        body: {
          padding: 0,
        },
      }}
      cover={
        <div 
          style={{ 
            height: '200px', 
            background: imgError || !collection.thumbnail_path
              ? 'var(--ac-thumb)'
              : 'transparent',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            position: 'relative',
            cursor: 'pointer',
            overflow: 'hidden'
          }}
          onClick={() => onView(collection)}
        >
          {!imgError && collection.thumbnail_path && (
            <img
              src={thumbnailUrl}
              alt={collection.collection_title}
              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              onError={() => setImgError(true)}
              draggable={false}
            />
          )}
          <div 
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: 'rgba(0,0,0,0.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              opacity: 0,
              transition: 'opacity 0.3s ease'
            }}
            className="video-overlay"
          >
            <PlayCircleOutlined style={{ fontSize: '40px', color: 'white' }} />
          </div>
          
          {/* 右上角合集类型标签 */}
          <div 
            style={{
              position: 'absolute',
              top: '12px',
              right: '12px',
              background: 'rgba(0,0,0,0.55)',
              backdropFilter: 'blur(6px)',
              color: 'rgba(255,255,255,0.95)',
              padding: '4px 9px',
              borderRadius: '999px',
              fontSize: '12px',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            {collection.collection_type === 'ai_recommended' ? 'AI pick' : 'Manual'}
          </div>
          
          {/* 左下角片段数量 */}
          <div 
            style={{
              position: 'absolute',
              bottom: '12px',
              left: '12px',
              background: 'rgba(0,0,0,0.7)',
              color: 'white',
              padding: '4px 8px',
              borderRadius: '8px',
              fontSize: '12px',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            {collectionClips.length} clips
          </div>
          
          {/* 右下角总时长 */}
          <div 
            style={{
              position: 'absolute',
              bottom: '12px',
              right: '12px',
              background: 'rgba(0,0,0,0.7)',
              color: 'white',
              padding: '4px 8px',
              borderRadius: '8px',
              fontSize: '12px',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            {formatDuration(totalDuration)}
          </div>
        </div>
      }
    >
      <div style={{ 
        padding: '16px', 
        height: '180px', 
        display: 'flex', 
        flexDirection: 'column',
        justifyContent: 'space-between'
      }}>
        {/* 内容区域 - 固定高度 */}
        <div style={{ 
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0 // 允许flex子项收缩
        }}>
          {/* 标题区域 - 固定高度 */}
          <div style={{ 
            height: '44px',
            marginBottom: '8px',
            display: 'flex',
            alignItems: 'flex-start'
          }}>
            <EditableCollectionTitle
              title={collection.collection_title}
              collectionId={collection.id}
              onTitleUpdate={(newTitle) => {
                // 更新合集标题
                if (onUpdate) {
                  onUpdate(collection.id, { collection_title: newTitle })
                }
              }}
              style={{ 
                fontSize: '16px',
                fontWeight: 600,
                lineHeight: '1.4',
                color: 'var(--ac-ink)',
                width: '100%',
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
                textOverflow: 'ellipsis'
              }}
            />
          </div>
          
          {/* 合集描述 - 固定高度 */}
          <div style={{ 
            height: '58px',
            marginBottom: '12px',
            display: 'flex',
            alignItems: 'flex-start'
          }}>
            <Tooltip 
              title={collection.collection_summary || 'No description'} 
              placement="top" 
              overlayStyle={{ maxWidth: '300px' }}
              mouseEnterDelay={0.5}
            >
              <div 
                style={{ 
                  fontSize: '13px',
                  display: '-webkit-box',
                  WebkitLineClamp: 3,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                  lineHeight: '1.5',
                  color: 'var(--ac-sub)',
                  cursor: 'pointer',
                  wordBreak: 'break-word',
                  textOverflow: 'ellipsis',
                  width: '100%'
                }}
              >
                {collection.collection_summary || 'No description'}
              </div>
            </Tooltip>
          </div>
        </div>
        
        {/* 操作按钮 - 固定在底部 */}
        <div style={{ 
          display: 'flex', 
          gap: '8px',
          height: '28px',
          alignItems: 'center',
          marginTop: 'auto'
        }}>
          <Button 
            type="text" 
            size="small"
            icon={<PlayCircleOutlined />}
            onClick={() => onView(collection)}
            style={{
              color: 'var(--ac-ink)',
              border: '1px solid var(--ac-line)',
              borderRadius: '6px',
              fontSize: '12px',
              height: '28px',
              padding: '0 12px',
              background: 'transparent'
            }}
          >
            Play
          </Button>
          {onGenerateVideo && (
            <Button 
              type="text" 
              size="small"
              icon={<DownloadOutlined />}
              onClick={() => onGenerateVideo(collection.id)}
              style={{
                color: 'var(--ac-sub)',
                border: '1px solid var(--ac-line)',
                borderRadius: '6px',
                fontSize: '12px',
                height: '28px',
                padding: '0 12px',
                background: 'transparent'
              }}
            >
              Download
            </Button>
          )}
          <Button 
            type="text" 
            size="small"
            icon={<EditOutlined />}
            onClick={() => message.info('Coming soon', 3)}
            style={{
              color: 'var(--ac-sub)',
              border: '1px solid var(--ac-line)',
              borderRadius: '6px',
              fontSize: '12px',
              height: '28px',
              padding: '0 12px',
              background: 'transparent'
            }}
          >
            Upload
          </Button>
        </div>
      </div>
    </Card>
  )
}

export default CollectionCard
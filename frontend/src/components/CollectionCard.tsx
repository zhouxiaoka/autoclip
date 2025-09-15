import React from 'react'
import { Card, Button, Tooltip } from 'antd'
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
  const collectionClips = collection.clip_ids.map(clipId => clips.find(clip => clip.id === clipId)).filter(Boolean) as Clip[]
  
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

  return (
    <Card
      className="collection-card"
      hoverable
      style={{ 
        width: '320px',
        height: '380px',
        flexShrink: 0,
        cursor: 'pointer',
        borderRadius: '16px',
        border: '1px solid #303030',
        background: 'linear-gradient(135deg, #1f1f1f 0%, #2a2a2a 100%)',
        position: 'relative',
        overflow: 'hidden'
      }}
      styles={{
        body: {
          padding: 0,
          height: '100%'
        }
      }}
      onClick={() => onView(collection)}
    >
      <div style={{ 
        height: '100%', 
        display: 'flex', 
        flexDirection: 'column',
        justifyContent: 'space-between'
      }}>
        {/* 封面区域 */}
        <div style={{
          height: '200px',
          background: collection.thumbnail_path 
            ? `url(http://localhost:8000/api/v1/projects/${collection.project_id}/collections/${collection.id}/thumbnail)`
            : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat',
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          overflow: 'hidden'
        }}>
          {/* 播放覆盖层 */}
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
              background: collection.collection_type === 'ai_recommended' 
                ? 'linear-gradient(45deg, #1890ff, #36cfc9)' 
                : 'linear-gradient(45deg, #722ed1, #eb2f96)',
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
            {collection.collection_type === 'ai_recommended' ? 'AI推荐' : '手动创建'}
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
            {collectionClips.length} 个片段
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
        
        {/* 内容区域 - 固定高度 */}
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
                  color: '#ffffff',
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
                title={collection.collection_summary || '暂无描述'} 
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
                    color: '#b0b0b0',
                    cursor: 'pointer',
                    wordBreak: 'break-word',
                    textOverflow: 'ellipsis',
                    width: '100%'
                  }}
                >
                  {collection.collection_summary || '暂无描述'}
                </div>
              </Tooltip>
            </div>
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
                color: '#4facfe',
                border: '1px solid rgba(79, 172, 254, 0.3)',
                borderRadius: '6px',
                fontSize: '12px',
                height: '28px',
                padding: '0 12px',
                background: 'rgba(79, 172, 254, 0.1)'
              }}
            >
              播放
            </Button>
            {onGenerateVideo && (
              <Button
                type="text"
                size="small"
                icon={<DownloadOutlined />}
                onClick={() => onGenerateVideo(collection.id)}
                style={{
                  color: '#52c41a',
                  border: '1px solid rgba(82, 196, 26, 0.3)',
                  borderRadius: '6px',
                  fontSize: '12px',
                  height: '28px',
                  padding: '0 12px',
                  background: 'rgba(82, 196, 26, 0.1)'
                }}
              >
                下载
              </Button>
            )}
            <Button
              type="text"
              size="small"
              icon={<EditOutlined />}
              onClick={() => onView(collection)}
              style={{
                color: '#ff7875',
                border: '1px solid rgba(255, 120, 117, 0.3)',
                borderRadius: '6px',
                fontSize: '12px',
                height: '28px',
                padding: '0 12px',
                background: 'rgba(255, 120, 117, 0.1)'
              }}
            >
              投稿
            </Button>
          </div>
      </div>
    </Card>
  )
}

export default CollectionCard
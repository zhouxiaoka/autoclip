import React, { useState } from 'react'
import { Card, Typography, Button, Popconfirm, Tooltip } from 'antd'
import { DeleteOutlined, PlayCircleOutlined } from '@ant-design/icons'
import { Collection, Clip } from '../store/useProjectStore'
import EditableCollectionTitle from './EditableCollectionTitle'
import './CollectionCard.css'

const { Text, Title } = Typography

interface CollectionCardMiniProps {
  collection: Collection
  clips: Clip[]
  onView: (collection: Collection) => void
  onGenerateVideo?: (collectionId: string) => void
  onDelete?: (collectionId: string) => void
  onUpdate?: (collectionId: string, updates: Partial<Collection>) => void
}

const CollectionCardMini: React.FC<CollectionCardMiniProps> = ({ 
  collection, 
  clips,
  onView,
  onGenerateVideo,
  onDelete,
  onUpdate
}) => {
  const [isHovered, setIsHovered] = useState(false)
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
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
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
          <div 
            style={{
              position: 'absolute',
              top: '8px',
              right: '8px',
              background: 'rgba(0,0,0,0.8)',
              color: 'white',
              padding: '4px 8px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: '500'
            }}
          >
            {collectionClips.length} 个片段
          </div>
        </div>
        
        {/* 内容区域 - 固定高度 */}
        <div style={{ 
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0,
          padding: '16px'
        }}>
          {/* 标题和标签区域 - 固定高度 */}
          <div style={{ 
            height: '56px',
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'flex-start',
            marginBottom: '12px'
          }}>
            <div style={{ 
              flex: 1,
              paddingRight: '8px',
              height: '100%',
              display: 'flex',
              alignItems: 'flex-start'
            }}>
              <Tooltip 
                title={collection.collection_title} 
                placement="top" 
                overlayStyle={{ maxWidth: '200px' }}
                mouseEnterDelay={0.5}
              >
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
                    fontSize: '15px',
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
              </Tooltip>
            </div>
            <span
              style={{ 
                fontSize: '10px', 
                margin: 0,
                borderRadius: '6px',
                border: 'none',
                background: collection.collection_type === 'ai_recommended' 
                  ? 'linear-gradient(45deg, #1890ff, #36cfc9)' 
                  : 'linear-gradient(45deg, #722ed1, #eb2f96)',
                color: 'white',
                padding: '2px 6px',
                fontWeight: 500,
                whiteSpace: 'nowrap',
                flexShrink: 0
              }}
            >
              {collection.collection_type === 'ai_recommended' ? 'AI推荐' : '手动创建'}
            </span>
          </div>
          
          {/* 描述区域 - 固定高度 */}
          <div style={{ 
            height: '48px',
            display: 'flex',
            alignItems: 'flex-start',
            marginBottom: '12px'
          }}>
            <Tooltip 
              title={collection.collection_summary || '暂无描述'} 
              placement="top" 
              overlayStyle={{ maxWidth: '250px' }}
              mouseEnterDelay={0.5}
            >
              <Text 
                type="secondary" 
                style={{ 
                  fontSize: '12px',
                  color: '#b0b0b0',
                  display: '-webkit-box',
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                  lineHeight: '1.4',
                  width: '100%',
                  cursor: 'pointer'
                }}
              >
                {collection.collection_summary || '暂无描述'}
              </Text>
            </Tooltip>
          </div>
        </div>
        
        {/* 底部区域 */}
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ 
              fontSize: '11px', 
              color: '#888',
              background: 'rgba(255,255,255,0.1)',
              padding: '2px 6px',
              borderRadius: '4px'
            }}>
              {collectionClips.length} 个片段
            </span>
            <span style={{ 
              fontSize: '11px', 
              color: '#888',
              background: 'rgba(255,255,255,0.1)',
              padding: '2px 6px',
              borderRadius: '4px'
            }}>
              {formatDuration(totalDuration)}
            </span>
          </div>
          
          <div style={{ 
            display: 'flex', 
            gap: '4px',
            opacity: isHovered ? 1 : 0,
            transition: 'opacity 0.2s ease'
          }}>
            {onGenerateVideo && (
              <Button 
                type="text" 
                size="small"
                onClick={(e) => {
                  e.stopPropagation()
                  onGenerateVideo(collection.id)
                }}
                style={{
                  color: '#1890ff',
                  fontSize: '10px',
                  height: '20px',
                  padding: '0 6px',
                  background: 'rgba(24, 144, 255, 0.1)',
                  border: '1px solid rgba(24, 144, 255, 0.3)',
                  borderRadius: '4px'
                }}
              >
                下载
              </Button>
            )}
            
            {onDelete && (
              <Popconfirm
                title="确定要删除这个合集吗？"
                onConfirm={(e) => {
                  e?.stopPropagation()
                  onDelete(collection.id)
                }}
                onCancel={(e) => e?.stopPropagation()}
                okText="确定"
                cancelText="取消"
              >
                <Button 
                  type="text" 
                  size="small"
                  icon={<DeleteOutlined />}
                  onClick={(e) => e.stopPropagation()}
                  style={{
                    color: '#ff4d4f',
                    fontSize: '10px',
                    height: '20px',
                    padding: '0 6px',
                    background: 'rgba(255, 77, 79, 0.1)',
                    border: '1px solid rgba(255, 77, 79, 0.3)',
                    borderRadius: '4px'
                  }}
                />
              </Popconfirm>
            )}
          </div>
        </div>
      </div>
    </Card>
  )
}

export default CollectionCardMini
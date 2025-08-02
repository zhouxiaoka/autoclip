import React, { useState } from 'react'
import { Card, Typography, Button, Popconfirm } from 'antd'
import { DeleteOutlined } from '@ant-design/icons'
import { Collection, Clip } from '../store/useProjectStore'

const { Text, Title } = Typography

interface CollectionCardMiniProps {
  collection: Collection
  clips: Clip[]
  onView: (collection: Collection) => void
  onGenerateVideo?: (collectionId: string) => void
  onDelete?: (collectionId: string) => void
}

const CollectionCardMini: React.FC<CollectionCardMiniProps> = ({ 
  collection, 
  clips,
  onView,
  onGenerateVideo,
  onDelete
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
      hoverable
      style={{ 
        width: '300px',
        height: '140px',
        flexShrink: 0,
        cursor: 'pointer',
        borderRadius: '12px',
        border: '1px solid #303030',
        background: 'linear-gradient(135deg, #1f1f1f 0%, #2a2a2a 100%)',
        position: 'relative'
      }}
      bodyStyle={{ 
        padding: '16px',
        height: '100%'
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
        {/* 头部区域 */}
        <div>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'flex-start',
            marginBottom: '12px'
          }}>
            <Title 
              level={5} 
              ellipsis={{ rows: 2 }} 
              style={{ 
                margin: 0, 
                fontSize: '15px',
                fontWeight: 600,
                lineHeight: '1.4',
                color: '#ffffff',
                flex: 1,
                paddingRight: '8px'
              }}
            >
              {collection.collection_title}
            </Title>
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
                whiteSpace: 'nowrap'
              }}
            >
              {collection.collection_type === 'ai_recommended' ? 'AI推荐' : '手动创建'}
            </span>
          </div>
          
          <Text 
            type="secondary" 
            style={{ 
              fontSize: '12px',
              color: '#b0b0b0',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              lineHeight: '1.4'
            }}
          >
            {collection.collection_summary || '暂无描述'}
          </Text>
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
                  color: '#52c41a',
                  fontSize: '10px',
                  height: '20px',
                  padding: '0 6px',
                  background: 'rgba(82, 196, 26, 0.1)',
                  border: '1px solid rgba(82, 196, 26, 0.3)',
                  borderRadius: '4px'
                }}
              >
                生成
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
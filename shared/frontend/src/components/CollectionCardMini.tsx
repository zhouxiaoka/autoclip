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

  // 移除评分计算

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
                background: collection.collection_type === 'manual' 
                  ? 'linear-gradient(45deg, #1890ff, #40a9ff)'
                  : 'linear-gradient(45deg, #722ed1, #9254de)',
                color: '#ffffff',
                fontWeight: 600,
                flexShrink: 0,
                display: 'inline-block',
                padding: '2px 8px',
                lineHeight: '1.4',
                boxShadow: collection.collection_type === 'manual'
                  ? '0 2px 4px rgba(24, 144, 255, 0.2)'
                  : '0 2px 4px rgba(114, 46, 209, 0.2)'
              }}
            >
              {collection.collection_type === 'manual' ? '手动创建' : 'AI推荐'}
            </span>
          </div>
          
          {/* 简介 */}
          <Text 
            type="secondary" 
            style={{ 
              fontSize: '12px',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              lineHeight: '1.5',
              color: '#b0b0b0',
              marginBottom: '12px'
            }}
          >
            {collection.collection_summary}
          </Text>
        </div>

        {/* 底部统计信息 */}
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between',
          alignItems: 'center',
          paddingTop: '8px',
          borderTop: '1px solid #404040'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <div style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                background: '#1890ff'
              }} />
              <Text style={{ fontSize: '11px', color: '#8c8c8c' }}>
                {collectionClips.length}个片段
              </Text>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <div style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                background: '#52c41a'
              }} />
              <Text style={{ fontSize: '11px', color: '#8c8c8c' }}>
                {formatDuration(totalDuration)}
              </Text>
            </div>
          </div>
          {onDelete && isHovered && (
            <Popconfirm
              title="确认删除"
              description="确定要删除这个合集吗？此操作不可撤销。"
              onConfirm={(e) => {
                e?.stopPropagation()
                onDelete(collection.id)
              }}
              okText="确认"
              cancelText="取消"
              okType="danger"
            >
              <Button
                type="text"
                size="small"
                icon={<DeleteOutlined />}
                onClick={(e) => e.stopPropagation()}
                style={{
                  color: '#ff4d4f',
                  fontSize: '12px',
                  padding: '2px 6px',
                  height: 'auto'
                }}
              >
                删除
              </Button>
            </Popconfirm>
          )}
        </div>
      </div>
    </Card>
  )
}

export default CollectionCardMini
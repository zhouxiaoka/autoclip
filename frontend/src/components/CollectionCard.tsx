import React, { useState } from 'react'
import { Card, Typography, Button, Space, Input, Tag, List, Modal, Tooltip, Popconfirm } from 'antd'
import { EditOutlined, SaveOutlined, CloseOutlined, PlayCircleOutlined, DragOutlined, DeleteOutlined, DownloadOutlined } from '@ant-design/icons'
import { Collection, Clip } from '../store/useProjectStore'
import { DragDropContext, Droppable, Draggable, DropResult } from 'react-beautiful-dnd'
import EditableCollectionTitle from './EditableCollectionTitle'
import './CollectionCard.css'

const { Text } = Typography
const { TextArea } = Input

interface CollectionCardProps {
  collection: Collection
  clips: Clip[]
  onUpdate: (collectionId: string, updates: Partial<Collection>) => void
  onDownload: (collectionId: string) => void
  onDelete?: (collectionId: string) => void
  onGenerateVideo?: (collectionId: string) => void
  onReorderClips?: (collectionId: string, newClipIds: string[]) => void
}

const CollectionCard: React.FC<CollectionCardProps> = ({ 
  collection, 
  clips,
  onUpdate, 
  onDelete,
  onGenerateVideo,
  onReorderClips
}) => {
  const [editing, setEditing] = useState(false)
  const [editTitle, setEditTitle] = useState(collection.collection_title)
  const [editSummary, setEditSummary] = useState(collection.collection_summary)
  const [showClipList, setShowClipList] = useState(false)
  const [showModal, setShowModal] = useState(false)
  const [isHovered, setIsHovered] = useState(false)

  const handleSave = () => {
    onUpdate(collection.id, {
      collection_title: editTitle,
      collection_summary: editSummary
    })
    setEditing(false)
  }

  const handleCancel = () => {
    setEditTitle(collection.collection_title)
    setEditSummary(collection.collection_summary)
    setEditing(false)
  }

  const handleDragEnd = (result: DropResult) => {
    if (!result.destination || !onReorderClips) return

    const newClipIds = Array.from(collection.clip_ids)
    const [reorderedItem] = newClipIds.splice(result.source.index, 1)
    newClipIds.splice(result.destination.index, 0, reorderedItem)

    onReorderClips(collection.id, newClipIds)
  }

  // 按照collection.clip_ids的顺序排列clips
  const collectionClips = collection.clip_ids.map(clipId => clips.find(clip => clip.id === clipId)).filter(Boolean) as Clip[]
  const totalDuration = collectionClips.reduce((total, clip) => {
    // 简单计算总时长
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
    <>
      <div style={{ position: 'relative', width: '100%' }}>
        {/* 删除按钮 - 只在hover时显示 */}
        {onDelete && isHovered && (
          <div style={{
            position: 'absolute',
            top: '8px',
            right: '8px',
            zIndex: 10
          }}>
            <Popconfirm
              title="确认删除合集"
              description={`确定要删除合集「${collection.collection_title}」吗？此操作不可恢复。`}
              onConfirm={() => onDelete(collection.id)}
              okText="确认删除"
              cancelText="取消"
              okType="danger"
            >
              <Button
                type="text"
                size="small"
                icon={<DeleteOutlined />}
                style={{
                  color: '#ff4d4f',
                  backgroundColor: 'rgba(255, 255, 255, 0.9)',
                  borderRadius: '50%',
                  width: '28px',
                  height: '28px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: 0,
                  minWidth: 'auto',
                  boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
                  border: '1px solid #ff4d4f'
                }}
              />
            </Popconfirm>
          </div>
        )}
        <Card
          className="collection-card"
          hoverable
          style={{ 
            height: '380px', 
            width: '100%',
            borderRadius: '16px',
            border: '1px solid #303030',
            background: 'linear-gradient(135deg, #1f1f1f 0%, #2a2a2a 100%)',
            overflow: 'hidden',
            cursor: 'pointer'
          }}
          styles={{
            body: {
              padding: 0,
            },
          }}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
          cover={
            <div 
              style={{ 
                height: '200px', 
                background: collection.thumbnail_path 
                  ? `url(http://localhost:8000/api/v1/projects/${collection.project_id}/collections/${collection.id}/thumbnail)`
                  : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                backgroundSize: 'cover',
                backgroundPosition: 'center',
                backgroundRepeat: 'no-repeat',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                position: 'relative',
                cursor: 'pointer',
                overflow: 'hidden'
              }}
              onClick={() => setShowModal(true)}
            >
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
          }
      >
        <div style={{ 
          padding: '16px', 
          height: '180px', 
          display: 'flex', 
          flexDirection: 'column',
          justifyContent: 'space-between'
        }}>
          {editing ? (
            <Space direction="vertical" style={{ width: '100%' }} size="small">
              <Input
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                placeholder="输入合集标题"
                maxLength={50}
              />
              <TextArea
                value={editSummary}
                onChange={(e) => setEditSummary(e.target.value)}
                placeholder="输入合集简介"
                rows={3}
                maxLength={200}
              />
              <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
                <Button size="small" icon={<CloseOutlined />} onClick={handleCancel}>
                  取消
                </Button>
                <Button size="small" type="primary" icon={<SaveOutlined />} onClick={handleSave}>
                  保存
                </Button>
              </Space>
            </Space>
          ) : (
            <>
              {/* 内容区域 - 固定高度 */}
              <div style={{ 
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                minHeight: 0
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
                      onUpdate(collection.id, { collection_title: newTitle })
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
                  onClick={() => setShowModal(true)}
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
                <Button 
                  type="text" 
                  size="small"
                  icon={<EditOutlined />}
                  onClick={() => setShowClipList(true)}
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
                  片段
                </Button>
                {onGenerateVideo && (
                  <Button 
                    type="text" 
                    size="small"
                    icon={<DownloadOutlined />}
                    onClick={() => onGenerateVideo(collection.id)}
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
                    下载
                  </Button>
                )}
              </div>
            </>
          )}
        </div>
        </Card>
      </div>

      {/* 片段列表模态框 */}
      <Modal
        title={`${collection.collection_title} - 片段列表`}
        open={showClipList}
        onCancel={() => setShowClipList(false)}
        footer={[
          <Button key="close" onClick={() => setShowClipList(false)}>
            关闭
          </Button>,
          onGenerateVideo && (
            <Button 
              key="generate" 
              type="primary" 
              onClick={() => {
                onGenerateVideo(collection.id)
                setShowClipList(false)
              }}
            >
              导出完整视频
            </Button>
          )
        ].filter(Boolean)}
        width={600}
      >
        <div style={{ marginBottom: '16px' }}>
          <Text type="secondary">
            拖拽调整片段顺序，生成视频时将按此顺序拼接
          </Text>
        </div>
        
        <DragDropContext onDragEnd={handleDragEnd}>
          <Droppable droppableId="clips">
            {(provided) => (
              <div {...provided.droppableProps} ref={provided.innerRef}>
                <List
                  dataSource={collection.clip_ids}
                  renderItem={(clipId, index) => {
                    const clip = clips.find(c => c.id === clipId)
                    if (!clip) return null
                    
                    return (
                      <Draggable key={clipId} draggableId={clipId} index={index}>
                        {(provided, snapshot) => (
                          <div
                            ref={provided.innerRef}
                            {...provided.draggableProps}
                            style={{
                              ...provided.draggableProps.style,
                              marginBottom: '8px'
                            }}
                          >
                            <List.Item
                              style={{
                                background: snapshot.isDragging ? '#f0f0f0' : 'white',
                                border: '1px solid #d9d9d9',
                                borderRadius: '6px',
                                padding: '12px'
                              }}
                              actions={[
                                <div {...provided.dragHandleProps}>
                                  <DragOutlined style={{ cursor: 'grab' }} />
                                </div>
                              ]}
                            >
                              <List.Item.Meta
                                title={
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <Text strong>{index + 1}.</Text>
                                    <Text ellipsis style={{ flex: 1 }}>
                                      {clip.title || clip.outline}
                                    </Text>
                                    <Tag color="blue">{(clip.final_score * 100).toFixed(0)}分</Tag>
                                  </div>
                                }
                                description={
                                  <Text type="secondary" ellipsis>
                                    {clip.start_time.substring(0, 8)} - {clip.end_time.substring(0, 8)}
                                  </Text>
                                }
                              />
                            </List.Item>
                          </div>
                        )}
                      </Draggable>
                    )
                  }}
                />
                {provided.placeholder}
              </div>
            )}
          </Droppable>
        </DragDropContext>
      </Modal>
    </>
  )
}

export default CollectionCard
import React, { useState } from 'react'
import { Card, Typography, Button, Space, Input, Tag, List, Modal, Tooltip, Divider, Popconfirm } from 'antd'
import { EditOutlined, DownloadOutlined, SaveOutlined, CloseOutlined, PlayCircleOutlined, DragOutlined, DeleteOutlined } from '@ant-design/icons'
import { Collection, Clip } from '../store/useProjectStore'
import { DragDropContext, Droppable, Draggable, DropResult } from 'react-beautiful-dnd'

const { Text, Title } = Typography
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
  onDownload,
  onDelete,
  onGenerateVideo,
  onReorderClips
}) => {
  const [editing, setEditing] = useState(false)
  const [editTitle, setEditTitle] = useState(collection.collection_title)
  const [editSummary, setEditSummary] = useState(collection.collection_summary)
  const [showClipList, setShowClipList] = useState(false)
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

  const averageScore = collectionClips.length > 0 
    ? collectionClips.reduce((sum, clip) => sum + clip.final_score, 0) / collectionClips.length
    : 0

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
          hoverable
          style={{ height: '100%', width: '100%' }}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
          cover={
            <div 
              style={{ 
                height: '120px', 
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                position: 'relative'
              }}
            >
              <PlayCircleOutlined style={{ fontSize: '36px', color: 'white', opacity: 0.9 }} />
              <div 
                style={{
                  position: 'absolute',
                  top: '8px',
                  right: '8px',
                  background: 'rgba(0,0,0,0.6)',
                  color: 'white',
                  padding: '4px 8px',
                  borderRadius: '4px',
                  fontSize: '12px'
                }}
              >
                {collectionClips.length} 个片段
              </div>
              <div 
                style={{
                  position: 'absolute',
                  bottom: '8px',
                  left: '8px',
                  right: '8px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}
              >
                <Text style={{ color: 'white', fontSize: '12px' }}>
                  总时长: {formatDuration(totalDuration)}
                </Text>
                <div 
                  style={{
                    background: averageScore >= 0.8 ? '#52c41a' : averageScore >= 0.7 ? '#1890ff' : '#faad14',
                    color: 'white',
                    padding: '2px 6px',
                    borderRadius: '12px',
                    fontSize: '12px',
                    fontWeight: 'bold'
                  }}
                >
                  {(averageScore * 100).toFixed(0)}分
                </div>
              </div>
            </div>
          }
          actions={[
            <Tooltip key="edit" title="编辑">
              <Button 
                type="text" 
                icon={<EditOutlined />}
                onClick={() => setEditing(true)}
              />
            </Tooltip>,
            <Tooltip key="clips" title="查看片段">
              <Button 
                type="text"
                onClick={() => setShowClipList(true)}
              >
                片段
              </Button>
            </Tooltip>,
            onGenerateVideo && (
              <Tooltip key="generate" title="导出完整视频">
                <Button 
                  type="text"
                  onClick={() => onGenerateVideo(collection.id)}
                >
                  导出完整视频
                </Button>
              </Tooltip>
            )
          ].filter(Boolean)}
      >
        <div style={{ padding: '0 8px' }}>
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
            <Space direction="vertical" style={{ width: '100%' }} size="small">
              <Title level={5} ellipsis={{ rows: 2 }} style={{ margin: 0, minHeight: '44px' }}>
                {collection.collection_title}
              </Title>
              
              <div>
                {collection.collection_type === 'manual' ? (
                  <Tag color="green">手动创建</Tag>
                ) : (
                  <Tag color="purple">AI推荐</Tag>
                )}
              </div>
              
              <div style={{ minHeight: '60px', fontSize: '12px' }}>
                <Text 
                  type="secondary" 
                  ellipsis
                  style={{ 
                    display: '-webkit-box',
                    WebkitLineClamp: 3,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden'
                  }}
                >
                  {collection.collection_summary}
                </Text>
              </div>
              
              <div style={{ marginTop: '8px' }}>
                <Text type="secondary" style={{ fontSize: '11px' }}>
                  包含片段：{collectionClips.slice(0, 2).map(clip => clip.title || clip.outline).join('、')}
                  {collectionClips.length > 2 && `等${collectionClips.length}个`}
                </Text>
              </div>
            </Space>
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
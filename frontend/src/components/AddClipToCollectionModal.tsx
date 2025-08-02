import React, { useState, useMemo } from 'react'
import { Modal, List, Button, Typography, Tag, Input, Space, Empty, Checkbox } from 'antd'
import { SearchOutlined, PlayCircleOutlined } from '@ant-design/icons'
import { Clip } from '../store/useProjectStore'
import './AddClipToCollectionModal.css'

const { Text, Title } = Typography
const { Search } = Input

interface AddClipToCollectionModalProps {
  visible: boolean
  clips: Clip[]
  existingClipIds: string[]
  onCancel: () => void
  onConfirm: (selectedClipIds: string[]) => void
}

const AddClipToCollectionModal: React.FC<AddClipToCollectionModalProps> = ({
  visible,
  clips,
  existingClipIds,
  onCancel,
  onConfirm
}) => {
  const [selectedClipIds, setSelectedClipIds] = useState<string[]>([])
  const [searchText, setSearchText] = useState('')

  // 过滤出不在当前合集中的切片
  const availableClips = useMemo(() => {
    return clips.filter(clip => !existingClipIds.includes(clip.id))
  }, [clips, existingClipIds])

  // 根据搜索文本过滤切片
  const filteredClips = useMemo(() => {
    if (!searchText.trim()) {
      return availableClips
    }
    
    const searchLower = searchText.toLowerCase()
    return availableClips.filter(clip => {
      const title = (clip.title || clip.generated_title || '').toLowerCase()
      const reason = (clip.recommend_reason || '').toLowerCase()
      const content = (clip.content || []).join(' ').toLowerCase()
      
      return title.includes(searchLower) || 
             reason.includes(searchLower) || 
             content.includes(searchLower)
    })
  }, [availableClips, searchText])

  const formatDuration = (clip: Clip) => {
    const start = clip.start_time.split(':')
    const end = clip.end_time.split(':')
    const startSeconds = parseInt(start[0]) * 3600 + parseInt(start[1]) * 60 + parseFloat(start[2].replace(',', '.'))
    const endSeconds = parseInt(end[0]) * 3600 + parseInt(end[1]) * 60 + parseFloat(end[2].replace(',', '.'))
    const duration = endSeconds - startSeconds
    const mins = Math.floor(duration / 60)
    const secs = Math.floor(duration % 60)
    return `${mins}:${String(secs).padStart(2, '0')}`
  }

  const handleClipToggle = (clipId: string) => {
    setSelectedClipIds(prev => {
      if (prev.includes(clipId)) {
        return prev.filter(id => id !== clipId)
      } else {
        return [...prev, clipId]
      }
    })
  }

  const handleSelectAll = () => {
    if (selectedClipIds.length === filteredClips.length) {
      setSelectedClipIds([])
    } else {
      setSelectedClipIds(filteredClips.map(clip => clip.id))
    }
  }

  const handleConfirm = () => {
    onConfirm(selectedClipIds)
    setSelectedClipIds([])
    setSearchText('')
  }

  const handleCancel = () => {
    onCancel()
    setSelectedClipIds([])
    setSearchText('')
  }

  return (
    <Modal
      title="添加切片到合集"
      open={visible}
      onCancel={handleCancel}
      width={800}
      className="add-clip-modal"
      footer={[
        <Button key="cancel" onClick={handleCancel}>
          取消
        </Button>,
        <Button 
          key="confirm" 
          type="primary" 
          onClick={handleConfirm}
          disabled={selectedClipIds.length === 0}
        >
          添加 {selectedClipIds.length > 0 && `(${selectedClipIds.length})`}
        </Button>
      ]}
    >
      <div className="add-clip-modal-content">
        {/* 搜索和操作栏 */}
        <div className="search-section">
          <Search
            placeholder="搜索切片标题、内容或推荐理由..."
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ marginBottom: 16 }}
            allowClear
          />
          
          <div className="action-bar">
            <Space>
              <Text type="secondary">
                可添加 {filteredClips.length} 个切片
              </Text>
              {filteredClips.length > 0 && (
                <Button 
                  type="link" 
                  size="small"
                  onClick={handleSelectAll}
                >
                  {selectedClipIds.length === filteredClips.length ? '取消全选' : '全选'}
                </Button>
              )}
            </Space>
          </div>
        </div>

        {/* 切片列表 */}
        <div className="clips-list-container">
          {filteredClips.length > 0 ? (
            <List
              dataSource={filteredClips}
              renderItem={(clip) => {
                const isSelected = selectedClipIds.includes(clip.id)
                return (
                  <List.Item
                    className={`clip-list-item ${isSelected ? 'selected' : ''}`}
                    onClick={() => handleClipToggle(clip.id)}
                  >
                    <div className="clip-item-content">
                      <div className="clip-checkbox">
                        <Checkbox 
                          checked={isSelected}
                          onChange={() => handleClipToggle(clip.id)}
                        />
                      </div>
                      
                      <div className="clip-info">
                        <div className="clip-title">
                          {clip.title || clip.generated_title}
                        </div>
                        
                        <div className="clip-meta">
                          <Space size="small">
                            <Tag color="blue">{formatDuration(clip)}</Tag>
                            <Tag color="green">
                              分数: {(clip.final_score * 100).toFixed(0)}
                            </Tag>
                          </Space>
                        </div>
                        
                        {clip.recommend_reason && (
                          <div className="clip-reason">
                            <Text type="secondary" style={{ fontSize: '12px' }}>
                              {clip.recommend_reason}
                            </Text>
                          </div>
                        )}
                        
                        {clip.content && clip.content.length > 0 && (
                          <div className="clip-content">
                            <Text type="secondary" style={{ fontSize: '11px' }}>
                              {clip.content.slice(0, 2).join('、')}
                              {clip.content.length > 2 && '...'}
                            </Text>
                          </div>
                        )}
                      </div>
                    </div>
                  </List.Item>
                )
              }}
            />
          ) : (
            <div className="empty-state">
              <Empty
                image={<PlayCircleOutlined style={{ fontSize: '48px', color: '#d9d9d9' }} />}
                description={
                  availableClips.length === 0 
                    ? "所有切片都已在合集中" 
                    : "没有找到匹配的切片"
                }
              />
            </div>
          )}
        </div>
      </div>
    </Modal>
  )
}

export default AddClipToCollectionModal
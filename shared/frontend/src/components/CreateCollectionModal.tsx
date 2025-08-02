import React, { useState } from 'react'
import { Modal, Input, Checkbox, Typography, Button, Divider } from 'antd'
import { PlusOutlined, TagOutlined, FileTextOutlined, VideoCameraOutlined } from '@ant-design/icons'
import './CreateCollectionModal.css'

const { Text, Title } = Typography
const { TextArea } = Input

interface Clip {
  id: string
  title?: string
  generated_title?: string
  start_time: string
  end_time: string
  final_score: number
}

interface CreateCollectionModalProps {
  visible: boolean
  clips: Clip[]
  onCancel: () => void
  onCreate: (title: string, summary: string, clipIds: string[]) => void
  loading?: boolean
}

const CreateCollectionModal: React.FC<CreateCollectionModalProps> = ({
  visible,
  clips,
  onCancel,
  onCreate,
  loading = false
}) => {
  const [title, setTitle] = useState('')
  const [summary, setSummary] = useState('')
  const [selectedClips, setSelectedClips] = useState<string[]>([])

  const handleCreate = () => {
    if (!title.trim()) {
      return
    }
    onCreate(title.trim(), summary.trim(), selectedClips)
  }

  const handleCancel = () => {
    setTitle('')
    setSummary('')
    setSelectedClips([])
    onCancel()
  }

  const handleClipToggle = (clipId: string) => {
    setSelectedClips(prev => 
      prev.includes(clipId) 
        ? prev.filter(id => id !== clipId)
        : [...prev, clipId]
    )
  }

  const selectAllClips = () => {
    setSelectedClips(clips.map(clip => clip.id))
  }

  const clearAllClips = () => {
    setSelectedClips([])
  }

  return (
    <Modal
      title={null}
      open={visible}
      onCancel={handleCancel}
      footer={null}
      width={900}
      className="create-collection-modal"
      destroyOnClose
    >
      <div className="modal-content">
        {/* 头部 */}
        <div className="modal-header">
          <div className="header-icon">
            <PlusOutlined />
          </div>
          <div className="header-text">
            <Title level={3} className="modal-title">创建新合集</Title>
            <Text className="modal-subtitle">将精选片段组合成一个主题合集</Text>
          </div>
        </div>

        <Divider className="header-divider" />

        {/* 表单区域 */}
        <div className="form-section">
          {/* 合集标题 */}
          <div className="form-item">
            <div className="form-label">
              <TagOutlined className="label-icon" />
              <Text strong>合集标题</Text>
              <span className="required-mark">*</span>
            </div>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="为您的合集起一个吸引人的标题"
              className="form-input"
              size="large"
            />
          </div>

          {/* 合集简介 */}
          <div className="form-item">
            <div className="form-label">
              <FileTextOutlined className="label-icon" />
              <Text strong>合集简介</Text>
            </div>
            <TextArea
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              placeholder="简要描述这个合集的主题和内容（可选）"
              className="form-textarea"
              rows={3}
              showCount
              maxLength={200}
            />
          </div>

          {/* 片段选择 */}
          <div className="form-item">
            <div className="form-label">
              <VideoCameraOutlined className="label-icon" />
              <Text strong>选择片段</Text>
              <Text className="clip-count">（已选择 {selectedClips.length} 个片段）</Text>
            </div>
            
            {/* 批量操作 */}
            <div className="batch-actions">
              <Button 
                type="link" 
                size="small" 
                onClick={selectAllClips}
                className="batch-btn"
              >
                全选
              </Button>
              <Button 
                type="link" 
                size="small" 
                onClick={clearAllClips}
                className="batch-btn"
              >
                清空
              </Button>
            </div>

            {/* 片段列表 */}
            <div className="clips-container">
              {clips.map((clip) => (
                <div 
                  key={clip.id} 
                  className={`clip-item ${selectedClips.includes(clip.id) ? 'selected' : ''}`}
                  onClick={() => handleClipToggle(clip.id)}
                >
                  <Checkbox
                    checked={selectedClips.includes(clip.id)}
                    onChange={() => handleClipToggle(clip.id)}
                    className="clip-checkbox"
                  />
                  <div className="clip-content">
                    <div className="clip-title">
                      {clip.title || clip.generated_title}
                    </div>
                    <div className="clip-meta">
                      <span className="clip-time">
                        {clip.start_time.substring(0, 8)} - {clip.end_time.substring(0, 8)}
                      </span>
                      <span className="clip-score">
                        评分: {(clip.final_score * 100).toFixed(0)}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 底部操作 */}
        <div className="modal-footer">
          <Button 
            onClick={handleCancel}
            className="cancel-btn"
            size="large"
          >
            取消
          </Button>
          <Button
            type="primary"
            onClick={handleCreate}
            loading={loading}
            disabled={!title.trim() || selectedClips.length === 0}
            className="create-btn"
            size="large"
          >
            创建合集
          </Button>
        </div>
      </div>
    </Modal>
  )
}

export default CreateCollectionModal
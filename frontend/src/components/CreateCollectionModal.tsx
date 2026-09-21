import { t } from '../i18n'
import { useTranslation } from 'react-i18next'
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
  useTranslation()
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
            <Title level={3} className="modal-title">{t("创建新合集")}</Title>
            <Text className="modal-subtitle">{t("将精选片段组合成一个主题合集")}</Text>
          </div>
        </div>

        <Divider className="header-divider" />

        {/* 表单区域 */}
        <div className="form-section">
          {/* 合集标题 */}
          <div className="form-item">
            <div className="form-label">
              <TagOutlined className="label-icon" />
              <Text strong>{t("合集标题")}</Text>
              <span className="required-mark">*</span>
            </div>
            <Input
              placeholder={t("请输入合集标题")}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="form-input"
              maxLength={50}
              showCount
            />
          </div>

          {/* 合集描述 */}
          <div className="form-item">
            <div className="form-label">
              <FileTextOutlined className="label-icon" />
              <Text strong>{t("合集描述")}</Text>
            </div>
            <TextArea
              placeholder={t("请输入合集描述（可选）")}
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              className="form-textarea"
              rows={3}
              maxLength={200}
              showCount
            />
          </div>

          {/* 选择片段 */}
          <div className="form-item">
            <div className="form-label">
              <VideoCameraOutlined className="label-icon" />
              <Text strong>{t("选择片段")}</Text>
              <span className="required-mark">*</span>
            </div>
            
            <div className="clips-selection">
              <div className="selection-header">
                <Text className="selection-info">{t("已选数量", { count: selectedClips.length })}</Text>
                <div className="selection-actions">
                  <Button 
                    type="link" 
                    size="small" 
                    onClick={selectAllClips}
                    className="action-btn"
                  >{t("全选")}</Button>
                  <Button 
                    type="link" 
                    size="small" 
                    onClick={clearAllClips}
                    className="action-btn"
                  >{t("清空")}</Button>
                </div>
              </div>
              
              <div className="clips-grid">
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
                        {clip.generated_title || clip.title || t("未命名片段")}
                      </div>
                      <div className="clip-meta">
                        <Text type="secondary" style={{ fontSize: '12px' }}>
                          {clip.start_time} - {clip.end_time}{t("• 评分:")}{(clip.final_score * 100).toFixed(0)}
                        </Text>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* 底部操作 */}
        <div className="modal-footer">
          <Button onClick={handleCancel} className="cancel-btn">{t("取消")}</Button>
          <Button 
            type="primary" 
            onClick={handleCreate}
            disabled={!title.trim() || selectedClips.length === 0}
            loading={loading}
            className="create-btn"
          >{t("创建合集")}</Button>
        </div>
      </div>
    </Modal>
  )
}

export default CreateCollectionModal
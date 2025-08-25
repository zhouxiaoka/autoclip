import React, { useState, useRef } from 'react'
import { Modal, Typography, Button, Tag, Space, Row, Col, Divider } from 'antd'
import { 
  PlayCircleOutlined, 
  DownloadOutlined, 
  ClockCircleOutlined, 
  StarFilled,
  CloseOutlined
} from '@ant-design/icons'
import ReactPlayer from 'react-player'
import { Clip } from '../store/useProjectStore'
import { projectApi } from '../services/api'

const { Text, Title } = Typography

interface ClipDetailModalProps {
  visible: boolean
  clip: Clip | null
  projectId: string
  onClose: () => void
  onDownload: (clipId: string) => void
}

const ClipDetailModal: React.FC<ClipDetailModalProps> = ({
  visible,
  clip,
  projectId,
  onClose,
  onDownload
}) => {
  const [playing, setPlaying] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const playerRef = useRef<ReactPlayer>(null)

  const formatTime = (timeStr: string) => {
    if (!timeStr) return '00:00:00'
    // 移除小数点后的毫秒部分，只保留时分秒
    return timeStr.replace(',', '.').substring(0, 8)
  }

  const getDuration = () => {
    if (!clip?.start_time || !clip?.end_time) return '00:00:00'
    const start = clip.start_time.replace(',', '.')
    const end = clip.end_time.replace(',', '.')
    return `${start.substring(0, 8)} - ${end.substring(0, 8)}`
  }

  const getScoreColor = (score: number) => {
    // 根据分数区间设置不同的颜色
    if (score >= 0.9) return '#52c41a' // 绿色 - 优秀
    if (score >= 0.8) return '#1890ff' // 蓝色 - 良好
    if (score >= 0.7) return '#faad14' // 橙色 - 一般
    if (score >= 0.6) return '#ff7a45' // 红橙色 - 较差
    return '#ff4d4f' // 红色 - 差
  }

  const handleDownload = async () => {
    if (!clip) return
    setDownloading(true)
    try {
      await onDownload(clip.id)
    } finally {
      setDownloading(false)
    }
  }

  const handleClose = () => {
    setPlaying(false)
    onClose()
  }

  if (!clip) return null

  return (
    <Modal
      visible={visible}
      onCancel={handleClose}
      footer={null}
      width={800}
      centered
      destroyOnClose
      style={{ top: 20 }}
      styles={{
        body: {
          padding: 0,
          background: 'rgba(26, 26, 46, 0.95)',
          borderRadius: '12px'
        }
      }}
    >
      <div style={{ padding: '24px' }}>
        {/* 头部 */}
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          marginBottom: '20px'
        }}>
          <Title level={4} style={{ margin: 0, color: '#ffffff' }}>
            切片详情
          </Title>
          <Button 
            type="text" 
            icon={<CloseOutlined />} 
            onClick={handleClose}
            style={{ color: '#cccccc' }}
          />
        </div>

        <Row gutter={24}>
          {/* 左侧视频播放器 */}
          <Col span={14}>
            <div style={{ 
              background: '#000', 
              borderRadius: '8px', 
              overflow: 'hidden',
              marginBottom: '16px'
            }}>
              <ReactPlayer
                ref={playerRef}
                url={projectApi.getClipVideoUrl(projectId, clip.id, clip.title || clip.generated_title)}
                width="100%"
                height="300px"
                playing={playing}
                controls
                onPlay={() => setPlaying(true)}
                onPause={() => setPlaying(false)}
                style={{ borderRadius: '8px' }}
              />
            </div>

            {/* 视频信息 */}
            <div style={{ marginBottom: '16px' }}>
              <Space size="middle">
                <Tag color="blue" icon={<ClockCircleOutlined />}>
                  {getDuration()}
                </Tag>
                {clip.final_score && (
                  <Tag 
                    icon={<StarFilled />}
                    style={{ 
                      background: getScoreColor(clip.final_score),
                      color: 'white',
                      border: 'none'
                    }}
                  >
                    评分: {(clip.final_score * 100).toFixed(0)}分
                  </Tag>
                )}
                {clip.outline && (
                  <Tag color="purple">{clip.outline}</Tag>
                )}
              </Space>
            </div>

            {/* 操作按钮 */}
            <Space>
              <Button 
                type="primary" 
                icon={<PlayCircleOutlined />}
                onClick={() => setPlaying(!playing)}
              >
                {playing ? '暂停' : '播放'}
              </Button>
              <Button 
                type="default" 
                icon={<DownloadOutlined />}
                loading={downloading}
                onClick={handleDownload}
              >
                下载切片
              </Button>
            </Space>
          </Col>

          {/* 右侧详细信息 */}
          <Col span={10}>
            <div style={{ color: '#ffffff' }}>
              {/* 标题 */}
              <div style={{ marginBottom: '16px' }}>
                <Title level={5} style={{ color: '#ffffff', marginBottom: '8px' }}>
                  {clip.generated_title || clip.title || '未命名片段'}
                </Title>
                <Text style={{ color: '#cccccc', fontSize: '12px' }}>
                  ID: {clip.id}
                </Text>
              </div>

              <Divider style={{ borderColor: 'rgba(255,255,255,0.1)' }} />

              {/* 内容要点 */}
              {clip.content && clip.content.length > 0 && (
                <div style={{ marginBottom: '16px' }}>
                  <Text strong style={{ color: '#ffffff', display: 'block', marginBottom: '8px' }}>
                    内容要点:
                  </Text>
                  <div>
                    {clip.content.map((point, index) => (
                      <div key={index} style={{ 
                        color: '#cccccc', 
                        fontSize: '12px',
                        marginBottom: '4px',
                        paddingLeft: '8px'
                      }}>
                        • {point}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 推荐理由 */}
              {clip.recommend_reason && (
                <div style={{ marginBottom: '16px' }}>
                  <Text strong style={{ color: '#ffffff', display: 'block', marginBottom: '8px' }}>
                    推荐理由:
                  </Text>
                  <Text style={{ color: '#cccccc', fontSize: '12px' }}>
                    {clip.recommend_reason}
                  </Text>
                </div>
              )}

              {/* 时间信息 */}
              <div style={{ marginBottom: '16px' }}>
                <Text strong style={{ color: '#ffffff', display: 'block', marginBottom: '8px' }}>
                  时间信息:
                </Text>
                <div style={{ color: '#cccccc', fontSize: '12px' }}>
                  <div>开始时间: {formatTime(clip.start_time || '00:00')}</div>
                  <div>结束时间: {formatTime(clip.end_time || '00:00')}</div>
                </div>
              </div>

              {/* 其他信息 */}
              {clip.content && clip.content.length > 0 && (
                <div style={{ marginBottom: '16px' }}>
                  <Text strong style={{ color: '#ffffff', display: 'block', marginBottom: '8px' }}>
                    详细内容:
                  </Text>
                  <Text style={{ 
                    color: '#cccccc', 
                    fontSize: '12px',
                    display: 'block',
                    maxHeight: '100px',
                    overflow: 'auto'
                  }}>
                    {clip.content.join(' ')}
                  </Text>
                </div>
              )}
            </div>
          </Col>
        </Row>
      </div>
    </Modal>
  )
}

export default ClipDetailModal 
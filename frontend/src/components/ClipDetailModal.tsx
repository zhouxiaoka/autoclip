import React, { useState, useRef } from 'react'
import { Modal, Typography, Button, Tag, Space, Row, Col, Divider, message } from 'antd'
import { 
  PlayCircleOutlined, 
  DownloadOutlined, 
  ClockCircleOutlined, 
  StarFilled,
  CloseOutlined,
  EditOutlined
} from '@ant-design/icons'
import ReactPlayer from 'react-player'
import { Clip } from '../store/useProjectStore'
import { projectApi } from '../services/api'
import SubtitleEditor from './SubtitleEditor'
import { subtitleEditorApi } from '../services/subtitleEditorApi'
import { SubtitleSegment, VideoEditOperation } from '../types/subtitle'

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
  const [showSubtitleEditor, setShowSubtitleEditor] = useState(false)
  const [subtitleData, setSubtitleData] = useState<SubtitleSegment[]>([])
  const [loadingSubtitles, setLoadingSubtitles] = useState(false)
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

  const handleOpenSubtitleEditor = async () => {
    if (!clip) return
    
    console.log('Opening subtitle editor for clip:', clip.id)
    setLoadingSubtitles(true)
    try {
      // 获取字幕数据
      const response = await subtitleEditorApi.getClipSubtitles(projectId, clip.id)
      console.log('Subtitle data received:', response)
      setSubtitleData(response.segments)
      setShowSubtitleEditor(true)
      console.log('Subtitle editor should be visible now')
    } catch (error) {
      console.error('获取字幕数据失败:', error)
      message.error('获取字幕数据失败')
    } finally {
      setLoadingSubtitles(false)
    }
  }

  const handleSubtitleEditorClose = () => {
    setShowSubtitleEditor(false)
    setSubtitleData([])
  }

  const handleSubtitleEditorSave = async (operations: VideoEditOperation[]) => {
    if (!clip) return
    
    try {
      // 提取要删除的字幕段ID
      const deletedSegments = operations
        .filter(op => op.type === 'delete')
        .flatMap(op => op.segmentIds)

      if (deletedSegments.length === 0) {
        console.log('没有删除操作')
        return
      }

      // 执行视频编辑
      const result = await subtitleEditorApi.editClipBySubtitles(
        projectId,
        clip.id,
        deletedSegments
      )

      if (result.success) {
        console.log('视频编辑成功:', result)
        // 这里可以添加成功提示
        // 可以刷新片段列表或更新UI
      }
    } catch (error) {
      console.error('视频编辑失败:', error)
      // 这里可以添加错误提示
    }
  }

  if (!clip) return null

  return (
    <>
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
              {console.log('Rendering operation buttons in ClipDetailModal')}
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
                <Button 
                  type="default" 
                  icon={<EditOutlined />}
                  loading={loadingSubtitles}
                  onClick={handleOpenSubtitleEditor}
                  style={{ border: '2px solid red' }} // 添加红色边框以便识别
                >
                  字幕编辑
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
                          fontSize: '14px',
                          marginBottom: '4px',
                          padding: '4px 8px',
                          background: 'rgba(255,255,255,0.05)',
                          borderRadius: '4px'
                        }}>
                          • {point}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 时间戳信息 */}
                <div style={{ marginBottom: '16px' }}>
                  <Text strong style={{ color: '#ffffff', display: 'block', marginBottom: '8px' }}>
                    时间信息:
                  </Text>
                  <div style={{ color: '#cccccc', fontSize: '14px' }}>
                    <div>开始时间: {formatTime(clip.start_time)}</div>
                    <div>结束时间: {formatTime(clip.end_time)}</div>
                  </div>
                </div>


              </div>
            </Col>
          </Row>
        </div>
      </Modal>

      {/* 字幕编辑器 */}
      {showSubtitleEditor && (
        <>
          {console.log('Rendering SubtitleEditor with:', { showSubtitleEditor, subtitleDataLength: subtitleData.length })}
          <SubtitleEditor
            videoUrl={projectApi.getClipVideoUrl(projectId, clip.id, clip.title || clip.generated_title)}
            subtitles={subtitleData}
            onSave={handleSubtitleEditorSave}
            onClose={handleSubtitleEditorClose}
          />
        </>
      )}
    </>
  )
}

export default ClipDetailModal 
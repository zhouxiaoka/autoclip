import React, { useState, useEffect, useRef } from 'react'
import { Card, Typography, Button, Tag, Tooltip, Modal } from 'antd'
import { PlayCircleOutlined, DownloadOutlined, ClockCircleOutlined, StarFilled } from '@ant-design/icons'
import ReactPlayer from 'react-player'
import { Clip } from '../store/useProjectStore'
import './ClipCard.css'

const { Text, Title } = Typography

interface ClipCardProps {
  clip: Clip
  videoUrl?: string
  onDownload: (clipId: string) => void
}

const ClipCard: React.FC<ClipCardProps> = ({ 
  clip, 
  videoUrl, 
  onDownload
}) => {

  const [showPlayer, setShowPlayer] = useState(false)
  const [videoThumbnail, setVideoThumbnail] = useState<string | null>(null)
  const playerRef = useRef<ReactPlayer>(null)



  // 生成视频缩略图
  useEffect(() => {
    if (videoUrl) {
      generateThumbnail()
    }
  }, [videoUrl])

  const generateThumbnail = () => {
    if (!videoUrl) return
    
    const video = document.createElement('video')
    video.crossOrigin = 'anonymous'
    video.currentTime = 1 // 获取第1秒的帧作为缩略图
    
    video.onloadeddata = () => {
      const canvas = document.createElement('canvas')
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      ctx.drawImage(video, 0, 0)
      
      const thumbnail = canvas.toDataURL('image/jpeg', 0.8)
      setVideoThumbnail(thumbnail)
    }
    
    video.src = videoUrl
  }

  const handleDownloadWithTitle = async () => {
    try {
      const fileName = `${clip.generated_title || clip.title || '视频片段'}.mp4`
      
      // 使用fetch获取视频文件
      const response = await fetch(videoUrl || '')
      if (!response.ok) {
        throw new Error('下载失败')
      }
      
      const blob = await response.blob()
      
      // 创建下载链接
      const downloadUrl = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = fileName
      
      // 触发下载
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      
      // 清理URL对象
      window.URL.revokeObjectURL(downloadUrl)
      
      // 同时调用原有的下载方法
      onDownload(clip.id)
    } catch (error) {
      console.error('下载失败:', error)
      // 如果fetch失败，回退到原来的方法
      const fileName = `${clip.generated_title || clip.title || '视频片段'}.mp4`
      const link = document.createElement('a')
      link.href = videoUrl || ''
      link.download = fileName
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      onDownload(clip.id)
    }
  }

  const handleClosePlayer = () => {
    // 停止视频播放
    if (playerRef.current) {
      playerRef.current.seekTo(0)
    }
    setShowPlayer(false)
  }



  const formatTime = (timeStr: string) => {
    // 将 SRT 时间格式转换为显示格式
    return timeStr.replace(',', '.').substring(0, 8)
  }

  const getDuration = () => {
    // 简单计算时长（实际项目中应该更精确）
    const start = clip.start_time.split(':')
    const end = clip.end_time.split(':')
    const startSeconds = parseInt(start[0]) * 3600 + parseInt(start[1]) * 60 + parseFloat(start[2].replace(',', '.'))
    const endSeconds = parseInt(end[0]) * 3600 + parseInt(end[1]) * 60 + parseFloat(end[2].replace(',', '.'))
    const duration = endSeconds - startSeconds
    return `${Math.floor(duration / 60)}:${String(Math.floor(duration % 60)).padStart(2, '0')}`
  }

  const getScoreColor = (score: number) => {
    if (score >= 0.9) return '#52c41a'
    if (score >= 0.8) return '#1890ff'
    if (score >= 0.7) return '#faad14'
    return '#ff4d4f'
  }

  // 生成内容要点的tooltip内容
  const getContentTooltip = () => {
    if (clip.content && clip.content.length > 0) {
      return (
        <div>
          <div style={{ fontWeight: 'bold', marginBottom: '8px' }}>内容要点：</div>
          {clip.content.map((point, index) => (
            <div key={index} style={{ marginBottom: '4px' }}>
              • {point}
            </div>
          ))}
        </div>
      )
    }
    return '暂无内容要点'
  }

  return (
    <>
      <Tooltip 
        title={getContentTooltip()}
        placement="top"
        overlayStyle={{ maxWidth: '300px' }}
      >
        <Card
          className="clip-card"
          hoverable
          style={{ 
            height: '380px',
            borderRadius: '16px',
            border: '1px solid #303030',
            background: 'linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%)',
            overflow: 'hidden'
          }}
          bodyStyle={{ padding: 0 }}
          cover={
            <div 
              style={{ 
                height: '200px', 
                background: videoThumbnail 
                  ? `url(${videoThumbnail}) center/cover no-repeat` 
                  : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                position: 'relative',
                cursor: 'pointer',
                overflow: 'hidden'
              }}
              onClick={() => setShowPlayer(true)}
            >
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
                <PlayCircleOutlined style={{ fontSize: '56px', color: 'white' }} />
              </div>
              
              {/* 顶部信息栏 */}
              <div 
                style={{
                  position: 'absolute',
                  top: '12px',
                  left: '12px',
                  right: '12px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}
              >
                <Tag 
                  color="geekblue" 
                  style={{ 
                    margin: 0, 
                    fontSize: '11px',
                    borderRadius: '8px',
                    border: 'none',
                    background: 'rgba(24, 144, 255, 0.9)',
                    color: 'white',
                    fontWeight: 500
                  }}
                >
                  {clip.outline}
                </Tag>
                <div 
                  style={{
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
                  <ClockCircleOutlined style={{ fontSize: '12px' }} />
                  {getDuration()}
                </div>
              </div>
              
              {/* 底部信息栏 */}
              <div 
                style={{
                  position: 'absolute',
                  bottom: '12px',
                  left: '12px',
                  right: '12px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}
              >
                <div style={{
                  background: 'rgba(0,0,0,0.7)',
                  color: 'white',
                  padding: '4px 8px',
                  borderRadius: '8px',
                  fontSize: '11px'
                }}>
                  {formatTime(clip.start_time)} - {formatTime(clip.end_time)}
                </div>
                <div 
                  style={{
                    background: getScoreColor(clip.final_score),
                    color: 'white',
                    padding: '4px 8px',
                    borderRadius: '12px',
                    fontSize: '12px',
                    fontWeight: 'bold',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.3)'
                  }}
                >
                  <StarFilled style={{ fontSize: '12px' }} />
                  {(clip.final_score * 100).toFixed(0)}分
                </div>
              </div>
            </div>
          }
        >
          <div style={{ padding: '16px', height: '180px', display: 'flex', flexDirection: 'column' }}>
            {/* 标题区域 */}
            <div style={{ marginBottom: '12px' }}>
              <Title 
                level={5} 
                ellipsis={{ rows: 2 }} 
                style={{ 
                  margin: 0, 
                  fontSize: '16px',
                  fontWeight: 600,
                  lineHeight: '1.4',
                  color: '#ffffff',
                  minHeight: '44px'
                }}
              >
                {clip.generated_title || clip.title || '未命名片段'}
              </Title>
            </div>
            
            {/* 推荐理由 */}
            <div style={{ flex: 1, marginBottom: '12px' }}>
              <Text 
                type="secondary" 
                style={{ 
                  fontSize: '13px',
                  display: '-webkit-box',
                  WebkitLineClamp: 4,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                  lineHeight: '1.5',
                  color: '#b0b0b0'
                }}
              >
                {clip.recommend_reason || '暂无推荐理由'}
              </Text>
            </div>
            

          </div>
        </Card>
      </Tooltip>

      {/* 视频播放模态框 */}
      <Modal
        title={clip.generated_title || clip.title || '视频预览'}
        open={showPlayer}
        onCancel={handleClosePlayer}
        footer={[
          <Button key="download" type="primary" icon={<DownloadOutlined />} onClick={handleDownloadWithTitle}>
            下载视频
          </Button>,
          <Button key="close" onClick={handleClosePlayer}>
            关闭
          </Button>
        ]}
        width={800}
        centered
        destroyOnClose
      >
        {videoUrl && (
          <ReactPlayer
            ref={playerRef}
            url={videoUrl}
            width="100%"
            height="400px"
            controls
            playing={showPlayer}
            config={{
              file: {
                attributes: {
                  controlsList: 'nodownload',
                  preload: 'metadata'
                },
                forceHLS: false,
                forceDASH: false
              }
            }}
            onReady={() => {
              console.log('Video ready for seeking')
            }}
            onError={(error) => {
              console.error('ReactPlayer error:', error)
            }}
          />
        )}
      </Modal>
    </>
  )
}

export default ClipCard